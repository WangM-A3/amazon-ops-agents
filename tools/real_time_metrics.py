"""
tools/real_time_metrics.py
==========================
实时指标计算 — 支撑ProfitOptimizer实时竞价决策

核心功能:
  1. 实时聚合：ACOS/TACOS/ROAS/CTR/CVR滚动窗口
  2. 趋势检测：偏离告警（ACOS飙升/预算耗尽）
  3. 竞价建议：基于ProfitMarketCurve的实时出价推荐
  4. ProfitOptimizer推送：实时推送最新指标

Author: 硅基军团 · AMS数据接入 Agent
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx
import numpy as np

logger = logging.getLogger("amazon_ops.realtime_metrics")

# ─── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass
class CampaignPerformance:
    """广告活动实时性能快照"""
    campaign_id: str
    campaign_name: str
    profile_id: str
    ad_type: str

    # 实时累计（当前窗口）
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    sales: float = 0.0
    orders: int = 0

    # 实时窗口配置
    window_minutes: int = 60

    # 计算属性
    ctr: float = 0.0
    cvr: float = 0.0
    cpc: float = 0.0
    acos: float = 0.0
    roas: float = 0.0
    taco: float = 0.0   # Total Advertising Cost of Sales（考虑归因窗口）

    # 趋势
    spend_pace: float = 0.0    # 预算消耗速度 ($/hr)
    daily_spend_pct: float = 0.0  # 当日预算消耗%
    budget: float = 0.0
    budget_exhaustion_eta: Optional[str] = None  # 预算耗尽预计时间

    # 告警标志
    acos_spike: bool = False
    budget_warning: bool = False
    budget_critical: bool = False  # >90% 消耗

    # 上下文
    last_updated: float = field(default_factory=time.time)
    data_points: int = 0   # 累积数据点（用于置信度）

    def compute(self):
        """重新计算派生字段"""
        if self.impressions > 0:
            self.ctr = round(self.clicks / self.impressions, 6)
        if self.clicks > 0:
            self.cvr = round(self.orders / self.clicks, 4)
            self.cpc = round(self.spend / self.clicks, 4)
        if self.spend > 0:
            if self.sales > 0:
                self.acos = round(self.spend / self.sales, 6)
                self.roas = round(self.sales / self.spend, 4)
            if self.taco > 0:
                pass  # taco由上游传入
        if self.budget > 0:
            self.daily_spend_pct = round(self.spend / self.budget, 4)
            hours_elapsed = (time.time() - self.last_updated) / 3600 + 0.01
            self.spend_pace = round(self.spend / hours_elapsed, 4)
            remaining = self.budget - self.spend
            if self.spend_pace > 0 and remaining > 0:
                eta_hours = remaining / self.spend_pace
                eta = datetime.now(timezone.utc) + timedelta(hours=eta_hours)
                self.budget_exhaustion_eta = eta.strftime("%H:%M")
            self.budget_warning = self.daily_spend_pct > 0.75
            self.budget_critical = self.daily_spend_pct > 0.90


@dataclass
class KeywordPerformance:
    """关键词实时性能"""
    keyword_id: str
    campaign_id: str
    keyword_text: str
    match_type: str
    profile_id: str

    # 指标
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    sales: float = 0.0
    orders: int = 0
    current_bid: float = 0.0

    # 计算
    ctr: float = 0.0
    cvr: float = 0.0
    acos: float = 0.0
    roas: float = 0.0
    cpc: float = 0.0

    # 状态
    state: str = "enabled"
    acos_spike: bool = False
    acos_target: float = 0.25  # 目标ACOS

    last_updated: float = field(default_factory=time.time)

    def compute(self):
        if self.impressions > 0:
            self.ctr = round(self.clicks / self.impressions, 6)
        if self.clicks > 0:
            self.cvr = round(self.orders / self.clicks, 4)
            self.cpc = round(self.spend / self.clicks, 4)
        if self.sales > 0:
            self.acos = round(self.spend / self.sales, 6)
            self.roas = round(self.sales / self.spend, 4)
        if self.acos > 0 and self.acos_target > 0:
            self.acos_spike = self.acos > self.acos_target * 1.2


@dataclass
class BidRecommendation:
    """竞价调整建议"""
    keyword_id: str
    campaign_id: str
    current_bid: float
    recommended_bid: float
    bid_change_pct: float
    confidence: float
    reason: str
    expected_acos: float
    expected_roas: float
    priority: str = "normal"   # low | normal | high | urgent
    estimated_impact: str = ""
    generated_at: float = field(default_factory=time.time)


# ─── 实时指标引擎 ─────────────────────────────────────────────────────────────

class RealTimeMetricsEngine:
    """
    实时指标计算引擎

    功能:
    - 滚动时间窗口聚合
    - 多账户/多Profile并发管理
    - 告警状态跟踪
    - ProfitOptimizer推送接口

    Usage:
        engine = RealTimeMetricsEngine(config)
        engine.update_campaign_metrics(profile_id, [campaign_data])
        snapshot = engine.get_snapshot()
        alerts   = engine.get_alerts()
    """

    def __init__(self, config, profit_optimizer=None):
        """
        Args:
            config: AMSConfig
            profit_optimizer: ProfitOptimizer实例（可选，用于生成竞价建议）
        """
        self.config = config
        self.profit_optimizer = profit_optimizer

        # 滚动窗口存储 {profile_id: {campaign_id: deque[CampaignPerformance]}}
        self._campaign_windows: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=1000)))
        # {profile_id: {keyword_id: deque[KeywordPerformance]}}
        self._keyword_windows: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=500)))

        # 最新快照（从滚动窗口聚合）
        self._campaign_snapshots: dict[str, dict[str, CampaignPerformance]] = defaultdict(dict)
        self._keyword_snapshots: dict[str, dict[str, KeywordPerformance]] = defaultdict(dict)

        # 告警队列
        self._alerts: list[dict[str, Any]] = []
        self._alert_lock = asyncio.Lock()

        # 统计
        self.total_updates = 0
        self.last_aggregation: float = 0.0
        self.update_latency_ms: float = 0.0

    # ── 数据更新 ──────────────────────────────────────────────────────────────

    def update_campaign_metrics(
        self,
        profile_id: str,
        metrics,           # list[CampaignMetrics]
        window_minutes: int = 60,
    ):
        """更新广告活动指标（从AMS客户端接收）"""
        from tools.ams_client import CampaignMetrics as AMCampaignMetrics

        t0 = time.time()
        for raw in metrics:
            if not isinstance(raw, AMCampaignMetrics):
                continue

            cid = raw.campaign_id
            window = self._campaign_windows[profile_id][cid]

            # 聚合到当前窗口
            snapshot = self._campaign_snapshots[profile_id].get(cid)
            if snapshot is None:
                snapshot = CampaignPerformance(
                    campaign_id=cid,
                    campaign_name=raw.campaign_name,
                    profile_id=profile_id,
                    ad_type=raw.campaign_type.value,
                    budget=raw.budget,
                    window_minutes=window_minutes,
                )

            snapshot.impressions += raw.impressions
            snapshot.clicks      += raw.clicks
            snapshot.spend        += raw.spend
            snapshot.sales        += raw.sales
            snapshot.orders       += raw.orders
            snapshot.status        = raw.status
            snapshot.last_updated  = raw.fetched_at
            snapshot.data_points  += 1

            # 保持budget（取最新值）
            if raw.budget > 0:
                snapshot.budget = raw.budget

            snapshot.compute()
            self._campaign_snapshots[profile_id][cid] = snapshot

            # 存入滚动窗口
            window.append(snapshot)

            # 告警检测
            self._check_campaign_alerts(snapshot)

        self.total_updates += 1
        self.last_aggregation = time.time()
        self.update_latency_ms = round((time.time() - t0) * 1000, 2)

    def update_keyword_metrics(
        self,
        profile_id: str,
        metrics,            # list[KeywordMetrics]
        window_minutes: int = 30,
    ):
        """更新关键词指标"""
        from tools.ams_client import KeywordMetrics as AMKeywordMetrics

        for raw in metrics:
            if not isinstance(raw, AMKeywordMetrics):
                continue

            kid = raw.keyword_id
            snapshot = self._keyword_snapshots[profile_id].get(kid)
            if snapshot is None:
                snapshot = KeywordPerformance(
                    keyword_id=kid,
                    campaign_id=raw.campaign_id,
                    keyword_text=raw.keyword_text,
                    match_type=raw.match_type,
                    profile_id=profile_id,
                    current_bid=raw.current_bid,
                    state=raw.state,
                    window_minutes=window_minutes,
                )

            snapshot.impressions += raw.impressions
            snapshot.clicks      += raw.clicks
            snapshot.spend       += raw.spend
            snapshot.sales       += raw.sales
            snapshot.orders      += raw.orders
            snapshot.last_updated = raw.fetched_at

            if raw.current_bid > 0:
                snapshot.current_bid = raw.current_bid

            snapshot.compute()
            self._keyword_snapshots[profile_id][kid] = snapshot

            # 关键词ACOS告警
            if snapshot.acos_spike:
                asyncio.create_task(self._emit_alert({
                    "type": "KEYWORD_ACOS_SPIKE",
                    "keyword_id": kid,
                    "campaign_id": raw.campaign_id,
                    "acos": round(snapshot.acos, 4),
                    "acos_target": snapshot.acos_target,
                    "message": f"关键词 [{snapshot.keyword_text}] ACOS={snapshot.acos:.1%}，超过目标{snapshot.acos_target:.1%}的20%",
                    "severity": "warning",
                    "timestamp": time.time(),
                }))

    def update_stream_events(self, profile_id: str, events):
        """
        更新Marketing Stream事件（增量聚合）

        事件类型: IMPRESSION | CLICK | CONVERSION
        用于超低延迟（秒级）指标更新
        """
        from tools.ams_client import StreamEvent

        for raw in events:
            if not isinstance(raw, StreamEvent):
                continue

            cid = raw.campaign_id
            snapshot = self._campaign_snapshots[profile_id].get(cid)
            if snapshot is None:
                continue  # 尚未初始化，等待完整拉取

            if raw.event_type == "IMPRESSION":
                snapshot.impressions += 1
            elif raw.event_type == "CLICK":
                snapshot.clicks += 1
                snapshot.spend  += raw.cost
            elif raw.event_type == "CONVERSION":
                snapshot.orders += 1
                snapshot.sales  += raw.value

            snapshot.compute()

    # ── 告警 ─────────────────────────────────────────────────────────────────

    def _check_campaign_alerts(self, snap: CampaignPerformance):
        """检测广告活动告警"""
        alerts: list[dict] = []

        # ACOS飙升（超过目标的150%）
        target_acos = 0.25  # 默认目标
        if snap.acos > target_acos * 1.5 and snap.spend > 10:
            alerts.append({
                "type": "CAMPAIGN_ACOS_SPIKE",
                "campaign_id": snap.campaign_id,
                "acos": round(snap.acos, 4),
                "acos_target": target_acos,
                "message": f"广告活动 [{snap.campaign_name}] ACOS={snap.acos:.1%}，超过目标25%的50%",
                "severity": "critical" if snap.acos > target_acos * 2 else "warning",
                "timestamp": time.time(),
            })

        # 预算告警
        if snap.budget_critical:
            alerts.append({
                "type": "BUDGET_CRITICAL",
                "campaign_id": snap.campaign_id,
                "spend_pct": round(snap.daily_spend_pct, 4),
                "message": f"广告活动 [{snap.campaign_name}] 预算消耗{snap.daily_spend_pct:.0%}，即将耗尽",
                "severity": "critical",
                "timestamp": time.time(),
            })
        elif snap.budget_warning:
            alerts.append({
                "type": "BUDGET_WARNING",
                "campaign_id": snap.campaign_id,
                "spend_pct": round(snap.daily_spend_pct, 4),
                "message": f"广告活动 [{snap.campaign_name}] 预算消耗{snap.daily_spend_pct:.0%}",
                "severity": "info",
                "timestamp": time.time(),
            })

        # 低ROAS（<1.0意味着亏损）
        if snap.roas > 0 and snap.roas < 1.0 and snap.spend > 5:
            alerts.append({
                "type": "CAMPAIGN_UNPROFITABLE",
                "campaign_id": snap.campaign_id,
                "roas": round(snap.roas, 4),
                "message": f"广告活动 [{snap.campaign_name}] ROAS={snap.roas:.2f}<1.0，广告亏损",
                "severity": "warning",
                "timestamp": time.time(),
            })

        for alert in alerts:
            asyncio.create_task(self._emit_alert(alert))

    async def _emit_alert(self, alert: dict):
        async with self._alert_lock:
            self._alerts.append(alert)
            # 保留最近1000条
            if len(self._alerts) > 1000:
                self._alerts = self._alerts[-1000:]

        logger.warning(f"[告警] {alert['type']} | {alert.get('message', '')}")

    async def get_alerts(self, since: float = 0) -> list[dict]:
        """获取告警列表"""
        async with self._alert_lock:
            return [a for a in self._alerts if a["timestamp"] > since]

    # ── 快照 ─────────────────────────────────────────────────────────────────

    def get_snapshot(
        self,
        profile_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        获取当前实时快照

        Args:
            profile_id: 过滤指定Profile
            campaign_id: 过滤指定Campaign

        Returns:
            包含campaigns/keywords/aggregates/alerts的字典
        """
        snapshots = self._campaign_snapshots

        if profile_id:
            profiles = [profile_id]
        else:
            profiles = list(snapshots.keys())

        campaigns_out = []
        for pid in profiles:
            cs = snapshots[pid]
            if campaign_id:
                c = cs.get(campaign_id)
                if c:
                    campaigns_out.append(self._campaign_to_dict(c))
            else:
                for c in cs.values():
                    campaigns_out.append(self._campaign_to_dict(c))

        # 聚合指标
        aggregates = self._compute_aggregates(campaigns_out)

        return {
            "campaigns": campaigns_out,
            "keywords": self._get_keywords_snapshot(profile_id),
            "aggregates": aggregates,
            "fetched_at": time.time(),
            "data_sources": profiles,
        }

    def _campaign_to_dict(self, c: CampaignPerformance) -> dict:
        return {
            "campaign_id": c.campaign_id,
            "campaign_name": c.campaign_name,
            "profile_id": c.profile_id,
            "ad_type": c.ad_type,
            "impressions": c.impressions,
            "clicks": c.clicks,
            "spend": round(c.spend, 4),
            "sales": round(c.sales, 4),
            "orders": c.orders,
            "ctr": c.ctr,
            "cvr": c.cvr,
            "cpc": c.cpc,
            "acos": c.acos,
            "roas": c.roas,
            "taco": c.taco,
            "budget": round(c.budget, 2),
            "daily_spend_pct": c.daily_spend_pct,
            "budget_exhaustion_eta": c.budget_exhaustion_eta,
            "acos_spike": c.acos_spike,
            "budget_warning": c.budget_warning,
            "budget_critical": c.budget_critical,
            "data_points": c.data_points,
            "last_updated": datetime.fromtimestamp(c.last_updated, tz=timezone.utc).isoformat(),
        }

    def _get_keywords_snapshot(self, profile_id: Optional[str]) -> list[dict]:
        snapshots = self._keyword_snapshots
        if profile_id:
            kws = snapshots.get(profile_id, {}).values()
        else:
            kws = [kw for ks in snapshots.values() for kw in ks.values()]
        return [{
            "keyword_id": k.keyword_id,
            "campaign_id": k.campaign_id,
            "keyword_text": k.keyword_text,
            "match_type": k.match_type,
            "profile_id": k.profile_id,
            "impressions": k.impressions,
            "clicks": k.clicks,
            "spend": round(k.spend, 4),
            "sales": round(k.sales, 4),
            "orders": k.orders,
            "ctr": k.ctr,
            "cvr": k.cvr,
            "acos": k.acos,
            "roas": k.roas,
            "cpc": k.cpc,
            "current_bid": round(k.current_bid, 4),
            "acos_spike": k.acos_spike,
            "state": k.state,
            "last_updated": datetime.fromtimestamp(k.last_updated, tz=timezone.utc).isoformat(),
        } for k in kws]

    def _compute_aggregates(self, campaigns: list[dict]) -> dict:
        if not campaigns:
            return {}

        total_impressions = sum(c["impressions"] for c in campaigns)
        total_clicks       = sum(c["clicks"]       for c in campaigns)
        total_spend        = sum(c["spend"]        for c in campaigns)
        total_sales        = sum(c["sales"]        for c in campaigns)
        total_orders       = sum(c["orders"]       for c in campaigns)
        total_budget       = sum(c["budget"]       for c in campaigns)

        return {
            "total_campaigns": len(campaigns),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_spend": round(total_spend, 4),
            "total_sales": round(total_sales, 4),
            "total_orders": total_orders,
            "total_budget": round(total_budget, 2),
            "budget_utilization": round(total_spend / max(total_budget, 0.01), 4),
            "ctr": round(total_clicks / max(total_impressions, 1), 6),
            "cvr": round(total_orders / max(total_clicks, 1), 4),
            "acos": round(total_spend / max(total_sales, 0.01), 6),
            "roas": round(total_sales / max(total_spend, 0.01), 4),
            "avg_cpc": round(total_spend / max(total_clicks, 1), 4),
        }

    # ── 竞价建议 ──────────────────────────────────────────────────────────────

    def generate_bid_recommendations(
        self,
        profile_id: str,
        top_n: int = 50,
        target_acos: float = 0.25,
    ) -> list[BidRecommendation]:
        """
        基于ProfitOptimizer生成竞价调整建议

        策略：
        1. ACOS过高的关键词 → 建议降Bid（保护利润）
        2. ACOS过低但曝光不足 → 建议升Bid（扩大规模）
        3. 新关键词（数据少） → 低置信度建议
        """
        if self.profit_optimizer is None:
            # 无ProfitOptimizer时，使用简单的ACOS规则
            return self._simple_bid_recommendations(profile_id, top_n, target_acos)

        recommendations = []
        keywords = list(self._keyword_snapshots.get(profile_id, {}).values())

        # 按spend排序，取top_n
        keywords.sort(key=lambda k: k.spend, reverse=True)
        keywords = keywords[:top_n]

        for kw in keywords:
            if kw.clicks < 5:
                continue  # 数据太少

            # 构建BidRecord用于ProfitOptimizer
            from execution.profit_optimizer import BidRecord
            record = BidRecord(
                bid=kw.current_bid,
                impressions=kw.impressions,
                clicks=kw.clicks,
                spend=kw.spend,
                sales=kw.sales,
                orders=kw.orders,
            )

            # 拟合曲线（使用历史数据窗口）
            window = self._keyword_windows.get(profile_id, {}).get(kw.keyword_id, deque())
            if len(window) >= 2:
                history = [
                    BidRecord(
                        bid=max(w.current_bid, 0.01),
                        impressions=w.impressions,
                        clicks=w.clicks,
                        spend=w.spend,
                        sales=w.sales,
                        orders=w.orders,
                    )
                    for w in list(window)[-10:]
                ]
                curve = self.profit_optimizer.fit_curve(history)
                result = self.profit_optimizer.find_optimal_bid(
                    curve, target_acos=target_acos,
                )

                change_pct = (result.optimal_bid - kw.current_bid) / max(kw.current_bid, 0.01)
                confidence = result.confidence
            else:
                # 数据不足，使用简单规则
                result = None
                change_pct = self._simple_change(kw, target_acos)
                confidence = min(kw.clicks / 100, 0.5)  # 数据量折扣

            if abs(change_pct) < 0.03:
                continue  # 变化<3%，跳过

            recommended_bid = round(kw.current_bid * (1 + change_pct), 4)
            recommended_bid = max(0.02, min(recommended_bid, 10.0))  # 限幅

            reason = self._build_reason(kw, change_pct, result)
            priority = "urgent" if abs(change_pct) > 0.3 else "high" if abs(change_pct) > 0.15 else "normal"

            recommendations.append(BidRecommendation(
                keyword_id=kw.keyword_id,
                campaign_id=kw.campaign_id,
                current_bid=kw.current_bid,
                recommended_bid=recommended_bid,
                bid_change_pct=round(change_pct, 4),
                confidence=round(confidence, 4),
                reason=reason,
                expected_acos=round(result.expected_acos, 4) if result else 0.0,
                expected_roas=round(result.expected_roas, 4) if result else 0.0,
                priority=priority,
            ))

        # 按优先级排序
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        recommendations.sort(key=lambda r: (priority_order[r.priority], -abs(r.bid_change_pct)))

        return recommendations

    # ── 简单规则（无ProfitOptimizer时） ─────────────────────────────────────

    def _simple_bid_recommendations(
        self,
        profile_id: str,
        top_n: int = 50,
        target_acos: float = 0.25,
    ) -> list[BidRecommendation]:
        keywords = list(self._keyword_snapshots.get(profile_id, {}).values())
        keywords.sort(key=lambda k: k.spend, reverse=True)
        keywords = keywords[:top_n]

        recommendations = []
        for kw in keywords:
            if kw.clicks < 10:
                continue

            change_pct = self._simple_change(kw, target_acos)
            if abs(change_pct) < 0.03:
                continue

            recommended_bid = round(kw.current_bid * (1 + change_pct), 4)
            recommended_bid = max(0.02, min(recommended_bid, 10.0))

            reason = f"ACOS={kw.acos:.1%} vs 目标={target_acos:.1%}，"
            if change_pct < 0:
                reason += "建议降低出价减少花费"
            else:
                reason += "建议提高出价扩大曝光"

            confidence = min(kw.clicks / 200, 0.8)
            priority = "urgent" if abs(change_pct) > 0.3 else "high" if abs(change_pct) > 0.15 else "normal"

            recommendations.append(BidRecommendation(
                keyword_id=kw.keyword_id,
                campaign_id=kw.campaign_id,
                current_bid=kw.current_bid,
                recommended_bid=recommended_bid,
                bid_change_pct=round(change_pct, 4),
                confidence=round(confidence, 4),
                reason=reason,
                expected_acos=0.0,
                expected_roas=0.0,
                priority=priority,
            ))

        return recommendations

    def _simple_change(self, kw: KeywordPerformance, target_acos: float) -> float:
        """ACOS目标规则计算Bid调整幅度"""
        if kw.acos <= 0 or kw.current_bid <= 0:
            return 0.0

        # ACOS过高 → 降Bid（比例调整）
        if kw.acos > target_acos:
            overshoot = kw.acos / max(target_acos, 0.001) - 1
            return max(-0.5, -min(overshoot * 0.5, 0.5))  # 最多降50%

        # ACOS过低且曝光少 → 升Bid
        if kw.acos < target_acos * 0.7 and kw.impressions < 1000:
            undershoot = 1 - kw.acos / max(target_acos, 0.001)
            return min(0.3, undershoot * 0.5)

        return 0.0

    def _build_reason(self, kw: KeywordPerformance, change_pct: float, result) -> str:
        if result:
            return (
                f"ProfitOptimizer模型(R²={result.curve.r_squared:.2f})推荐: "
                f"当前ACOS={kw.acos:.1%} → 预期ACOS={result.expected_acos:.1%}"
            )
        return f"基于ACOS规则({kw.acos:.1%} vs 25%目标)"

    # ── ProfitOptimizer推送 ───────────────────────────────────────────────────

    async def push_to_optimizer(self) -> dict[str, Any]:
        """推送实时指标到ProfitOptimizer端点"""
        endpoint = self.config.pipeline.optimizer_endpoint

        snapshot = self.get_snapshot()
        aggregates = snapshot["aggregates"]

        payload = {
            "source": "AMSRealTimeMetrics",
            "timestamp": time.time(),
            "aggregates": aggregates,
            "alert_count": len(self._alerts[-100:]),
        }

        if aggregates:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(endpoint, json=payload)
                    resp.raise_for_status()
                    logger.info(f"ProfitOptimizer推送成功: ACOS={aggregates.get('acos', 0):.4f}")
                    return {"status": "success", "acos": aggregates.get("acos", 0)}
            except Exception as e:
                logger.warning(f"ProfitOptimizer推送失败: {e}")
                return {"status": "error", "error": str(e)}

        return {"status": "skipped", "reason": "no_data"}

    # ── 健康状态 ─────────────────────────────────────────────────────────────

    @property
    def health(self) -> dict[str, Any]:
        return {
            "total_updates": self.total_updates,
            "campaigns_tracked": sum(len(cs) for cs in self._campaign_snapshots.values()),
            "keywords_tracked": sum(len(ks) for ks in self._keyword_snapshots.values()),
            "alerts_pending": len(self._alerts),
            "last_aggregation": datetime.fromtimestamp(self.last_aggregation, tz=timezone.utc).isoformat() if self.last_aggregation else None,
            "update_latency_ms": self.update_latency_ms,
        }
