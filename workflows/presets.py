"""
Amazon Ops - 预置工作流（Preset Workflows）
一键启动端到端业务流程
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum

logger = logging.getLogger("amazon_ops.workflows")

# ─── 工作流状态 ────────────────────────────────────────────────────────────────
class WorkflowStatus(Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"


# ─── 工作流步骤定义 ────────────────────────────────────────────────────────────
@dataclass
class WorkflowStep:
    """工作流步骤（v2.3 复核沙箱扩展）"""
    name: str
    agent_id: str
    description: str
    input_key: str          # 从context中读取的输入key
    output_key: str         # 写入context的输出key
    estimated_seconds: int = 5
    optional: bool = False
    # ── v2.3 复核沙箱层 ─────────────────────────────────────────────────────
    review: bool = False                # 该步骤产物需要人工复核后才放行采纳
    review_reason: str = ""             # 复核原因（why 需要人看）
    risk: str = "low"                   # low | medium | high
    expected_keys: list[str] = field(default_factory=list)  # 产物应含的键（缺失→提示性校验，不中断）


@dataclass
class PresetWorkflow:
    """预置工作流定义"""
    id: str
    name: str
    emoji: str
    description: str
    steps: list[WorkflowStep]
    estimated_total_seconds: int = 0

    def __post_init__(self):
        self.estimated_total_seconds = sum(
            s.estimated_seconds for s in self.steps
        )


# ─── 预置工作流定义 ────────────────────────────────────────────────────────────

WORKFLOW_NEW_PRODUCT_LAUNCH = PresetWorkflow(
    id="new_product_launch",
    name="新品上架工作流",
    emoji="🆕",
    description="从市场调研到Listing创建的全链路，包含SEO优化和图片生成",
    steps=[
        WorkflowStep(
            name="市场调研",
            agent_id="product_research",
            description="分析市场趋势、竞品格局、机会评分",
            input_key="product_name",
            output_key="research_result",
            estimated_seconds=15,
        ),
        WorkflowStep(
            name="关键词挖掘",
            agent_id="keyword_research",
            description="挖掘高搜索量低竞争关键词",
            input_key="product_name",
            output_key="keywords",
            estimated_seconds=10,
        ),
        WorkflowStep(
            name="Listing优化",
            agent_id="listing_optimizer",
            description="生成标题、五点描述、SearchTerms",
            input_key="research_result + keywords",
            output_key="listing_content",
            estimated_seconds=20,
            review=True,
            review_reason="对外 Listing 文案（标题/五点），上架前需人工复核措辞与合规",
            risk="high",
            expected_keys=["optimized_title", "bullet_points"],
        ),
        WorkflowStep(
            name="A+内容生成",
            agent_id="acontent",
            description="生成品牌故事、产品图表、A+页面",
            input_key="listing_content",
            output_key="acontent_content",
            estimated_seconds=15,
            optional=True,
        ),
    ],
)

WORKFLOW_AD_OPTIMIZATION = PresetWorkflow(
    id="ad_optimization",
    name="广告优化工作流",
    emoji="📈",
    description="从广告数据分析到策略制定的完整优化流程",
    steps=[
        WorkflowStep(
            name="广告数据分析",
            agent_id="ppc_manager",
            description="分析ACOS/CPC/CTR等核心指标",
            input_key="ad_campaign_id",
            output_key="ad_analysis",
            estimated_seconds=10,
        ),
        WorkflowStep(
            name="竞品广告研究",
            agent_id="sponsored_ads",
            description="研究竞品投放策略和关键词",
            input_key="product_asin",
            output_key="competitor_ads",
            estimated_seconds=12,
        ),
        WorkflowStep(
            name="制定优化策略",
            agent_id="ppc_manager",
            description="生成竞价调整、预算分配、否定关键词建议",
            input_key="ad_analysis + competitor_ads",
            output_key="optimization_plan",
            estimated_seconds=15,
            review=True,
            review_reason="涉及竞价/预算调整建议（花钱动作），执行前需人工复核",
            risk="high",
            expected_keys=["optimization_plan"],
        ),
        WorkflowStep(
            name="ROI预测",
            agent_id="profit_calculator",
            description="预估优化后的投资回报率",
            input_key="optimization_plan",
            output_key="roi_forecast",
            estimated_seconds=8,
        ),
    ],
)

WORKFLOW_INVENTORY_ALERT = PresetWorkflow(
    id="inventory_alert",
    name="库存预警工作流",
    emoji="📦",
    description="从FBA库存监控到补货计划的全链路预警",
    steps=[
        WorkflowStep(
            name="FBA库存检查",
            agent_id="fba_manager",
            description="查询各SKU当前库存和FBA费用",
            input_key="sku_list",
            output_key="inventory_status",
            estimated_seconds=8,
        ),
        WorkflowStep(
            name="销售预测",
            agent_id="inventory_planner",
            description="基于历史销量预测未来需求",
            input_key="inventory_status + sales_history",
            output_key="sales_forecast",
            estimated_seconds=12,
        ),
        WorkflowStep(
            name="补货计划生成",
            agent_id="inventory_planner",
            description="计算最优补货量和时间",
            input_key="sales_forecast + current_inventory",
            output_key="replenishment_plan",
            estimated_seconds=10,
            review=True,
            review_reason="补货涉及采购资金占用，下单前需人工复核数量与节奏",
            risk="medium",
        ),
        WorkflowStep(
            name="供应链评估",
            agent_id="supply_chain",
            description="评估供应商交期和物流时效",
            input_key="replenishment_plan",
            output_key="supply_chain_result",
            estimated_seconds=8,
        ),
        WorkflowStep(
            name="库存预警报告",
            agent_id="inventory_planner",
            description="汇总预警清单（断货/滞销/积压）",
            input_key="all_previous_results",
            output_key="alert_report",
            estimated_seconds=5,
        ),
    ],
)

WORKFLOW_CUSTOMER_SERVICE = PresetWorkflow(
    id="customer_service",
    name="客户服务流程",
    emoji="💬",
    description="从买家消息处理到回复生成的全链路客服",
    steps=[
        WorkflowStep(
            name="消息分类",
            agent_id="customer_service",
            description="识别消息类型（退货/咨询/投诉）",
            input_key="buyer_message",
            output_key="message_classification",
            estimated_seconds=3,
        ),
        WorkflowStep(
            name="知识库检索",
            agent_id="qa_agent",
            description="从FAQ和历史工单中检索答案",
            input_key="message_classification",
            output_key="kb_answers",
            estimated_seconds=5,
        ),
        WorkflowStep(
            name="生成回复",
            agent_id="customer_service",
            description="生成符合亚马逊政策的专业回复",
            input_key="buyer_message + kb_answers",
            output_key="draft_reply",
            estimated_seconds=8,
            review=True,
            review_reason="将发送给买家的回复文案，发出前需人工复核语气与合规",
            risk="high",
        ),
        WorkflowStep(
            name="风险审核",
            agent_id="compliance_checker",
            description="审核回复内容是否合规",
            input_key="draft_reply",
            output_key="compliance_check",
            estimated_seconds=5,
        ),
    ],
)

# ─── 工作流注册表 ──────────────────────────────────────────────────────────────
PRESET_WORKFLOWS: dict[str, PresetWorkflow] = {
    wf.id: wf
    for wf in [
        WORKFLOW_NEW_PRODUCT_LAUNCH,
        WORKFLOW_AD_OPTIMIZATION,
        WORKFLOW_INVENTORY_ALERT,
        WORKFLOW_CUSTOMER_SERVICE,
    ]
}


# ─── WorkflowEngine ─────────────────────────────────────────────────────────────
@dataclass
class WorkflowExecutionResult:
    """工作流执行结果（v2.3 含复核沙箱 reviews）"""
    workflow_id: str
    status: WorkflowStatus
    step_results: dict[str, Any] = field(default_factory=dict)
    total_seconds: float = 0.0
    error: str | None = None
    started_at: str = ""
    completed_at: str = ""
    estimated_vs_actual: dict[str, int] = field(default_factory=dict)
    # ── v2.3：步骤复核沙箱（output_key → review 信息）────────────────────────
    reviews: dict[str, dict[str, Any]] = field(default_factory=dict)


class WorkflowEngine:
    """
    预置工作流执行引擎

    支持：
    - 一键启动预定义工作流
    - 并行/串行步骤执行
    - 步骤结果自动聚合
    - 执行进度跟踪
    """

    def __init__(self) -> None:
        self.name = "WorkflowEngine"

    async def launch(
        self,
        workflow_id: str,
        context: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """
        启动预置工作流

        Args:
            workflow_id: 工作流ID（如 "new_product_launch"）
            context: 初始输入参数
                     示例：{"product_name": "蓝牙耳机"}

        Returns:
            WorkflowExecutionResult: 包含所有步骤结果
        """
        import time
        start_time = time.time()

        if workflow_id not in PRESET_WORKFLOWS:
            return WorkflowExecutionResult(
                workflow_id=workflow_id,
                status=WorkflowStatus.FAILED,
                error=f"未知工作流: {workflow_id}",
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                total_seconds=0.0,
            )

        workflow = PRESET_WORKFLOWS[workflow_id]
        step_results: dict[str, Any] = {}
        estimated_vs_actual: dict[str, int] = {}
        reviews: dict[str, dict[str, Any]] = {}
        step_start = time.time()

        logger.info(
            f"[WorkflowEngine] ▶ 启动工作流 {workflow.emoji} {workflow.name} "
            f"({len(workflow.steps)}个步骤)"
        )

        # 依次执行每个步骤（串行，数据依赖）
        for step in workflow.steps:
            step_name = f"[{step.agent_id}] {step.name}"
            logger.info(f"[WorkflowEngine]   → 步骤: {step_name}")
            step_start = time.time()

            try:
                # 获取当前步骤的输入
                # 简单实现：从context和已有step_results中拼接
                step_input = self._resolve_step_input(step, context, step_results)

                # 执行Agent（模拟，实际需引入AGENTS）
                result = await self._execute_step(step, step_input)
                step_results[step.output_key] = result
                elapsed = int(time.time() - step_start)
                estimated_vs_actual[step.name] = elapsed

                # ── v2.3 复核沙箱层：每步输出校验 + 复核标记 ────────────────
                reviews[step.output_key] = self._sandbox_step(step, result)
                rinfo = reviews[step.output_key]
                logger.info(
                    f"[WorkflowEngine]   🛡 {step_name} "
                    f"review={step.review} validated={rinfo['validated']} "
                    f"missing={rinfo['missing']}"
                )

                logger.info(
                    f"[WorkflowEngine]   ✓ {step_name} "
                    f"(实际{elapsed}s / 预估{step.estimated_seconds}s)"
                )
            except Exception as exc:
                elapsed = int(time.time() - step_start)
                logger.error(f"[WorkflowEngine]   ✗ {step_name}: {exc}")
                if not step.optional:
                    return WorkflowExecutionResult(
                        workflow_id=workflow_id,
                        status=WorkflowStatus.FAILED,
                        step_results=step_results,
                        error=f"步骤失败: {step.name} → {exc}",
                        started_at=datetime.now().isoformat(),
                        completed_at=datetime.now().isoformat(),
                        total_seconds=time.time() - start_time,
                        estimated_vs_actual=estimated_vs_actual,
                    )
                # 可选步骤失败不影响整体
                step_results[step.output_key] = {"error": str(exc)}

        total_seconds = time.time() - start_time

        result = WorkflowExecutionResult(
            workflow_id=workflow_id,
            status=WorkflowStatus.DONE,
            step_results=step_results,
            total_seconds=total_seconds,
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            estimated_vs_actual=estimated_vs_actual,
            reviews=reviews,
        )

        logger.info(
            f"[WorkflowEngine] ✓ 完成 {workflow.emoji} {workflow.name} "
            f"总耗时 {total_seconds:.1f}s"
        )
        return result

    def _resolve_step_input(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
        results: dict[str, Any],
    ) -> dict[str, Any]:
        """解析步骤输入参数（修复：非 dict 值包装 + Agent 信封解包）"""
        if step.input_key.startswith("all_previous_results"):
            return results
        if step.input_key in context:
            return context[step.input_key]
        if "+" in step.input_key:
            parts = [p.strip() for p in step.input_key.split("+")]
            merged: dict[str, Any] = {}
            for part in parts:
                val: Any = None
                if part in context:
                    val = context[part]
                elif part in results:
                    val = results[part]
                    # 解包 Agent 信封：只取业务 result，忽略 agent/tokens/kpis 元数据
                    if isinstance(val, dict) and isinstance(val.get("result"), dict):
                        val = val["result"]
                if isinstance(val, dict):
                    merged.update(val)
                elif val is not None:
                    # 非 dict（list/str/数值）按键名包装，避免 update() 崩溃
                    merged[part] = val
            return merged
        return context.get(step.input_key, {})

    async def _execute_step(
        self,
        step: WorkflowStep,
        step_input: Any,
    ) -> dict[str, Any]:
        """执行单个工作流步骤（调用对应Agent）"""
        # 动态导入避免循环
        from agents.base import AGENTS

        if step.agent_id not in AGENTS:
            return {"error": f"Agent不存在: {step.agent_id}"}

        agent = AGENTS[step.agent_id]
        # Agent.execute 返回 dict结果
        result = await agent.execute(
            task=str(step_input)[:500],
            context={"workflow_input": step_input},
        )
        return result

    # ── v2.3 复核沙箱层 ──────────────────────────────────────────────────────
    @staticmethod
    def _unwrap_payload(result: Any) -> Any:
        """解包 Agent 信封（{agent,tokens,result,kpis,...}）取业务产物"""
        if isinstance(result, dict) and isinstance(result.get("result"), dict):
            return result["result"]
        if isinstance(result, dict) and "error" in result:
            return None
        return result

    def _sandbox_step(
        self,
        step: WorkflowStep,
        result: Any,
    ) -> dict[str, Any]:
        """
        步骤"沙箱"：对单步产物做隔离校验与复核登记（不跨步污染）。

        - 输出校验：产物应含 expected_keys（缺失 → validated=False，提示性，不中断流程）
        - 复核登记：review=True 的步骤标记为待人工复核（approve/reject 由 ReviewGate 处理）
        """
        payload = self._unwrap_payload(result)
        missing: list[str] = []
        if isinstance(payload, dict) and step.expected_keys:
            missing = [k for k in step.expected_keys if k not in payload]
        info: dict[str, Any] = {
            "step": step.name,
            "agent_id": step.agent_id,
            "review_required": step.review,
            "risk": step.risk,
            "reason": step.review_reason,
            "decision": "pending" if step.review else "auto",
            "validated": not missing,
            "missing": missing,
        }
        if step.review:
            # 给复核人产物预览（截断，不含完整数据）
            try:
                import json as _json
                preview = _json.dumps(payload, ensure_ascii=False)[:400] if payload is not None else ""
                info["preview"] = preview
            except Exception:  # noqa: BLE001
                info["preview"] = str(payload)[:200]
        return info

    def list_workflows(self) -> list[dict[str, Any]]:
        """列出所有预置工作流（v2.3 含复核标记）"""
        return [
            {
                "id": wf.id,
                "name": wf.name,
                "emoji": wf.emoji,
                "description": wf.description,
                "steps_count": len(wf.steps),
                "estimated_seconds": wf.estimated_total_seconds,
                "steps": [
                    {
                        "name": s.name,
                        "agent_id": s.agent_id,
                        "estimated_seconds": s.estimated_seconds,
                        "review": s.review,
                        "risk": s.risk,
                        "review_reason": s.review_reason,
                    }
                    for s in wf.steps
                ],
            }
            for wf in PRESET_WORKFLOWS.values()
        ]


# 全局单例
WORKFLOW_ENGINE = WorkflowEngine()
