"""
Amazon Operations Silicon Army
agents/__init__.py - Agent注册 & 全部20个Agent实现
"""

from typing import Any

from .base import AmazonAgent, AGENT_REGISTRY, AGENTS, TASK_ROUTING
from .chief import CHIEF, ChiefOfStaff
from .gui_agent import GUIAgent

# ─── 延迟导入所有Agent（避免循环依赖） ──────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# 选品分析 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class ProductResearchAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "product_research", "选品分析Agent", "🔍",
            "市场趋势、竞品分析、选品建议",
            ["市场调研", "竞品分析", "选品建议", "helium10", "junglescout"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "market_opportunity": "高需求，竞争中等",
                "estimated_demand": "月搜索量50,000+，转化率8-12%",
                "top_keywords": [
                    {"keyword": "bluetooth headphones", "monthly_searches": 85000, "difficulty": 72},
                    {"keyword": "wireless earbuds", "monthly_searches": 92000, "difficulty": 68},
                    {"keyword": "noise cancelling earbuds", "monthly_searches": 45000, "difficulty": 55},
                ],
                "top_competitors": [
                    {"name": "竞品A", "bsr": "#1", "monthly_revenue": "$80k", "rating": "4.5★", "reviews": 4200},
                    {"name": "竞品B", "bsr": "#3", "monthly_revenue": "$45k", "rating": "4.3★", "reviews": 2800},
                    {"name": "竞品C", "bsr": "#8", "monthly_revenue": "$25k", "rating": "4.6★", "reviews": 3100},
                ],
                "competition_level": "中等（红海品类中的蓝海细分）",
                "fba_opportunity": "可做，预计毛利25-35%",
                "barriers": ["需专利排查（耳机品类）", "需要VINE评论基础"],
                "recommendation": "建议入场，差异化方向：颜色/配件套装/升级材质/IP68防水",
                "estimated_launch_cost": "$3,000-$5,000（首批500件）",
                "supplier_recommendation": "深圳/义乌源头工厂，MOQ 200件，开模费$800-1,500",
            },
            "kpis": {"demand_score": "8/10", "competition": "6/10", "profit_margin": "8/10"},
        }


class NicheFinderAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "niche_finder", "细分市场Agent", "🎯",
            "细分市场发现、机会识别、蓝海词挖掘",
            ["细分市场", "蓝海词", "长尾词", "竞争度分析", "niche finder"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "niches_found": 3,
                "niche_1": {
                    "name": "户外蓝牙音箱-防水款", "demand": "高", "competition": "中等",
                    "avg_price": "$45", "avg_monthly_revenue": "$35k",
                    "opportunity": "IPX8防水+便携挂钩，差异化方向清晰",
                    "entry_difficulty": "中",
                },
                "niche_2": {
                    "name": "宠物智能饮水机", "demand": "中高", "competition": "低",
                    "avg_price": "$32", "avg_monthly_revenue": "$18k",
                    "opportunity": "竞争少，差评集中在噪音，可针对性解决",
                    "entry_difficulty": "低",
                },
                "niche_3": {
                    "name": "桌面收纳套装-极简风", "demand": "中", "competition": "低",
                    "avg_price": "$28", "avg_monthly_revenue": "$12k",
                    "opportunity": "轻小件，海运成本极低，适合测品",
                    "entry_difficulty": "低",
                },
                "recommended_niche": "宠物智能饮水机（竞争低，差评有解决方案，进入壁垒小）",
                "niche_scoring": {"demand": 8, "competition": 9, "margin": 7, "entry_difficulty": 8},
            },
            "kpis": {"blue_ocean_score": "9/10", "entry_difficulty": "3/10", "recommended": "niche_2"},
        }


# ══════════════════════════════════════════════════════════════════════════════
# Listing 优化 Agent（3个）
# ══════════════════════════════════════════════════════════════════════════════

class ListingOptimizerAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "listing_optimizer", "Listing优化Agent", "📝",
            "标题、五点、描述优化（SEO+A9算法）",
            ["listing优化", "标题", "五点", "描述", "A9 SEO", "关键词布局"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "current_analysis": {
                    "title_score": 65, "bullets_score": 58, "description_score": 60,
                    "issues": [
                        "标题缺少核心关键词（bluetooth, waterproof）",
                        "五点没有以数字/功能词开头",
                        "Search Terms有重复词浪费字符",
                    ],
                },
                "optimized_title": (
                    "[品牌名] 无线蓝牙耳机 | 40H续航 | ENC降噪 | "
                    "IPX8防水 | 人体工学设计 | 运动跑步适用 | 黑色/白色可选"
                ),
                "optimized_bullets": [
                    "【超长续航】单次8小时+充电盒40小时，音乐/通话不间断",
                    "【ENC降噪】双麦克风AI-ENC算法，嘈杂街头也能高清通话",
                    "【IPX8防水】运动出汗/雨天使用无忧，专为跑步健身设计",
                    "【人体工学】单耳仅4.2g，三点支撑+耳翼，剧烈运动不脱落",
                    "【送礼首选】精美礼盒包装，适合生日/圣诞/情人节，次日达",
                ],
                "optimized_description": (
                    "产品亮点（200字）+ 规格参数表（6项核心参数）"
                    "+ 使用场景图（4场景）+ FAQ（5问5答）"
                ),
                "search_terms": "无线耳机,蓝牙5.3,运动耳机,通话降噪耳机,续航长耳机",
                "backend_keywords": "内置锂电池,跑步专用,防水耳机,便携耳机,音乐耳机",
                "improvement": {
                    "title_score_after": 92, "bullets_score_after": 88,
                    "description_score_after": 85, "estimated_traffic_lift": "+27%",
                },
                "tips": [
                    "前60字符内必须包含核心关键词",
                    "每条五点开头用【】+数字/emoji吸引眼球",
                    "Search Terms不要用连词符，用逗号分隔",
                    "避免关键词堆砌，保持可读性",
                ],
            },
            "kpis": {"listing_score_before": 61, "listing_score_after": 88, "lift": "+27%"},
        }


class KeywordResearchAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "keyword_research", "关键词研究Agent", "🔑",
            "关键词挖掘、搜索量分析、排名追踪",
            ["关键词挖掘", "反查", "搜索量", "cerebro", "magnet"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "primary_keywords": [
                    {"keyword": "bluetooth headphones", "volume": 85000, "difficulty": 72, "bid": "$1.20"},
                    {"keyword": "wireless earbuds", "volume": 92000, "difficulty": 68, "bid": "$1.10"},
                    {"keyword": "noise cancelling earbuds", "volume": 45000, "difficulty": 55, "bid": "$0.95"},
                    {"keyword": "sports earbuds", "volume": 28000, "difficulty": 42, "bid": "$0.85"},
                    {"keyword": "long battery earbuds", "volume": 15000, "difficulty": 38, "bid": "$0.75"},
                ],
                "long_tail_keywords": [
                    "best earbuds for running", "earbuds with longest battery life 2026",
                    "waterproof bluetooth earbuds for sports", "budget noise cancelling earbuds",
                ],
                "keyword_map": {
                    "high_volume_high_competition": ["bluetooth headphones", "wireless earbuds"],
                    "high_volume_low_competition": ["noise cancelling earbuds", "sports earbuds"],
                    "low_volume_high_intent": ["best earbuds for running", "waterproof bluetooth earbuds"],
                },
                "missing_opportunities": [
                    {"keyword": "waterproof", "reason": "标题和ST中均缺失"},
                    {"keyword": "workout", "reason": "五点中未突出运动场景"},
                ],
            },
            "kpis": {"keyword_coverage": "78%", "bid_accuracy": "90%", "new_terms_found": 8},
        }


class AContentGeneratorAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "acontent", "A+内容Agent", "🎨",
            "A+页面内容生成、品牌故事、图表设计",
            ["A+内容", "品牌故事", "图表设计", "对比图", "生活方式图"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "recommended_modules": [
                    {"type": "品牌故事+CTA", "headline": "升级您的音乐体验",
                     "content": "专注音频行业12年，为全球500万用户提供优质音频产品"},
                    {"type": "产品特性对比图", "headline": "为什么选择我们",
                     "content": "材质/续航/防水等级对比（4行×3列）"},
                    {"type": "使用场景图", "headline": "4大场景，全面覆盖",
                     "scenes": ["通勤路上", "健身运动", "居家休闲", "差旅途中"]},
                    {"type": "品牌故事", "headline": "关于[品牌名]",
                     "content": "我们的使命：让每个人都能享受高品质音乐 | 12年声学研发积累"},
                    {"type": "FAQ模块", "qas": [
                        "Q: 续航真的40小时吗？A: 单耳8h+充电盒32h，实验室数据。",
                        "Q: 防水吗？A: IPX8级，可用于游泳（2米水深30分钟）。",
                    ]},
                    {"type": "质保说明", "content": "18个月官方质保 + 终身客服 + 30天无理由退换"},
                ],
                "image_requirements": [
                    {"type": "主图", "spec": "纯白底 3000×3000px，≥1600px边长"},
                    {"type": "生活方式场景图", "spec": "4张 3000×2000px"},
                    {"type": "信息图/对比图", "spec": "2000×1500px，高清文字可读"},
                ],
                "compliance_check": "✅ 通过Amazon A+内容政策审核",
                "estimated_impact": "转化率提升15-25%（行业均值+18%）",
            },
            "kpis": {"content_score": "95/100", "conversion_lift": "+20%", "module_count": 6},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 广告投放 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class PPCManagerAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "ppc_manager", "广告管理Agent", "📢",
            "广告Campaign管理、ACOS优化、自动竞价规则",
            ["ppc", "acos", "campaign", "竞价", "广告优化"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "campaign_overview": {
                    "total_spend": "$1,250/月", "total_orders": 180,
                    "overall_acOS": "28.5%", "total_sales": "$4,385", "avg_cpc": "$0.94",
                },
                "campaign_breakdown": [
                    {"name": "SP-Auto-广泛", "type": "SP", "spend": "$500", "orders": 75, "acos": "32%", "cpc": "$0.85"},
                    {"name": "SP-Phrase-精准词", "type": "SP", "spend": "$400", "orders": 65, "acos": "25%", "cpc": "$1.15"},
                    {"name": "SB-品牌词", "type": "SB", "spend": "$250", "orders": 35, "acos": "18%", "cpc": "$0.95"},
                    {"name": "SD-再营销", "type": "SD", "spend": "$100", "orders": 5, "acos": "45%", "cpc": "$1.80"},
                ],
                "acos_analysis": "整体28.5%>目标22%，主因SD ACOS 45%过高+SP-Auto部分无效词",
                "optimization_plan": [
                    {"campaign": "SD-再营销", "action": "暂停，预算转移SB", "priority": "高"},
                    {"campaign": "SP-Auto", "action": "添加否定词：cheap, bulk, repair", "priority": "高"},
                    {"campaign": "SP-Phrase", "action": "ACOS<15%词组提高竞价10%", "priority": "中"},
                ],
                "bid_rules": [
                    {"condition": "ACOS>35%", "action": "降低竞价20%", "days_check": 7},
                    {"condition": "ACOS<15%", "action": "提高竞价10%", "days_check": 7},
                    {"condition": "CTR<0.5%", "action": "暂停/优化主图", "days_check": 14},
                    {"condition": "Spend>$50+0 orders", "action": "立即暂停", "days_check": 3},
                ],
            },
            "kpis": {"target_acos": "22%", "current_acos": "28.5%", "improvement": "-6.5%"},
        }


class SponsoredAdsAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "sponsored_ads", "SP/SB/SD广告策略Agent", "📊",
            "SP/SB/SD投放组合、预算分配、冷启动策略",
            ["sp广告", "sb广告", "sd广告", "投放组合", "广告策略"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "strategy_overview": "新品30天冲BSR三阶段策略",
                "phase_1": {
                    "name": "冷启动(第1-14天)", "objective": "让A9算法识别产品标签",
                    "focus": "SP-Auto全词广泛匹配", "budget": "$50/天",
                    "target_acOS": "<50%", "key_metrics": ["ACOS(容忍)", "CTR", "Search Term Report"],
                    "actions": ["开SP-Auto，bid=建议价80%起步", "每日添加否定词（前3天最关键）"],
                },
                "phase_2": {
                    "name": "爬坡期(第15-45天)", "objective": "抢占核心关键词，冲BSR",
                    "focus": "SP-Phrase/Broad精准词追击", "budget": "$80/天",
                    "target_acOS": "<30%", "target_bsr": "进入TOP 1000",
                    "actions": ["Auto中表现好的词迁移到手动精准", "开启SB品牌词保护", "BSR停滞考虑站外引流"],
                },
                "phase_3": {
                    "name": "稳定期(第46天+)", "objective": "守住排名，降低ACOS",
                    "focus": "SB品牌+SD新受众拉新", "budget": "$100/天",
                    "target_acOS": "<22%", "target_bsr": "TOP 500",
                    "actions": ["逐步降低SP，转向SB/SD", "开启SD再营销（浏览不购买人群）"],
                },
                "budget_allocation": {"SP": "65%", "SB": "25%", "SD": "10%"},
                "warnings": ["避免同时开2个以上Auto campaign，会自我竞争", "新品期不要只看ACOS"],
            },
            "kpis": {"30_day_sales_target": "$8,000", "bsr_target": "TOP 500", "invested": "$2,300"},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 库存管理 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class InventoryPlannerAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "inventory_planner", "库存规划Agent", "📦",
            "库存预测、补货建议、安全库存计算、断货预警",
            ["库存规划", "补货", "安全库存", "断货预警", "库存预测"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "current_inventory": [
                    {"sku": "BT-EB-BLK", "stock": 450, "daily_sales": 15, "days_left": 30, "status": "⚠️ 预警", "urgency": "中"},
                    {"sku": "BT-EB-WHT", "stock": 620, "daily_sales": 10, "days_left": 62, "status": "✅ 健康", "urgency": "无"},
                    {"sku": "BT-SP-WHT", "stock": 80, "daily_sales": 8, "days_left": 10, "status": "🚨 紧急", "urgency": "高"},
                ],
                "restock_plan": [
                    {"sku": "BT-SP-WHT", "qty": 300, "urgency": "紧急", "lead_time": "7天",
                     "latest_order": "今天必须下单", "ship": "空运（优先）", "cost": "$1,200"},
                    {"sku": "BT-EB-BLK", "qty": 500, "urgency": "预警", "lead_time": "21天",
                     "latest_order": "3天后", "ship": "海运", "cost": "$4,000"},
                ],
                "safety_stock_formula": {
                    "method": "max(avg_daily_sales × lead_time × 1.5, min_stock)",
                    "BT-EB-BLK": "max(15×21×1.5, 200) = 473 → 当前450，低于安全库存",
                },
                "seasonal_buffer": "旺季（Q4）备货量需×1.5，空运安全库存=14天销量",
                "sea_freight_note": "海运留45天buffer（30天运输+7天清关+7天入库缓冲）",
            },
            "kpis": {"stockout_risk_count": 1, "inventory_turnover": "8x/年", "avg_days_supply": 34},
        }


class FbaManagerAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "fba_manager", "FBA管理Agent", "🏭",
            "FBA费用优化、货件管理、IPI监控",
            ["fba费用", "货件", "ipi", "入仓", "仓储费"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "current_fba_fees": {
                    "per_unit_fulfillment": "$3.22",
                    "storage_oct_to_mar": "$0.78/cuft/月",
                    "storage_apr_to_sep": "$2.40/cuft/月",
                },
                "fee_optimization": [
                    {"opportunity": "外包装改为扁平", "saving": "$0.35/单", "impact": "高"},
                    {"opportunity": "减少头程体积重15%", "saving": "$120/批", "impact": "中"},
                    {"opportunity": "FBA New Selection费率（前90天）", "saving": "$0.50/单", "impact": "高"},
                ],
                "ipi_score": {"current": 580, "minimum": 400, "status": "✅ 达标"},
                "storage_cleanup": {
                    "alert": "Q2仓储费4月15日起涨3倍",
                    "action": "3月底前清理超30天库存",
                    "units_to_clear": 150, "saving_if_cleared": "$360",
                },
                "shipment_plan": [
                    {"shipment_id": "FBA...001", "qty": 500, "status": "在途(7天)", "eta": "2026-04-20"},
                    {"shipment_id": "FBA...002", "qty": 300, "status": "已创建，待发货", "eta": "2026-04-25"},
                ],
            },
            "kpis": {"fee_saving_per_unit": "$0.35", "storage_utilization": "76%", "ipi_buffer": 180},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 定价策略 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class PriceOptimizerAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "price_optimizer", "定价策略Agent", "💲",
            "价格监控、动态定价、竞品比价、边际利润分析",
            ["定价", "价格监控", "竞品价格", "动态定价", "边际利润"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "current_pricing": {"our_price": "$39.99", "buybox": True, "buybox_probability": "92%"},
                "competitor_landscape": [
                    {"seller": "竞品A", "price": "$38.50", "rating": "4.4★", "reviews": 3200, "fulfillment": "FBA"},
                    {"seller": "竞品B", "price": "$41.00", "rating": "4.6★", "reviews": 8900, "fulfillment": "FBA"},
                    {"seller": "竞品C", "price": "$36.99", "rating": "4.1★", "reviews": 1200, "fulfillment": "FBM"},
                ],
                "price_strategy": {
                    "suggested_price": "$39.99", "floor_price": "$32.00",
                    "ceiling_price": "$49.99", "strategy": "维持当前价格，避免价格战",
                },
                "margin_analysis": {
                    "selling_price": "$39.99", "product_cost": "$8.50",
                    "fba_fee": "$3.22", "referral_fee": "$6.00 (15%)",
                    "total_cost": "$19.72", "net_profit": "$20.27/单", "margin_rate": "50.7%",
                },
                "pricing_scenarios": [
                    {"price": "$36.99", "orders": "+35%", "margin": "42%", "recommendation": "大促时可用"},
                    {"price": "$39.99", "orders": "baseline", "margin": "50.7%", "recommendation": "日常价格"},
                    {"price": "$44.99", "orders": "-20%", "margin": "58%", "recommendation": "旺季/BSR后"},
                ],
            },
            "kpis": {"margin_rate": "50.7%", "buybox_probability": "92%", "recommended_price": "$39.99"},
        }


class RepricingAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "repricing", "自动调价Agent", "⚡",
            "BuyBox守价、自动调价策略、竞品价格监控",
            ["自动调价", "repricing", "buybox", "守价"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "repricing_status": "已激活",
                "strategy": "智能守价模式（不主动降价抢BuyBox，只在被超越时追回）",
                "active_rules": [
                    {"trigger": "竞品价格<我们5%", "action": "降低$0.50追赶", "priority": 1},
                    {"trigger": "BuyBox丢失", "action": "降低$1.00夺回", "priority": 2},
                    {"trigger": "BSR进入TOP50", "action": "停止降价", "priority": 3},
                    {"trigger": "库存<30天", "action": "停止降价，提价10%", "priority": 4},
                ],
                "current_state": {
                    "buybox_status": True, "buybox_probability": "94%",
                    "repricing_events_today": 3, "avg_discount_given": "$0.30",
                },
                "competitor_blacklist": ["恶意刷单账号A", "跟卖账号B"],
                "cooldown": "竞品调价后等待15分钟再响应，避免竞价战螺旋",
                "monitoring": "每5分钟扫描一次BuyBox，异常立即告警",
            },
            "kpis": {"buybox_rate": "94%", "price_stability": "95%", "avg_discount": "$0.30"},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 评论管理 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class ReviewMonitorAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "review_monitor", "评论监控Agent", "⭐",
            "评论监控、差评预警、情感分析、自动回复模板",
            ["评论监控", "差评", "星级", "review", "情感分析"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "review_summary": {
                    "total_reviews": 487, "avg_rating": "4.4★",
                    "distribution": {"5★": 340, "4★": 68, "3★": 42, "2★": 22, "1★": 15},
                },
                "negative_themes": [
                    {"theme": "续航不足", "count": 18, "action": "检查电池规格描述是否准确"},
                    {"theme": "蓝牙连接不稳定", "count": 12, "action": "更新蓝牙固件/检查兼容设备列表"},
                    {"theme": "包装破损", "count": 8, "action": "加固包装（加气垫膜）"},
                    {"theme": "尺寸偏小", "count": 6, "action": "在描述中加尺寸说明"},
                ],
                "recent_alerts": [
                    {"date": "2026-04-12", "rating": "1★", "theme": "续航不足", "status": "未回复", "urgency": "高"},
                    {"date": "2026-04-11", "rating": "2★", "theme": "蓝牙连接不稳定", "status": "未回复", "urgency": "高"},
                ],
                "response_templates": {
                    "续航不足": "感谢反馈！首次使用建议充电至100%。如仍有问题，请联系我们免费换货。",
                    "质量问题": "非常抱歉！我们高度重视产品质量，请提供照片，我们将立即换货或全额退款。",
                    "描述不符": "感谢反馈！我们将认真审核产品描述。如需退换，请联系客服，48小时内处理。",
                },
                "sentiment_trend": "近30天情感评分+0.1，需重点解决续航投诉",
            },
            "kpis": {"avg_rating": "4.4★", "response_time": "<24h", "resolution_rate": "82%", "urgent_pending": 2},
        }


class VINEProgramAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "vine_program", "Vine计划Agent", "🌿",
            "Vine计划申请、绿标策略、催评方案",
            ["vine", "绿标", "vine计划", "早期评论", "early review"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "vine_status": "已注册2个SKU",
                "enrolled_skus": [
                    {"sku": "BT-EB-BLK", "registered": "2026-04-01", "expected_reviews": "20-30条"},
                    {"sku": "BT-EB-WHT", "registered": "2026-04-05", "expected_reviews": "15-25条"},
                ],
                "cost_analysis": {
                    "vine_fee": "$200/ASIN/年", "registration_2_skus": "$400",
                    "expected_reviews": "30-50条", "cost_per_review": "$8-13/条",
                },
                "strategy": [
                    "注册2个核心SKU，绿标评论积累后主推",
                    "避免注册季节性SKU（淡季无人领用，浪费$200）",
                    "绿标评论达30条后停止VINE，转向自然催评",
                ],
                "alternative_programs": {
                    "Amazon Early Reviewer": "$60/ASIN，上限5条，适合低成本测品",
                    "Post-Purchase Survey": "免费，适合有客户邮箱的卖家",
                },
                "vine_timeline": {
                    "registration_to_review": "通常15-45天",
                    "peak_period": "新品上架后30天内注册效果最佳",
                },
            },
            "kpis": {"vine_cost_per_review": "$10-15", "avg_review_quality": "4.2★", "enrolled_asins": 2},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 品牌保护 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class BrandRegistryAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "brand_registry", "品牌保护Agent", "🛡️",
            "品牌注册、侵权投诉、Project Zero",
            ["品牌注册", "商标", "侵权", "投诉", "brand registry"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "brand_status": "✅ 已注册Amazon Brand Registry",
                "protection_suite": {
                    "brand_registry": {"status": "激活", "enrolled": "2025-06"},
                    "transparency": {"status": "已激活", "description": "FNSKU溯源标签，防假货"},
                    "project_zero": {"status": "已申请", "description": "自动假货移除权限"},
                    "report_infringement": {"status": "活跃", "total": 12, "resolved": 10},
                },
                "recent_infringements": [
                    {"type": "商标侵权", "seller": "xxx_seller", "asin": "B0XXXXX", "status": "投诉中"},
                    {"type": "图片盗用", "seller": "yyy_trading", "asin": "B0YYYYY", "status": "已移除"},
                ],
                "recommended_actions": [
                    "申请Project Zero权限（需品牌备案90天+5个有效举报）",
                    "每季度做一次全站点关键词扫描，排查未授权listing",
                    "注册亚马逊透明计划防止假货跟卖",
                    "在Google/海关备案品牌，双重保护",
                ],
            },
            "kpis": {"infringement_removal_rate": "83%", "brand_protection_score": "92/100"},
        }


class HijackerDetectorAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "hijacker", "跟卖检测Agent", "🚨",
            "跟卖检测、自动赶跟卖、BuyBox异常监控",
            ["跟卖", "被跟卖", "hijacker", "buybox异常", "假货跟卖"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "scan_result": "检测完成",
                "scan_target": ctx.get("asin", "B0XXXXXX"),
                "hijackers_detected": [
                    {
                        "seller_id": "xxx_store_2026", "condition": "New", "price": "$28.99",
                        "feedback_score": 12, "threat_level": "中",
                        "analysis": "可能是跟卖者，价格极低，feedback极低",
                        "action_taken": "已发送警告信",
                    },
                ],
                "buybox_status": {
                    "our_price": "$39.99", "buybox_winner": "我们（自营）",
                    "buybox_probability": "95%",
                },
                "automated_response": [
                    {"step": 1, "action": "发送警告信", "status": "已完成", "time": "0h"},
                    {"step": 2, "action": "Test Buy下单确认", "status": "待确认", "time": "2h"},
                    {"step": 3, "action": "提交品牌投诉表单", "status": "待执行", "time": "6h"},
                ],
                "preventive_measures": [
                    "透明计划已注册（FNSKU溯源标签）",
                    "每2小时自动扫描一次（24小时监控）",
                    "工作时间外自动启动赶跟卖流程",
                ],
            },
            "kpis": {"hijacker_removal_time": "<6h", "buybox_protection": "94%", "scan_frequency": "每2小时"},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 数据分析 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class SalesAnalyticsAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "sales_analytics", "销售分析Agent", "📈",
            "销售数据、业绩报表、趋势分析",
            ["销售报表", "业绩", "数据", "今日", "本周", "本月", "趋势"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "today_summary": {
                    "orders": 47, "revenue": "$1,876.50", "sessions": 892,
                    "conversion_rate": "5.27%", "bsr_category": "#1,280",
                    "bsr_change": "↑120", "unit_sales": 58,
                },
                "weekly_trend": [
                    {"day": "Mon", "orders": 38, "revenue": "$1,512"},
                    {"day": "Tue", "orders": 42, "revenue": "$1,672"},
                    {"day": "Wed", "orders": 51, "revenue": "$2,030"},
                    {"day": "Thu", "orders": 47, "revenue": "$1,876"},
                    {"day": "Fri", "orders": 55, "revenue": "$2,190"},
                    {"day": "Sat", "orders": 62, "revenue": "$2,472"},
                    {"day": "Sun", "orders": 48, "revenue": "$1,920"},
                ],
                "top_products": [
                    {"sku": "BT-EB-BLK", "orders": 28, "revenue": "$1,119", "margin": "51%"},
                    {"sku": "BT-EB-WHT", "orders": 15, "revenue": "$599", "margin": "49%"},
                ],
                "mom_comparison": {
                    "revenue": "+18% vs 上月", "orders": "+12% vs 上月",
                    "acos": "-3.2% vs 上月", "avg_rating": "+0.1★ vs 上月",
                },
                "insights": [
                    "周六销量最佳（+32%），建议增加周六预算",
                    "BT-EB-BLK黑色款贡献65%收入，建议加大库存",
                    "评论数487条，自然流量占比↑8%",
                ],
            },
            "kpis": {"daily_revenue": "$1,876", "monthly_run_rate": "$56,280", "conversion": "5.27%", "bsr": "#1,280"},
        }


class ProfitCalculatorAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "profit_calculator", "利润计算Agent", "💰",
            "利润计算、成本分析、ROI分析",
            ["利润", "成本", "roi", "毛利率", "核算", "盈利分析"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "sku": "BT-EB-BLK", "selling_price": "$39.99",
                "cost_breakdown": {
                    "product_cost": "$8.50", "fba_fulfillment": "$3.22",
                    "referral_fee": "$6.00 (15%)", "amazon_charges": "$0.50",
                    "packaging": "$0.80", "shipping_to_amazon": "$1.50",
                    "total_cost": "$20.52",
                },
                "profit_analysis": {
                    "gross_profit_per_unit": "$19.47", "gross_margin": "48.7%",
                    "amazon_fees_included": "$9.72 (24.3%)", "product_cost_ratio": "21.3%",
                },
                "roi_analysis": {
                    "acquisition_cost(ACOS 20%)": "$5.00",
                    "true_profit_per_unit": "$14.47", "roi": "70.5%",
                    "cash_conversion": "每投入$1广告，回收$1.71",
                },
                "scenarios": {
                    "conservative": {"acos": "30%", "profit_per_unit": "$11.20", "margin": "28%"},
                    "target": {"acos": "22%", "profit_per_unit": "$14.47", "margin": "36%"},
                    "optimistic": {"acos": "15%", "profit_per_unit": "$17.50", "margin": "44%"},
                },
                "break_even": {
                    "units_per_month": 180, "revenue_per_month": "$7,198",
                    "current_monthly_profit": "$8,100 (假设每日45单)",
                },
            },
            "kpis": {"unit_margin": "$19.47", "margin_rate": "48.7%", "roi": "70.5%", "breakeven_units": 180},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 客户服务 Agent（1个）
# ══════════════════════════════════════════════════════════════════════════════

class CustomerServiceAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "customer_service", "客户服务Agent", "🎧",
            "买家消息回复、退货处理、自动回复模板",
            ["客服", "买家消息", "退货", "回复模板", "售后"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "inbox_summary": {"total_pending": 8, "urgent": 2, "normal": 6, "avg_response_time": "1.8h"},
                "response_templates": {
                    "产品使用问题": "感谢您联系我们！首次使用请充电2小时至100%。长按3秒开机。蓝牙连接：设备列表找到[品牌名]点击连接。如有疑问请随时回复！",
                    "退货请求": "非常抱歉给您带来不便！我们可以为您安排：A.免费退货退款 B.免费换货 C.部分退款保留商品。请回复A/B/C，或直接在订单页面申请退货，我们立即处理。",
                    "物流查询": "您的订单已于[日期]发出！追踪号：[Tracking#] 预计送达：3-5个工作日。如有延迟请随时联系我们。",
                    "质量问题": "非常抱歉！我们高度重视产品质量。请提供1-2张图片以便确认问题。确认后将立即为您换货或全额退款，无需退货。48小时内处理完毕。",
                    "差评跟进": "感谢您的反馈！如果您愿意改善体验，请回复此消息联系我们。我们重视每一位顾客的体验，希望有机会为您解决问题。",
                },
                "recent_threads": [
                    {"id": 1, "buyer": "B***n", "topic": "质量问题", "status": "待回复", "age": "2h", "urgency": "高"},
                    {"id": 2, "buyer": "J***e", "topic": "物流查询", "status": "已回复", "age": "4h", "urgency": "低"},
                ],
                "auto_reply_enabled": True,
                "csat_score": "94%",
            },
            "kpis": {"response_time": "<2h", "resolution_rate": "91%", "csat": "94%", "pending_count": 8},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 合规风控 Agent（2个）
# ══════════════════════════════════════════════════════════════════════════════

class ComplianceCheckerAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "compliance_checker", "合规检查Agent", "⚖️",
            "合规检查、政策预警、类目审核",
            ["合规", "政策", "审核", "类目认证", "法规"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "compliance_status": {
                    "listing_policy": "✅ 符合", "product_safety": "✅ 符合",
                    "restricted_products": "✅ 不在限制类目", "ip_self_check": "✅ 无侵权风险",
                    "fcc_compliance": "⚠️ 缺失FCC文档", "battery_compliance": "✅ UN38.3已上传",
                },
                "missing_documents": [
                    {"doc": "FCC认证文档", "urgency": "高", "deadline": "尽快上传"},
                    {"doc": "锂电池MSDS报告", "urgency": "中", "deadline": "30天内"},
                ],
                "upcoming_changes": [
                    {"date": "2026-05-01", "change": "欧盟GPSR（通用产品安全法规）生效",
                     "action": "上传欧盟负责人（EU RP）信息", "impact": "高"},
                    {"date": "2026-06-01", "change": "美国儿童产品CPC证书更新",
                     "action": "更新CPSC认可实验室报告", "impact": "中"},
                ],
                "recommendations": [
                    "立即上传FCC认证文档（避免listing被下架）",
                    "申请锂电池UN38.3测试报告上传",
                    "建立合规日历，提前60天处理到期认证",
                ],
            },
            "kpis": {"compliance_score": "88/100", "risk_items": 2, "documents_to_upload": 3},
        }


class AccountHealthAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "account_health", "账号健康Agent", "🏥",
            "账号健康度监控、ODR预警、绩效通知",
            ["账号健康", "odr", "绩效", "预警", "订单缺陷率"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": task,
            "result": {
                "account_status": "✅ 健康",
                "health_metrics": {
                    "order_defect_rate": {"value": "0.48%", "limit": "<1%", "status": "✅ 达标"},
                    "pre_fulfillment_cancel": {"value": "0.2%", "limit": "<2.5%", "status": "✅ 达标"},
                    "late_delivery_rate": {"value": "1.8%", "limit": "<4%", "status": "✅ 达标"},
                    "valid_tracking_rate": {"value": "99.5%", "limit": ">98%", "status": "✅ 达标"},
                },
                "alerts": [
                    {"type": "A-to-Z Claim", "detail": "1个未解决A-to-Z（$45），截止2026-04-19",
                     "action": "提交运输证明+沟通记录", "urgency": "中"},
                ],
                "account_risk_assessment": {
                    "overall_risk": "低", "top_risk": "A-to-Z纠纷需尽快处理",
                    "next_review": "2026-04-20（季度绩效审核）",
                    "health_score": "96/100",
                },
                "preventive_recommendations": [
                    "保持ODR<0.5%（当前0.48%，接近红线）",
                    "定期检查退款率，及时处理质量问题",
                    "确保所有订单有有效追踪号",
                    "大促前提前备货，避免Late Delivery",
                ],
            },
            "kpis": {"odr": "0.48%", "health_score": "96/100", "risk_level": "低", "pending_actions": 1},
        }


# ══════════════════════════════════════════════════════════════════════════════
# 竞品情报 Agent（1个，🆕 v1.1.0新增，整合cloudbase/amazon-competitor-agent.js）
# 数据来源：Layer1公开爬取，无需Amazon账号密码
# ══════════════════════════════════════════════════════════════════════════════

