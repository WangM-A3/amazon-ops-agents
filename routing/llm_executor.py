"""
routing/llm_executor.py — SMALL/LARGE 引擎的真实 LLM 执行器
=============================================================
替代原先"只估算 Token 不调用模型"的假路由：当 LLM 端点可用时，
用真实大模型按 Agent 角色生成结构化结果（result + kpis），并把
DataProvider 的真实数据注入提示词（数据型 Agent 基于真实数字分析）。

开关：AMAZON_OPS_LLM = auto（默认：端点可用即启用）| on | off
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from llm.client import get_llm_client

logger = logging.getLogger("amazon_ops.llm_executor")


def llm_enabled() -> bool:
    mode = os.getenv("AMAZON_OPS_LLM", "auto").lower()
    if mode == "off":
        return False
    if mode == "on":
        return True
    return get_llm_client().available  # auto


# 数据型 Agent：把真实数据摘要注入提示词
_DATA_AGENTS = {
    "sales_analytics": "sales_summary",
    "inventory_planner": "inventory",
    "ppc_manager": "ads",
    "profit_calculator": "profit",
    "fba_manager": "inventory",
}

# 各 Agent 期望的输出字段（引导 LLM 输出有用结构）
_EXPECTED_KEYS = {
    "product_research": ["market_opportunity", "estimated_demand", "top_keywords", "top_competitors", "recommendation"],
    "listing_optimizer": ["current_analysis", "optimized_title", "bullet_points", "search_terms"],
    "acontent": ["recommended_modules", "image_requirements", "compliance_check"],
    "ppc_manager": ["campaign_overview", "campaign_breakdown", "acos_analysis", "optimization_plan"],
    "inventory_planner": ["current_inventory", "restock_plan", "safety_stock_formula"],
    "profit_calculator": ["cost_breakdown", "profit_analysis", "roi_analysis"],
    "sales_analytics": ["summary", "top_products", "insights"],
    "review_monitor": ["review_summary", "negative_themes", "reply_suggestion"],
    "customer_service": ["message_classification", "draft_reply", "policy_check"],
    "compliance_checker": ["risk_items", "ai_content_compliance", "policy_reference", "recommendation"],
}

# AI 内容合规规则注入（亚马逊/TikTok Shop 双平台 AI 内容标注新规）
_AI_COMPLIANCE_RULE = (
    "AI 内容合规铁律（2025 新规，必须检查并在 ai_content_compliance 中输出）：\n"
    "1) 亚马逊：AI 生成的逼真人物图片（含 A+/旗舰店/广告）必须在元数据添加 AI 披露标签"
    "（contains-synthetic-performer / synthetic-media），未标注有审核不通过/下架风险；纯产品图不受人物披露约束。\n"
    "2) TikTok Shop：AI 生成内容必须显著标注；明确禁止 AI 篡改商品外观、捏造不实效果，违者下架/封店。\n"
    "输出结构：ai_content_compliance: {summary, risk_level, items:[{platform,status,action}], all_pass}"
)


def _grounding_data(agent_id: str, context: dict[str, Any]) -> dict[str, Any]:
    """数据型 Agent 从 DataProvider 取真实数据摘要（无数据返回空）"""
    from data.provider import get_provider
    kind = _DATA_AGENTS.get(agent_id)
    if not kind:
        return {}
    try:
        prov = get_provider()
        if kind == "sales_summary":
            data, src = prov.get_sales_summary(marketplace=context.get("marketplace"), days=30)
            return {"source": src, "sales": data}
        if kind == "inventory":
            data, src = prov.get_inventory()
            # 附带近30天销量，让 LLM 能关联计算 days_left/补货
            sales, sales_src = prov.get_sales_summary(marketplace=context.get("marketplace"), days=30)
            return {"source": src, "inventory": data, "sales_30d": sales if sales.get("items") else {}}
        if kind == "ads":
            data, src = prov.get_ads_metrics(days=30)
            return {"source": src, "ads": data}
        if kind == "profit":
            data, src = prov.get_profit_inputs(sku=context.get("sku"))
            return {"source": src, "profit_inputs": data}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[LLMExecutor] grounding failed for {agent_id}: {exc}")
    return {}


class LLMExecutor:
    """用真实 LLM 执行单个 Agent 任务，输出与模板 Agent 同构的结果"""

    def __init__(self, client: Any = None) -> None:
        self.client = client or get_llm_client()

    def _system_prompt(self, agent_id: str) -> str:
        from agents.base import AGENT_REGISTRY
        meta = AGENT_REGISTRY.get(agent_id, {})
        name = meta.get("name", agent_id)
        desc = meta.get("description", "亚马逊运营专家")
        expected = _EXPECTED_KEYS.get(agent_id, [])
        keys_hint = f" result 应尽量包含字段: {', '.join(expected)}" if expected else ""
        compliance_hint = (
            f"\n{_AI_COMPLIANCE_RULE}" if agent_id in ("compliance_checker", "listing_optimizer", "acontent") else ""
        )
        return (
            f"你是亚马逊运营专家，扮演「{name}」。职责：{desc}。"
            f"{keys_hint}{compliance_hint}。"
            "输出必须是合法 JSON，结构：{\"result\": {…}, \"kpis\": {…}}。"
            "若参考数据为空或标记为 demo，明确说明\"data_available\": false；"
            "若有真实数据，基于数据给出可执行的具体结论，不要编造数据。"
        )

    def _experience_block(self, agent_id: str, task: str) -> list[dict[str, Any]]:
        """检索本店历史经验（v2.1 经验记忆闭环）；无命中返回 []"""
        try:
            from memory.experience_store import retrieve_experiences
            return retrieve_experiences(agent_id, task)
        except Exception as exc:  # noqa: BLE001 — 记忆层故障不阻断主流程
            logger.warning(f"[LLMExecutor] 经验检索失败: {exc}")
            return []

    async def execute(
        self,
        agent_id: str,
        task: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        context = context or {}
        grounding = _grounding_data(agent_id, context)
        user_parts = [f"任务：{task}"]
        if grounding:
            user_parts.append(f"参考数据：{json.dumps(grounding, ensure_ascii=False)[:4000]}")
        # ── v2.1：历史经验注入 ──────────────────────────────────────────────
        exp_used = self._experience_block(agent_id, task)
        if exp_used:
            notes = "\n".join(
                f"- [{e['title']}] {e['content']}" for e in exp_used
            )
            user_parts.append(
                "本店历史经验（来自过往运营沉淀；若与当前任务相关请优先遵循，"
                "无关则忽略）：\n" + notes
            )
        messages = [
            {"role": "system", "content": self._system_prompt(agent_id)},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]
        try:
            parsed, usage = await self.client.chat_json(messages, max_tokens=1024)
            result = parsed.get("result")
            if not isinstance(result, dict):
                raise ValueError("LLM 未返回 result 对象")
            kpis = parsed.get("kpis", {})
            if not isinstance(kpis, dict):
                kpis = {}
            from agents.base import AGENT_REGISTRY
            meta = AGENT_REGISTRY.get(agent_id, {})
            return {
                "agent": f"{meta.get('emoji', '🤖')} {meta.get('name', agent_id)}(LLM)",
                "tokens": usage.get("total_tokens", 0),
                "result": result,
                "kpis": kpis,
                "llm": True,
                "model": self.client.model,
                "experience_used": [
                    {"id": e["id"], "title": e["title"]} for e in exp_used
                ],
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[LLMExecutor] {agent_id} LLM 失败({exc})，回退模板")
            from agents.base import AGENTS
            if agent_id in AGENTS:
                fallback = await AGENTS[agent_id].execute(task, context)
                fallback["llm_mode"] = "template_fallback"
                fallback["experience_used"] = [
                    {"id": e["id"], "title": e["title"]} for e in exp_used
                ]
                return fallback
            return {"agent": agent_id, "tokens": 0, "result": {"error": str(exc)}, "kpis": {}, "llm": False}


LLM_EXECUTOR = LLMExecutor()
