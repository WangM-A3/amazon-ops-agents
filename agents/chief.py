"""
Amazon Operations Silicon Army - ChiefOfStaff (幕僚长)
增强版：集成TaskRouter端云智能路由
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from .base import AGENTS, TASK_ROUTING

logger = logging.getLogger("amazon_ops")


class ChiefOfStaff:
    """
    幕僚长 - 智能任务调度中心（增强版）

    工作流程:
    1. 任务复杂度评估（TaskRouter）
    2. 引擎选择（LOCAL → SMALL → LARGE）
    3. Agent路由（多Agent并行）
    4. 结果聚合（JSON标准化输出）

    增强点（相比YOYO Claw）：
    - 三级引擎路由（本地/小模型/大模型）
    - LOCAL级别零Token消耗
    - 自动降级机制（fallback）
    - 全链路Token预估
    """

    def __init__(self) -> None:
        self.name = "ChiefOfStaff"
        self.emoji = "🎩"
        # 延迟导入避免循环依赖
        self._router = None
        self._executor = None

    @property
    def router(self):
        """懒加载TaskRouter"""
        if self._router is None:
            from routing import ROUTER
            self._router = ROUTER
        return self._router

    @property
    def executor(self):
        """懒加载LocalExecutor"""
        if self._executor is None:
            from routing import EXECUTOR
            self._executor = EXECUTOR
        return self._executor

    def route(self, task: str) -> list[str]:
        """
        关键词路由：返回匹配度最高的Agent ID列表（按分数降序）
        触发多个Agent时并行执行，结果在execute()中聚合。

        路由策略：
        1. TASK_ROUTING 静态关键词（20个核心Agent）
        2. AGENTS.capabilities 动态能力（GUI Agent 等动态注册Agent）
        """
        task_lower = task.lower()
        scores: dict[str, int] = {}

        # 1. 静态关键词路由（TASK_ROUTING）
        for agent_id, keywords in TASK_ROUTING.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[agent_id] = scores.get(agent_id, 0) + score

        # 2. 动态能力路由（AGENTS.capabilities - GUI Agent等）
        for agent_id, agent in AGENTS.items():
            if agent_id in scores:
                continue  # 已通过静态路由得分，跳过
            capabilities = getattr(agent, "capabilities", []) or []
            score = sum(1 for kw in capabilities if kw in task_lower)
            if score > 0:
                scores[agent_id] = score

        if not scores:
            logger.info(f"[ChiefOfStaff] 未匹配到Agent，使用默认：sales_analytics")
            return ["sales_analytics"]

        routed = sorted(scores, key=scores.get, reverse=True)
        logger.info(f"[ChiefOfStaff] 路由 {routed} | 任务: {task[:50]}")
        return routed

    async def execute(self, task: str, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        智能执行：先路由 → 再路由引擎 → 最后执行Agent

        Returns:
            {
                "chief": "🎩 ChiefOfStaff",
                "input": "...",
                "routing": {                # 新增：引擎路由信息
                    "engine": "small_model",
                    "complexity_score": 42,
                    "estimated_tokens": 100,
                    "reasoning": "...",
                    "fallback": "local",
                },
                "routed_agents": ["ppc_manager", "review_monitor"],
                "agent_count": 2,
                "strategy": "parallel",
                "results": { "ppc_manager": {...}, ... },
                "total_tokens": 300,
                "timestamp": "2026-04-13T..."
            }
        """
        routed = self.route(task)
        context = context or {}

        # ── Step 1: 端云路由决策 ──────────────────────────────────────────────
        routing_decision = self.router.route(task, routed)
        engine = routing_decision.engine
        context["_routing"] = {
            "engine": engine.value,
            "complexity_score": routing_decision.complexity_score,
            "estimated_tokens": routing_decision.estimated_tokens,
            "reasoning": routing_decision.reasoning,
            "fallback": routing_decision.fallback.value if routing_decision.fallback else None,
        }

        logger.info(
            f"[ChiefOfStaff] 路由决策: 引擎={engine.value} | "
            f"复杂度={routing_decision.complexity_score} | "
            f"Agents={routed}"
        )

        # ── Step 2: LOCAL引擎 → 本地执行（零Token）──────────────────────────────
        if engine.value == "local":
            logger.info("[ChiefOfStaff] → 本地执行引擎（零Token消耗）")
            local_result = self.executor.execute(task, context)
            return {
                "chief": f"{self.emoji} {self.name}",
                "input": task,
                "routing": {
                    "engine": "local",
                    "complexity_score": routing_decision.complexity_score,
                    "estimated_tokens": 0,
                    "reasoning": routing_decision.reasoning,
                    "fallback": None,
                },
                "routed_agents": [],
                "agent_count": 0,
                "strategy": "local",
                "results": {"local": {
                    "success": local_result.success,
                    "data": local_result.data,
                    "message": local_result.message,
                    "error": local_result.error,
                }},
                "total_tokens": 0,
                "timestamp": datetime.now().isoformat(),
            }

        # ── Step 3: SMALL/LARGE引擎 → Agent并行执行 ───────────────────────────
        async def run_one(aid: str) -> tuple[str, dict[str, Any]]:
            if aid not in AGENTS:
                logger.warning(f"[ChiefOfStaff] Agent不存在: {aid}")
                return aid, {"error": f"Agent '{aid}' not found in registry"}
            try:
                return aid, await AGENTS[aid].execute(task, context)
            except Exception as exc:  # pragma: no cover
                logger.error(f"[ChiefOfStaff] Agent执行失败 {aid}: {exc}")
                return aid, {"error": str(exc)}

        results_list = await asyncio.gather(
            *[run_one(a) for a in routed], return_exceptions=True
        )

        results: dict[str, Any] = {}
        for item in results_list:
            if isinstance(item, Exception):
                continue
            aid, res = item
            results[aid] = res if isinstance(res, dict) and "error" not in res else {"error": str(res)}

        total_tokens = sum(r.get("tokens", 0) for r in results.values())

        return {
            "chief": f"{self.emoji} {self.name}",
            "input": task,
            "routing": {
                "engine": engine.value,
                "complexity_score": routing_decision.complexity_score,
                "estimated_tokens": routing_decision.estimated_tokens,
                "reasoning": routing_decision.reasoning,
                "fallback": routing_decision.fallback.value if routing_decision.fallback else None,
            },
            "routed_agents": routed,
            "agent_count": len(routed),
            "strategy": "parallel" if len(routed) > 1 else "single",
            "results": results,
            "total_tokens": total_tokens,
            "timestamp": datetime.now().isoformat(),
        }

    # ─── 新增：直接查询路由决策（不执行） ─────────────────────────────────────
    def plan(self, task: str) -> dict[str, Any]:
        """
        仅做路由规划，不执行（用于预览Token消耗和执行策略）

        Returns:
            {
                "routing": { engine, complexity_score, estimated_tokens, reasoning },
                "candidate_agents": [...],
                "workflow_candidates": [...],
            }
        """
        routed = self.route(task)
        decision = self.router.route(task, routed)

        # 工作流候选
        workflow_candidates = []
        from workflows import PRESET_WORKFLOWS
        for wf_id, wf in PRESET_WORKFLOWS.items():
            if any(step.agent_id in routed for step in wf.steps):
                workflow_candidates.append({
                    "id": wf_id,
                    "name": wf.name,
                    "emoji": wf.emoji,
                    "steps_count": len(wf.steps),
                    "estimated_seconds": wf.estimated_total_seconds,
                })

        return {
            "routing": {
                "engine": decision.engine.value,
                "complexity_score": decision.complexity_score,
                "estimated_tokens": decision.estimated_tokens,
                "reasoning": decision.reasoning,
                "fallback": decision.fallback.value if decision.fallback else None,
            },
            "candidate_agents": routed,
            "workflow_candidates": workflow_candidates,
        }


CHIEF = ChiefOfStaff()
