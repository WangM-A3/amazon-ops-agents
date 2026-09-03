"""
agents/support_agents.py — 工作流支撑 Agent（supply_chain / qa_agent）
======================================================================
预置工作流引用但此前缺失的两个 Agent：
- supply_chain : 供应链评估（供应商交期 / 物流时效）
- qa_agent     : 知识库检索（FAQ / 历史工单答案）
"""
from __future__ import annotations

from typing import Any

from .base import AmazonAgent

# 内置 FAQ 知识库（真实数据导入后可替换）
_FAQ_KB = [
    {"q": "怎么申请退货", "a": "买家在订单页面申请退货，卖家 48 小时内需响应；FBA 订单由亚马逊自动处理退货授权。"},
    {"q": "发货时效", "a": "FBA 订单由亚马逊履约；FBM 订单建议 48 小时内发货，超过 3 天会被计入迟发率(Late Shipment Rate)。"},
    {"q": "发票", "a": "买家可在订单页面下载电子发票；FBA 订单发票由亚马逊代开，FBM 订单需卖家在后台上传。"},
    {"q": "coupon", "a": "优惠券设置：广告页 → Coupons → 新建；生效需 6 小时，可与 Deals 叠加需注意预算。"},
    {"q": "差评", "a": "合规处理：先排查订单确认问题，通过买家消息沟通；严禁诱导删除差评（违反评论政策）。"},
    {"q": "断货", "a": "断货会降权重；建议补货到 FBA 或转 FBM 保在售；恢复后排名回升需要 1-2 周。"},
]


class SupplyChainAgent(AmazonAgent):
    """供应链评估：供应商交期 / 物流时效 / 断货风险"""

    def __init__(self) -> None:
        super().__init__(
            "supply_chain", "供应链评估Agent", "🚢",
            "供应商交期、物流时效、头程方案、断货风险评估",
            ["供应链", "供应商交期", "物流时效", "头程", "断货风险"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        quotes, src = [], "demo"
        try:
            from data.provider import get_provider
            quotes, src = get_provider().get_supplier_quotes()
        except Exception:  # noqa: BLE001
            pass
        if quotes and src != "demo":
            return {
                "input": task,
                "result": {"data_source": "✅ 真实数据", "supplier_quotes": quotes},
                "kpis": {"suppliers": len(quotes)},
            }
        return {
            "input": task,
            "result": {
                "data_source": "⚠️ 演示数据（接入供应商数据源后可替换）",
                "lead_time_assessment": {
                    "海运(美国西岸)": "18-25天", "海运(美国东岸)": "30-40天",
                    "空运": "5-8天", "中欧班列": "16-20天",
                },
                "recommendations": [
                    "断货风险高的 SKU 优先空运补货（5-8天）",
                    "常规补货走海运，预留 45 天 buffer（30 天运输 + 7 天清关 + 8 天入库）",
                    "旺季前 2 个月下单，避开舱位紧张",
                ],
            },
            "kpis": {"air_lead_days": 7, "sea_lead_days": 35},
        }


class QAAgent(AmazonAgent):
    """知识库检索：从 FAQ / 历史工单检索答案"""

    def __init__(self) -> None:
        super().__init__(
            "qa_agent", "知识库检索Agent", "📚",
            "FAQ知识库检索、历史工单答案、政策库查询",
            ["知识库", "faq", "工单", "政策库", "检索答案"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        query = str(ctx.get("message_classification") or ctx.get("buyer_message") or task).lower()
        hits = []
        for item in _FAQ_KB:
            if any(kw in query for kw in item["q"].lower().split("怎么")[-1:]) or any(
                kw in query for kw in ("退货", "发货", "发票", "优惠券", "差评", "断货")
            ):
                if item["q"] in query or any(kw in query for kw in item["q"][:2].split()):
                    pass
            if item["q"] in query or any(kw in query for kw in item["q"].replace("怎么", "").split()):
                hits.append(item)
        if not hits:
            for item in _FAQ_KB:
                if any(kw in query for kw in ("退货", "发货", "发票", "coupon", "优惠券", "差评", "断货")):
                    hits.append(item)
        return {
            "input": task,
            "result": {
                "query": query,
                "kb_hits": hits[:3] if hits else [{"q": "通用", "a": "建议转人工客服处理"}],
                "kb_size": len(_FAQ_KB),
            },
            "kpis": {"hits": len(hits[:3])},
        }
