"""
集成 Tracing 的 TaskRouter
在路由决策前后自动记录 span。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("amazon_ops.router")

# ─── Tracing 工具 ─────────────────────────────────────────────────────────────
_tracing_module: Any = None


def _get_tracing():
    """
    返回 tracing 模块（懒加载，失败静默返回 None）。
    返回 (TraceContext_cls, SpanType_cls, get_current_trace_fn) 或 None。
    """
    global _tracing_module
    if _tracing_module is None:
        try:
            from tracing.trace_context import TraceContext, SpanType, get_current_trace
            _tracing_module = (TraceContext, SpanType, get_current_trace)
        except ImportError:
            _tracing_module = None
    return _tracing_module


# ─── 引擎枚举 ─────────────────────────────────────────────────────────────────
class Engine(Enum):
    LOCAL = "local"
    SMALL = "small_model"
    LARGE = "large_model"


@dataclass
class RoutingDecision:
    engine: Engine
    agent_ids: list[str]
    complexity_score: int
    reasoning: str
    estimated_tokens: int
    fallback: Engine | None = None


# ─── 复杂度指标 ────────────────────────────────────────────────────────────────
HIGH_COMPLEXITY_PATTERNS = [
    r"策略", r"策划", r"分析报告", r"制定方案", r"全面分析",
    r"竞品调研", r"市场机会", r"增长策略", r"品牌战略",
    r"创意", r"文案撰写", r"深度优化", r"完整方案",
    r"如何", r"怎么", r"建议", r"规划", r"预测",
    r"竞争对手", r"机会点", r"风险评估", r"年度",
]

MEDIUM_COMPLEXITY_PATTERNS = [
    r"数据", r"报表", r"统计", r"分析", r"计算",
    r"查询", r"查看", r"获取", r"监控", r"预警",
    r"报告", r"概览", r"健康", r"绩效", r"成本",
    r"趋势", r"对比", r"罗列", r"整理", r"汇总",
    r"销量", r"库存", r"利润", r"广告", r"评论",
]

LOCAL_PATTERNS = [
    r"提取", r"导出", r"转\w*格式", r"csv", r"json",
    r"排序", r"筛选", r"过滤", r"去重",
    r"匹配", r"查找", r"搜索", r"统计",
    r"计算", r"求和", r"平均", r"占比",
    r"格式化", r"表格", r"列表",
    r"提醒", r"通知", r"预警", r"告警",
]

FORCE_LOCAL_PATTERNS = [
    r"^无", r"不需要", r"跳过", r"直接返回",
    r"提取.*数据", r"导出.*报表", r"格式转换",
]


AGENT_ENGINE_MAP: dict[str, Engine] = {
    "product_research": Engine.LARGE,
    "niche_finder":      Engine.LARGE,
    "listing_optimizer": Engine.SMALL,
    "keyword_research":  Engine.SMALL,
    "acontent":          Engine.LARGE,
    "ppc_manager":       Engine.SMALL,
    "sponsored_ads":     Engine.LARGE,
    "inventory_planner": Engine.SMALL,
    "fba_manager":       Engine.SMALL,
    "price_optimizer":   Engine.SMALL,
    "repricing":         Engine.SMALL,
    "review_monitor":    Engine.SMALL,
    "vine_program":      Engine.SMALL,
    "brand_registry":    Engine.SMALL,
    "hijacker":          Engine.SMALL,
    "sales_analytics":  Engine.SMALL,
    "profit_calculator": Engine.LOCAL,
    "customer_service":  Engine.SMALL,
    "compliance_checker": Engine.LARGE,
    "account_health":    Engine.SMALL,
    "gui_agent":         Engine.LARGE,
}


# ─── TaskRouter（集成版）───────────────────────────────────────────────────────
class TaskRouter:
    """
    智能任务路由器（Tracing 集成版）

    每个 route() 调用自动记录一个 span 到当前 TraceContext。
    """

    def __init__(self) -> None:
        self.name = "TaskRouter"
        self.logger = logging.getLogger("amazon_ops.router")

    def _score_task(self, task: str) -> tuple[int, str]:
        task_lower = task.lower()
        reasons: list[str] = []

        length_score = min(len(task) // 5, 20)
        reasons.append(f"任务长度+{length_score}")

        high_hits = sum(1 for p in HIGH_COMPLEXITY_PATTERNS if re.search(p, task_lower))
        high_score = min(high_hits * 15, 60)
        if high_hits:
            reasons.append(f"高复杂度命中+{high_score}({high_hits}个)")

        medium_hits = sum(1 for p in MEDIUM_COMPLEXITY_PATTERNS if re.search(p, task_lower))
        medium_score = min(medium_hits * 8, 40)
        if medium_hits:
            reasons.append(f"中复杂度命中+{medium_score}({medium_hits}个)")

        local_hits = sum(1 for p in LOCAL_PATTERNS if re.search(p, task_lower))
        local_score = min(local_hits * 10, 30)
        if local_hits:
            reasons.append(f"本地候选+{local_score}({local_hits}个)")

        for p in FORCE_LOCAL_PATTERNS:
            if re.search(p, task_lower):
                reasons.append("强制本地模式")
                return 5, "; ".join(reasons)

        total = min(length_score + high_score + medium_score, 100)
        return total, "; ".join(reasons)

    def _is_local_task(self, task: str) -> bool:
        local_hits = sum(1 for p in LOCAL_PATTERNS if re.search(p, task.lower()))
        force_local = any(re.search(p, task.lower()) for p in FORCE_LOCAL_PATTERNS)
        high_complexity = any(re.search(p, task.lower()) for p in HIGH_COMPLEXITY_PATTERNS)
        return force_local or (local_hits >= 2 and not high_complexity)

    def _estimate_tokens(self, task: str, engine: Engine) -> int:
        if engine == Engine.LOCAL:
            return 0
        elif engine == Engine.SMALL:
            return 100
        else:
            return min(len(task) // 4 + 150, 800)

    def route(self, task: str, candidate_agents: list[str]) -> RoutingDecision:
        """
        核心路由决策（自动记录 span）
        """
        tm = _get_tracing()
        span: Any = None

        if tm is not None:
            TraceContext_cls, SpanType_cls, get_current_trace_fn = tm
            ctx = get_current_trace_fn()
            if ctx is not None:
                scope = ctx.span("TaskRouter.route", SpanType_cls.ROUTER,
                                 input_summary=task[:200])
                span = scope._span

        # ── 执行路由决策 ──────────────────────────────────────────────────────
        score, reasoning = self._score_task(task)

        if self._is_local_task(task):
            engine = Engine.LOCAL
            reasoning += " → 本地执行"
        elif score < 30:
            engine = Engine.SMALL
            reasoning += f" → 小模型(分={score})"
        elif score < 60:
            engine = Engine.SMALL
            reasoning += f" → 小模型(分={score})"
        else:
            engine = Engine.LARGE
            reasoning += f" → 大模型(分={score})"

        for agent_id in candidate_agents:
            if agent_id in AGENT_ENGINE_MAP:
                mapped = AGENT_ENGINE_MAP[agent_id]
                if mapped.value > engine.value:
                    engine = mapped
                    reasoning += f" [Agent覆盖:{agent_id}→{engine.value}]"
                    break

        estimated_tokens = self._estimate_tokens(task, engine)

        fallback: Engine | None = None
        if engine == Engine.LARGE:
            fallback = Engine.SMALL
        elif engine == Engine.SMALL:
            fallback = Engine.LOCAL

        decision = RoutingDecision(
            engine=engine,
            agent_ids=candidate_agents,
            complexity_score=score,
            reasoning=reasoning,
            estimated_tokens=estimated_tokens,
            fallback=fallback,
        )

        # ── 记录 span ─────────────────────────────────────────────────────────
        if span is not None:
            span.finish(
                output_summary=f"engine={engine.value} agents={candidate_agents} | {reasoning}",
            )

        self.logger.info(
            f"[TaskRouter] 分={score} | 引擎={engine.value} | "
            f"Token={estimated_tokens} | Agents={candidate_agents} | "
            f"任务: {task[:40]}"
        )
        return decision

    def get_engine_for_agent(self, agent_id: str) -> Engine:
        return AGENT_ENGINE_MAP.get(agent_id, Engine.SMALL)


# 全局单例
ROUTER = TaskRouter()
