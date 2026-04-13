"""
端云智能路由 - TaskRouter
基于任务复杂度自动选择执行引擎：
  LOCAL   → 本地Python（零Token消耗）
  SMALL   → 小模型（如Qwen-7B）
  LARGE   → 大模型（如GPT-4）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("amazon_ops")


# ─── 引擎枚举 ─────────────────────────────────────────────────────────────────
class Engine(Enum):
    """执行引擎级别"""
    LOCAL = "local"          # 本地Python执行，零Token
    SMALL = "small_model"    # 小参数模型（Qwen-7B等）
    LARGE = "large_model"    # 大参数模型（GPT-4等）


@dataclass
class RoutingDecision:
    """路由决策结果"""
    engine: Engine
    agent_ids: list[str]           # 目标Agent列表
    complexity_score: int           # 0-100，复杂度分
    reasoning: str                 # 决策依据
    estimated_tokens: int          # 预估Token消耗
    fallback: Engine | None = None # 降级方案


# ─── 复杂度指标 ────────────────────────────────────────────────────────────────
# 高Token关键词（触发大模型）
HIGH_COMPLEXITY_PATTERNS = [
    r"策略", r"策划", r"分析报告", r"制定方案", r"全面分析",
    r"竞品调研", r"市场机会", r"增长策略", r"品牌战略",
    r"创意", r"文案撰写", r"深度优化", r"完整方案",
    r"如何", r"怎么", r"建议", r"规划", r"预测",
    r"竞争对手", r"机会点", r"风险评估", r"年度",
]

# 中等复杂度关键词（触发小模型）
MEDIUM_COMPLEXITY_PATTERNS = [
    r"数据", r"报表", r"统计", r"分析", r"计算",
    r"查询", r"查看", r"获取", r"监控", r"预警",
    r"报告", r"概览", r"健康", r"绩效", r"成本",
    r"趋势", r"对比", r"罗列", r"整理", r"汇总",
    r"销量", r"库存", r"利润", r"广告", r"评论",
]

# 本地执行关键词（纯Python）
LOCAL_PATTERNS = [
    # 数据提取与格式转换
    r"提取", r"导出", r"转\w*格式", r"csv", r"json",
    r"排序", r"筛选", r"过滤", r"去重",
    # 规则匹配
    r"匹配", r"查找", r"搜索", r"统计",
    # 简单计算
    r"计算", r"求和", r"平均", r"占比",
    # 格式化输出
    r"格式化", r"表格", r"列表",
    # 通知与提醒
    r"提醒", r"通知", r"预警", r"告警",
]

# 强制本地任务类型
FORCE_LOCAL_PATTERNS = [
    r"^无", r"不需要", r"跳过", r"直接返回",
    r"提取.*数据", r"导出.*报表", r"格式转换",
]


# ─── Agent→Engine默认映射 ─────────────────────────────────────────────────────
AGENT_ENGINE_MAP: dict[str, Engine] = {
    # 选品分析 → 大模型（需创意判断）
    "product_research": Engine.LARGE,
    "niche_finder":      Engine.LARGE,
    # Listing优化 → 中等（涉及文案生成）
    "listing_optimizer": Engine.SMALL,
    "keyword_research":  Engine.SMALL,
    "acontent":          Engine.LARGE,
    # 广告投放 → 大模型（策略决策）
    "ppc_manager":       Engine.SMALL,
    "sponsored_ads":     Engine.LARGE,
    # 库存/定价 → 小模型（规则驱动）
    "inventory_planner": Engine.SMALL,
    "fba_manager":       Engine.SMALL,
    "price_optimizer":   Engine.SMALL,
    "repricing":         Engine.SMALL,
    # 评论/品牌 → 小模型
    "review_monitor":    Engine.SMALL,
    "vine_program":      Engine.SMALL,
    "brand_registry":    Engine.SMALL,
    "hijacker":          Engine.SMALL,
    # 数据分析 → 小模型
    "sales_analytics":  Engine.SMALL,
    "profit_calculator": Engine.LOCAL,
    # 客户服务 → 小模型
    "customer_service":  Engine.SMALL,
    # 合规/账号 → 大模型（涉及政策判断）
    "compliance_checker": Engine.LARGE,
    "account_health":    Engine.SMALL,
    # GUI Agent → 大模型（复杂操作序列）
    "gui_agent":         Engine.LARGE,
}


# ─── TaskRouter ────────────────────────────────────────────────────────────────
class TaskRouter:
    """
    智能任务路由器

    工作流程：
    1. 复杂度评分（模式匹配 + 任务类型判断）
    2. 引擎选择（LOCAL → SMALL → LARGE）
    3. Agent路由（复用ChiefOfStaff关键词匹配）
    4. 输出RoutingDecision
    """

    def __init__(self) -> None:
        self.name = "TaskRouter"
        self.logger = logging.getLogger("amazon_ops.router")

    def _score_task(self, task: str) -> tuple[int, str]:
        """
        评估任务复杂度，返回 (score, reasoning)
        score: 0-100，越高越复杂
        """
        task_lower = task.lower()
        reasons: list[str] = []

        # 基础分数（任务长度反映复杂度）
        length_score = min(len(task) // 5, 20)
        reasons.append(f"任务长度+{length_score}")

        # 高复杂度匹配
        high_hits = sum(
            1 for p in HIGH_COMPLEXITY_PATTERNS
            if re.search(p, task_lower)
        )
        high_score = min(high_hits * 15, 60)
        if high_hits:
            reasons.append(f"高复杂度命中+{high_score}({high_hits}个)")

        # 中等复杂度匹配
        medium_hits = sum(
            1 for p in MEDIUM_COMPLEXITY_PATTERNS
            if re.search(p, task_lower)
        )
        medium_score = min(medium_hits * 8, 40)
        if medium_hits:
            reasons.append(f"中复杂度命中+{medium_score}({medium_hits}个)")

        # 本地执行匹配
        local_hits = sum(
            1 for p in LOCAL_PATTERNS
            if re.search(p, task_lower)
        )
        local_score = min(local_hits * 10, 30)
        if local_hits:
            reasons.append(f"本地候选+{local_score}({local_hits}个)")

        # 强制本地模式
        for p in FORCE_LOCAL_PATTERNS:
            if re.search(p, task_lower):
                reasons.append("强制本地模式")
                return 5, "; ".join(reasons)

        total = min(length_score + high_score + medium_score, 100)
        return total, "; ".join(reasons)

    def _is_local_task(self, task: str) -> bool:
        """判断是否可本地执行"""
        local_hits = sum(
            1 for p in LOCAL_PATTERNS
            if re.search(p, task.lower())
        )
        # 强制本地关键词 + 无高复杂度词 → 本地执行
        force_local = any(
            re.search(p, task.lower()) for p in FORCE_LOCAL_PATTERNS
        )
        high_complexity = any(
            re.search(p, task.lower()) for p in HIGH_COMPLEXITY_PATTERNS
        )
        return force_local or (local_hits >= 2 and not high_complexity)

    def _estimate_tokens(self, task: str, engine: Engine) -> int:
        """预估Token消耗"""
        if engine == Engine.LOCAL:
            return 0
        elif engine == Engine.SMALL:
            return 100
        else:
            # LARGE: 基于任务长度估算
            return min(len(task) // 4 + 150, 800)

    def route(self, task: str, candidate_agents: list[str]) -> RoutingDecision:
        """
        核心路由决策

        Args:
            task: 自然语言任务描述
            candidate_agents: ChiefOfStaff已匹配的Agent列表

        Returns:
            RoutingDecision 包含引擎选择、复杂度评分、预估Token
        """
        score, reasoning = self._score_task(task)

        # 引擎决策
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

        # 覆盖：Agent级别决定（比分数更可靠）
        for agent_id in candidate_agents:
            if agent_id in AGENT_ENGINE_MAP:
                mapped = AGENT_ENGINE_MAP[agent_id]
                if mapped.value > engine.value:
                    engine = mapped
                    reasoning += f" [Agent覆盖:{agent_id}→{engine.value}]"
                    break

        estimated_tokens = self._estimate_tokens(task, engine)

        # 降级方案
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

        self.logger.info(
            f"[TaskRouter] 分={score} | 引擎={engine.value} | "
            f"Token={estimated_tokens} | Agents={candidate_agents} | "
            f"任务: {task[:40]}"
        )
        return decision

    def get_engine_for_agent(self, agent_id: str) -> Engine:
        """查询单个Agent的默认引擎"""
        return AGENT_ENGINE_MAP.get(agent_id, Engine.SMALL)


# 全局单例
ROUTER = TaskRouter()
