"""
Workflow Engine - LangGraph风格工作流引擎
用有向图建模亚马逊运营工作流
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("amazon_ops")


# ─── 节点状态 ──────────────────────────────────────────────────────────────────
class NodeState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


# ─── 工作流节点 ────────────────────────────────────────────────────────────────
@dataclass
class WorkflowNode:
    id: str
    name: str
    agent_id: str              # 对应哪个Agent
    input_mapping: dict[str, str] = field(default_factory=dict)  # var_name → source_node_id.output_key
    condition: Optional[Callable[[dict], bool]] = None  # 条件判断
    retry: int = 2             # 重试次数
    timeout_seconds: float = 30.0


@dataclass
class WorkflowEdge:
    from_node: str
    to_node: str
    condition: Optional[str] = None  # "success" | "failure" | "*"


# ─── 工作流定义 ────────────────────────────────────────────────────────────────
@dataclass
class Workflow:
    id: str
    name: str
    description: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    context_schema: dict[str, Any] = field(default_factory=dict)


# ─── 内置亚马逊工作流 ──────────────────────────────────────────────────────────
AMAZON_WORKFLOWS: dict[str, Workflow] = {}


def _build_workflows() -> None:
    """构建预置工作流"""

    # ── 工作流1: 新品上架全流程 ──────────────────────────────────────────────
    NEW_PRODUCT_WF = Workflow(
        id="new_product_launch",
        name="新品上架全流程",
        description="从选品分析到Listing上线完整流程",
        nodes=[
            WorkflowNode(
                id="research",
                name="选品分析",
                agent_id="product_research",
                input_mapping={"task": "context.product_idea"},
            ),
            WorkflowNode(
                id="niche",
                name="细分市场分析",
                agent_id="niche_finder",
                input_mapping={"task": "context.product_idea"},
            ),
            WorkflowNode(
                id="listing",
                name="Listing优化",
                agent_id="listing_optimizer",
                input_mapping={"task": "context.product_info"},
            ),
            WorkflowNode(
                id="keywords",
                name="关键词研究",
                agent_id="keyword_research",
                input_mapping={"task": "context.product_info"},
            ),
            WorkflowNode(
                id="content",
                name="A+内容生成",
                agent_id="acontent",
                input_mapping={"task": "context.product_info"},
            ),
            WorkflowNode(
                id="pricing",
                name="定价策略",
                agent_id="price_optimizer",
                input_mapping={"task": "context.product_info"},
            ),
            WorkflowNode(
                id="compliance",
                name="合规检查",
                agent_id="compliance_checker",
                input_mapping={"task": "context.product_info"},
            ),
        ],
        edges=[
            WorkflowEdge("research", "niche", "success"),
            WorkflowEdge("research", "compliance", "failure"),
            WorkflowEdge("niche", "listing", "success"),
            WorkflowEdge("listing", "keywords", "success"),
            WorkflowEdge("keywords", "content", "success"),
            WorkflowEdge("content", "pricing", "success"),
            WorkflowEdge("pricing", "compliance", "success"),
        ],
    )

    # ── 工作流2: 广告优化全流程 ──────────────────────────────────────────────
    AD_OPTIMIZE_WF = Workflow(
        id="ad_optimization",
        name="广告优化全流程",
        description="从数据分析到竞价优化的完整广告运营流程",
        nodes=[
            WorkflowNode("analytics", "销售数据分析", "sales_analytics"),
            WorkflowNode("ppc", "PPC广告管理", "ppc_manager"),
            WorkflowNode("strategy", "广告策略", "sponsored_ads"),
            WorkflowNode("inventory", "库存规划", "inventory_planner"),
            WorkflowNode("profit", "利润分析", "profit_calculator"),
        ],
        edges=[
            WorkflowEdge("analytics", "ppc", "success"),
            WorkflowEdge("analytics", "inventory", "success"),
            WorkflowEdge("ppc", "strategy", "success"),
            WorkflowEdge("strategy", "profit", "success"),
        ],
    )

    # ── 工作流3: 差评危机处理 ────────────────────────────────────────────────
    REVIEW_CRISIS_WF = Workflow(
        id="review_crisis",
        name="差评危机处理流程",
        description="从差评检测到危机公关的完整流程",
        nodes=[
            WorkflowNode("monitor", "评论监控", "review_monitor"),
            WorkflowNode("customer", "客户服务", "customer_service"),
            WorkflowNode("brand", "品牌保护", "brand_registry"),
            WorkflowNode("account", "账号健康", "account_health"),
        ],
        edges=[
            WorkflowEdge("monitor", "customer", "success"),
            WorkflowEdge("customer", "account", "success"),
            WorkflowEdge("customer", "brand", "failure"),
            WorkflowEdge("brand", "account", "success"),
        ],
    )

    # ── 工作流4: 选品+Listing+广告一体化（LangGraph DAG）──────────────────
    LAUNCH_WF = Workflow(
        id="product_launch",
        name="新品Launch一体化",
        description="选品→Listing→定价→广告→库存五步自动串联",
        nodes=[
            WorkflowNode("research", "选品分析", "product_research"),
            WorkflowNode("listing", "Listing优化", "listing_optimizer"),
            WorkflowNode("pricing", "定价策略", "price_optimizer"),
            WorkflowNode("ad_plan", "广告规划", "sponsored_ads"),
            WorkflowNode("inventory", "库存规划", "inventory_planner"),
            WorkflowNode("profit", "利润计算", "profit_calculator"),
        ],
        edges=[
            WorkflowEdge("research", "listing", "success"),
            WorkflowEdge("listing", "pricing", "success"),
            WorkflowEdge("pricing", "ad_plan", "success"),
            WorkflowEdge("ad_plan", "inventory", "success"),
            WorkflowEdge("inventory", "profit", "success"),
        ],
    )

    global AMAZON_WORKFLOWS
    AMAZON_WORKFLOWS = {
        "new_product_launch": NEW_PRODUCT_WF,
        "ad_optimization": AD_OPTIMIZE_WF,
        "review_crisis": REVIEW_CRISIS_WF,
        "product_launch": LAUNCH_WF,
    }


_build_workflows()


# ─── Workflow Engine ──────────────────────────────────────────────────────────
class WorkflowEngine:
    """
    LangGraph风格工作流执行引擎

    支持：
    - 有向无环图（DAG）执行
    - 条件分支
    - 节点状态追踪
    - 结果上下文传递
    - 失败重试
    """

    def __init__(self, chief) -> None:
        self.chief = chief  # ChiefOfStaff引用

    async def run(
        self,
        workflow_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """执行预置工作流"""
        if workflow_id not in AMAZON_WORKFLOWS:
            return {"error": f"Unknown workflow: {workflow_id}", "available": list(AMAZON_WORKFLOWS.keys())}

        wf = AMAZON_WORKFLOWS[workflow_id]
        node_states: dict[str, str] = {n.id: NodeState.PENDING.value for n in wf.nodes}
        node_results: dict[str, Any] = {}

        logger.info(f"[WorkflowEngine] 启动工作流: {wf.name} ({workflow_id})")

        # 构建邻接表
        adj: dict[str, list[str]] = {n.id: [] for n in wf.nodes}
        for edge in wf.edges:
            adj[edge.from_node].append(edge.to_node)

        # 拓扑执行（支持分支）
        async def execute_node(node: WorkflowNode) -> tuple[str, NodeState, dict[str, Any]]:
            node_states[node.id] = NodeState.RUNNING.value
            try:
                # 从context或前序节点结果构建输入
                input_data = self._build_node_input(node, context, node_results)
                result = await self.chief.execute(input_data, context)
                node_states[node.id] = NodeState.DONE.value
                node_results[node.id] = result
                return node.id, NodeState.DONE, result
            except Exception as exc:
                logger.error(f"[WorkflowEngine] 节点 {node.id} 失败: {exc}")
                node_states[node.id] = NodeState.FAILED.value
                return node.id, NodeState.FAILED, {"error": str(exc)}

        # 简单BFS执行
        pending = {n.id for n in wf.nodes}
        completed: set[str] = set()

        while pending:
            # 找所有前置已完成的节点
            ready = [
                n for n in wf.nodes
                if n.id in pending
                and all(prev in completed for prev, edges in adj.items() if n.id in edges)
            ]
            if not ready:
                break

            batch_results = await self._run_batch(execute_node, ready)
            for node_id, state, _ in batch_results:
                pending.discard(node_id)
                if state == NodeState.DONE:
                    completed.add(node_id)

        return {
            "workflow_id": workflow_id,
            "workflow_name": wf.name,
            "nodes": node_states,
            "results": {
                nid: {"keys": list(res.keys()) if isinstance(res, dict) else str(res)}
                for nid, res in node_results.items()
            },
            "total_nodes": len(wf.nodes),
            "completed": len(completed),
            "failed": len(wf.nodes) - len(completed),
            "timestamp": datetime.now().isoformat(),
        }

    def _build_node_input(
        self,
        node: WorkflowNode,
        context: dict[str, Any],
        results: dict[str, Any],
    ) -> str:
        """构建节点的输入任务描述"""
        if node.input_mapping:
            task = node.input_mapping.get("task", "")
            if task.startswith("context."):
                key = task.split(".", 1)[1]
                return str(context.get(key, task))
        return node.name

    async def _run_batch(
        self,
        fn: Callable,
        items: list,
    ) -> list:
        import asyncio
        return await asyncio.gather(*[fn(item) for item in items])

    def list_workflows(self) -> list[dict[str, str]]:
        return [
            {"id": wf.id, "name": wf.name, "description": wf.description}
            for wf in AMAZON_WORKFLOWS.values()
        ]


# ─── 工作流 API ────────────────────────────────────────────────────────────────
async def run_workflow(workflow_id: str, context: dict[str, Any], chief) -> dict[str, Any]:
    """API入口"""
    engine = WorkflowEngine(chief)
    return await engine.run(workflow_id, context)
