"""
Amazon Operations Silicon Army - Agent Base & Routing
"""

import logging
from datetime import datetime
from typing import Any, TypeVar

logger = logging.getLogger("amazon_ops")

# ─── 关键词路由表（20个Agent × 关键词） ──────────────────────────────────────
TASK_ROUTING: dict[str, list[str]] = {
    "product_research":    ["选品","市场","竞品","蓝海","能不能做","产品分析"," niches"],
    "niche_finder":        ["细分","利基","长尾","小类","细分市场","小类目"," niche"],
    "listing_optimizer":   ["listing","标题","五点","要点","描述","优化"," listing"],
    "keyword_research":     ["关键词","搜索词","searchterm","反查","搜索量","热词","cerebro"],
    "acontent":             ["a+","acontent","品牌故事","图文","图片","增强内容"," a content"],
    "ppc_manager":         ["广告","ppc","acos","cpc","竞价","campaign","投放"," sponsored"],
    "sponsored_ads":       ["sp广告","sb广告","sd广告","投放组合","预算分配","广告策略"],
    "inventory_planner":   ["库存","补货","断货","备货","安全库存","预测"," reorder"],
    "fba_manager":         ["fba","仓储","货件","ipi","入库","fba费用","仓储费"],
    "price_optimizer":      ["定价","价格","竞品价格","调价","利润","边际利润"," pricing"],
    "repricing":           ["自动调价","repric","buybox","守价","调价策略","自动降价"],
    "review_monitor":      ["评论","差评","星级","review","好评","1星","2星"," star"],
    "vine_program":        ["vine","绿标","v绿","早期评论","vine计划","early review"],
    "brand_registry":      ["品牌","商标","侵权","投诉","品牌注册","tm标"," brand"],
    "hijacker":            ["跟卖","被跟卖","hijacker","抢夺","跟卖者"," hijack"],
    "sales_analytics":     ["销售","报表","业绩","数据","今日","本周","本月","趋势"," revenue"],
    "profit_calculator":   ["利润","成本","roi","毛利率","核算","盈利"," profit"],
    "customer_service":    ["客服","买家消息","退货","回复","售后","问询"," cs message"],
    "compliance_checker":  ["合规","政策","审核","类目","认证","法规"," regulation"],
    "account_health":      ["账号","odr","健康度","绩效","预警","账户","违规"," account health"],
    "competitor_analysis": ["竞品","竞争对手","best seller","bsr","同行","竞品分析","价格追踪","竞争对手分析"," competitor"],
}

AGENT_REGISTRY: dict[str, dict[str, Any]] = {}
AGENT_CALL_LOG: list[dict[str, Any]] = []
AGENTS: dict[str, "AmazonAgent"] = {}

T = TypeVar("T")


def log_call(agent_id: str, task: str, tokens: int) -> None:
    """记录Agent调用（用于统计和分析）"""
    if agent_id in AGENT_REGISTRY:
        AGENT_REGISTRY[agent_id]["invoked_count"] += 1
        AGENT_REGISTRY[agent_id]["total_tokens"] += tokens
    AGENT_CALL_LOG.append({
        "agent": agent_id, "task": task[:80],
        "tokens": tokens, "time": datetime.now().isoformat(),
    })


# ─── Agent基类 ───────────────────────────────────────────────────────────────
class AmazonAgent:
    """
    所有Amazon运营Agent的基类

    设计原则:
    - 统一接口：execute(task, context) → dict
    - 自动日志记录和Token计数
    - 子类只需实现 _run() 方法
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        emoji: str,
        description: str,
        capabilities: list[str],
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.emoji = emoji
        self.description = description
        self.capabilities = capabilities

        AGENT_REGISTRY[agent_id] = {
            "id": agent_id, "name": name, "emoji": emoji,
            "description": description, "capabilities": capabilities,
            "invoked_count": 0, "total_tokens": 0,
        }
        AGENTS[agent_id] = self
        logger.debug(f"[Agent] 注册 {emoji} {name} ({agent_id})")

    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        """统一入口：日志 → _run → 元数据附加"""
        log_call(self.agent_id, task, 150)
        try:
            result = await self._run(task, context)
        except Exception as exc:  # pragma: no cover
            logger.error(f"[Agent.{self.agent_id}] 异常: {exc}")
            result = {"error": str(exc)}
        result["agent"] = f"{self.emoji} {self.name}"
        result["tokens"] = 150
        return result

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.agent_id}._run() 必须被子类实现")