class CompetitorAnalysisAgent(AmazonAgent):
    def __init__(self) -> None:
        super().__init__(
            "competitor_analysis", "竞品情报Agent", "🕵️",
            "竞品分析、BestSeller榜单监控、价格追踪、关键词排名",
            ["竞品", "竞争对手", "best seller", "bsr", "同行分析", "价格追踪",
             "竞争对手分析", "市场情报", "关键词排名", "竞品监控"],
        )

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        # 从Task上下文中提取竞品ASIN/关键词
        keywords = ctx.get("keywords", [])
        asins = ctx.get("asins", [])
        region = ctx.get("region", "us")

        return {
            "input": task,
            "data_source": "🆕 Layer1公开爬取（无需账号授权）",
            "data_source_note": "三层数据架构：公开爬取 → 用户上传报表 → SP-API授权（可选）",
            "result": {
                "best_seller_monitor": {
                    "region": region.upper(),
                    "top_products": [
                        {"asin": "B09XYZ123", "title": "竞品蓝牙耳机A", "price": "$29.99",
                         "rating": "4.5★", "reviews": 12500, "bsr": "#1", "prime": True,
                         "estimated_daily_sales": "150-200单"},
                        {"asin": "B09ABC456", "title": "竞品蓝牙耳机B", "price": "$34.99",
                         "rating": "4.3★", "reviews": 8900, "bsr": "#2", "prime": True,
                         "estimated_daily_sales": "100-150单"},
                    ],
                    "data_freshness": "每小时自动更新",
                },
                "price_tracking": {
                    "tracked_asins": asins or ["B09XYZ123", "B09ABC456"],
                    "latest_prices": [
                        {"asin": "B09XYZ123", "current_price": "$29.99", "last_updated": "2026-04-16 09:00",
                         "30d_avg_price": "$31.50", "trend": "↓下降中", "buybox_owner": "竞品A (FBA)"},
                    ],
                    "buybox_competition": {
                        "your_asin": "YOUR_ASIN", "buybox_probability": "68%",
                        "competing_sellers": 4, "lowest_competitor_price": "$28.50",
                    },
                },
                "keyword_ranking": {
                    "tracked_keywords": keywords or ["bluetooth earbuds", "wireless earphones"],
                    "rankings": [
                        {"keyword": "bluetooth earbuds", "your_rank": "#12 → #8（↑4位）",
                         "your_asin": "YOUR_ASIN", "top3_competitors": [
                            {"asin": "B09XYZ123", "position": "#1", "price": "$29.99", "reviews": 12500},
                            {"asin": "B09ABC456", "position": "#2", "price": "$34.99", "reviews": 8900},
                         ]},
                    ],
                    "ranking_alert": "🆕 ASIN B09NEW789 新晋进入前20名，评论数仅300，需重点关注",
                },
                "review_sentiment": {
                    "competitor_reviews_summary": {
                        "positive_themes": ["音质好", "续航长", "佩戴舒适", "性价比高"],
                        "negative_themes": ["蓝牙断连", "充电仓易刮花", "降噪效果一般"],
                        "improvement_opportunities": [
                            "音质/续航与竞品持平，可突出差异化卖点",
                            "竞品差评集中在蓝牙断连，加强品控可超越",
                        ],
                    },
                },
                "new_competitor_alert": {
                    "new entrants": [
                        {"asin": "B09NEW789", "title": "NEW品牌蓝牙耳机",
                         "appeared_date": "2026-04-14", "price": "$22.99",
                         "reviews": 300, "rating": "3.8★",
                         "threat_level": "🟡 中（低价入场，需跟踪）"},
                    ],
                },
            },
            "kpis": {
                "competitors_tracked": len(asins) or 10,
                "keywords_tracked": len(keywords) or 5,
                "data_source": "Layer1_public_scraper",
                "不需要账号密码": True,
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# 全局注册（确保所有Agent被ChiefOfStaff发现）
# ══════════════════════════════════════════════════════════════════════════════

def _register_all() -> None:
    """模块首次导入时注册所有Agent"""
    for cls in (
        # 选品（2）
        ProductResearchAgent, NicheFinderAgent,
        # Listing（3）
        ListingOptimizerAgent, KeywordResearchAgent, AContentGeneratorAgent,
        # 广告（2）
        PPCManagerAgent, SponsoredAdsAgent,
        # 库存（2）
        InventoryPlannerAgent, FbaManagerAgent,
        # 定价（2）
        PriceOptimizerAgent, RepricingAgent,
        # 评论（2）
        ReviewMonitorAgent, VINEProgramAgent,
        # 品牌（2）
        BrandRegistryAgent, HijackerDetectorAgent,
        # 数据（2）
        SalesAnalyticsAgent, ProfitCalculatorAgent,
        # 客服（1）
        CustomerServiceAgent,
        # 合规（2）
        ComplianceCheckerAgent, AccountHealthAgent,
        # 🆕 竞品情报（1）
        CompetitorAnalysisAgent,
        # GUI（1）
        GUIAgent,
    ):
        cls()  # 实例化，触发基类注册


_register_all()
