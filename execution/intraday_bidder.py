"""
execution/intraday_bidder.py
============================
IntradayBidder — 日内动态出价引擎

核心思想
--------
传统 PPC 策略「一天只调一次」，Adspert 的护城河在于「一天多次动态调价」：

    传统:  T=00:00  set_bid($1.20)  ← 全天不变
    Intraday: 每小时评估 → 动态调整 → 紧贴实时竞争

为什么有效？
- 亚马逊竞价系统 24h 实时拍卖，不同时段竞争强度不同
- 晚间（美国西部）竞争降低 30-40%，低出价也能拿到好位置
- 高峰时段（美国东部 9-11am ET）竞争激烈，需要溢价争抢

时段调价策略
------------
| 时段 (ET)        | 竞争强度 | 建议调整      | 原因              |
|-----------------|----------|---------------|-------------------|
| 00:00 - 05:00   | 极低     | -20% ~ -30%   | 美国深夜/亚太白天 |
| 05:00 - 07:00   | 低       | -10% ~ -20%   | 美国凌晨          |
| 07:00 - 09:00   | 上升     | ±0%           | 卖家开始上班      |
| 09:00 - 11:00   | 极高     | +15% ~ +25%   | 美国上午高峰      |
| 11:00 - 13:00   | 高       | +5% ~ +15%    | 维持              |
| 13:00 - 15:00   | 中       | ±0%           | 下午平稳          |
| 15:00 - 18:00   | 上升     | +5% ~ +10%    | 美国晚间购物      |
| 18:00 - 21:00   | 极高     | +10% ~ +20%   | 最高转化时段      |
| 21:00 - 24:00   | 下降     | -10% ~ -20%   | 流量开始回落      |

三层决策机制
------------
Layer 1 — 时段基础调整（ScheduleRule）
    基于美国东部时间（ET）的基础出价修正

Layer 2 — 实时表现调整（PerformanceRule）
    基于小时级 KPI（CTR/CVR/ACOS）动态修正

Layer 3 — 竞品超调（CompetitionRule）
    检测到竞品活动时触发紧急竞价调整

Author: 硅基军团 · 广告优化 Agent
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger("amazon_ops.intraday_bidder")


# ─── 数据模型 ─────────────────────────────────────────────────────────────────

class TimeSlot(str, Enum):
    """ET 时段枚举"""
    DEEP_NIGHT   = "deep_night"   # 00-05
    EARLY_MORNING= "early_morning" # 05-07
    MORNING_RAMP = "morning_ramp"  # 07-09
    PEAK_AM      = "peak_am"       # 09-11
    LUNCH        = "lunch"         # 11-13
    AFTERNOON    = "afternoon"     # 13-15
    LATE_AFTERNOON = "late_afternoon" # 15-18
    PEAK_EVE     = "peak_evening"  # 18-21
    NIGHT_WINDOWN = "night_window"  # 21-24


class MarketSession(str, Enum):
    """市场活跃度"""
    ULTRA_LOW = "ultra_low"
    LOW       = "low"
    NORMAL    = "normal"
    HIGH      = "high"
    ULTRA_HIGH = "ultra_high"


@dataclass
class HourlyPerformance:
    """小时级绩效数据"""
    hour_et:            int     # 美国东部时间（0-23）
    impressions:        int     # 曝光数
    clicks:             int     # 点击数
    spend:              float   # 花费（美元）
    sales:              float   # 销售额（美元）
    orders:             int     # 订单数

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions > 0 else 0.0

    @property
    def cvr(self) -> float:
        return self.orders / self.clicks if self.clicks > 0 else 0.0

    @property
    def acos(self) -> float:
        return self.spend / self.sales if self.sales > 0 else 0.0

    @property
    def cpc(self) -> float:
        return self.clicks / self.spend if self.spend > 0 else 0.0

    @property
    def roas(self) -> float:
        return self.sales / self.spend if self.spend > 0 else 0.0


@dataclass
class BidAdjustment:
    """单次出价调整指令"""
    keyword:          str
    current_bid:      float
    new_bid:          float
    adjustment_pct:   float   # 变化百分比
    trigger_reason:   str    # 触发原因
    layer:            str    # "schedule" | "performance" | "competition"
    confidence:       float


@dataclass
class IntradaySession:
    """一轮日内调价会话"""
    timestamp_utc: str
    timezone:      str = "ET"   # 美国东部时间
    adjustments:   list[BidAdjustment] = field(default_factory=list)
    session_acos:  float = 0.0
    market_session: MarketSession = MarketSession.NORMAL

    def summary(self) -> str:
        n = len(self.adjustments)
        ups = sum(1 for a in self.adjustments if a.adjustment_pct > 0)
        downs = sum(1 for a in self.adjustments if a.adjustment_pct < 0)
        return (
            f"[Intraday Session {self.timestamp_utc}] "
            f"调整 {n} 个关键词 | "
            f"↑{ups} ↓{downs} | "
            f"ACOS={self.session_acos:.1%} | "
            f"市场={self.market_session.value}"
        )


# ─── 时段规则库 ───────────────────────────────────────────────────────────────

# 时段 → 基础调整系数（相对于基准出价的倍数）
# >1.0 = 加价，<1.0 = 降价
TIME_SLOT_RULES: dict[TimeSlot, float] = {
    TimeSlot.DEEP_NIGHT:    0.75,   # -25%
    TimeSlot.EARLY_MORNING: 0.85,   # -15%
    TimeSlot.MORNING_RAMP:  0.98,   # -2%
    TimeSlot.PEAK_AM:       1.20,   # +20%
    TimeSlot.LUNCH:         1.10,   # +10%
    TimeSlot.AFTERNOON:     1.00,   # ±0%
    TimeSlot.LATE_AFTERNOON: 1.08,  # +8%
    TimeSlot.PEAK_EVE:      1.18,   # +18%
    TimeSlot.NIGHT_WINDOWN: 0.88,   # -12%
}

# 时段 → 市场活跃度
SLOT_TO_SESSION: dict[TimeSlot, MarketSession] = {
    TimeSlot.DEEP_NIGHT:    MarketSession.ULTRA_LOW,
    TimeSlot.EARLY_MORNING: MarketSession.LOW,
    TimeSlot.MORNING_RAMP:  MarketSession.NORMAL,
    TimeSlot.PEAK_AM:       MarketSession.ULTRA_HIGH,
    TimeSlot.LUNCH:         MarketSession.HIGH,
    TimeSlot.AFTERNOON:     MarketSession.NORMAL,
    TimeSlot.LATE_AFTERNOON: MarketSession.HIGH,
    TimeSlot.PEAK_EVE:      MarketSession.ULTRA_HIGH,
    TimeSlot.NIGHT_WINDOWN: MarketSession.LOW,
}

# 性能超参数
PERFORMANCE_BOUNDS = {
    "acos": {"low": 0.15, "high": 0.35},   # 健康ACOS区间
    "ctr":  {"low": 0.02, "high": 0.10},   # 健康CTR区间
    "cvr":  {"low": 0.05, "high": 0.20},  # 健康CVR区间
}


# ─── 核心引擎 ─────────────────────────────────────────────────────────────────

class IntradayBidder:
    """
    日内动态出价引擎

    支持三种调用模式：
    1. full_evaluation:  综合三层决策（时段+表现+竞品）
    2. schedule_only:     仅时段调整（低开销）
    3. performance_only:  仅表现调整（快速响应）

    Example:
        bidder = IntradayBidder()
        session = bidder.adjust_bids(
            current_hour=10,   # ET时间 10点
            performance=[
                HourlyPerformance(hour_et=9, impressions=500, clicks=25, spend=12.5, sales=62.5, orders=2),
                HourlyPerformance(hour_et=10, impressions=600, clicks=30, spend=15.0, sales=50.0, orders=1),
            ],
            keywords={
                "wireless earbuds": 1.50,
                "bluetooth headphones": 2.00,
            },
        )
        print(session.summary())
    """

    def __init__(
        self,
        enable_performance_layer: bool = True,
        enable_competition_layer: bool = False,
        max_bid_change_pct: float = 0.30,   # 单次最大变化不超过30%
        min_bid_floor: float = 0.02,         # 最低出价 $0.02
        max_bid_cap: float = 10.0,           # 最高出价 $10
    ):
        """
        Args:
            enable_performance_layer: 是否启用表现层（L2）
            enable_competition_layer:  是否启用竞品层（L3）
            max_bid_change_pct:        单次最大调整幅度
            min_bid_floor:            出价下限
            max_bid_cap:              出价上限
        """
        self.enable_performance = enable_performance_layer
        self.enable_competition = enable_competition_layer
        self.max_change = max_bid_change_pct
        self.min_floor  = min_bid_floor
        self.max_cap    = max_bid_cap
        self._history: list[IntradaySession] = []

    # ── 公开 API ───────────────────────────────────────────────────────────────

    def adjust_bids(
        self,
        current_hour: int,
        performance: list[HourlyPerformance],
        keywords: dict[str, float],
        target_acos: float = 0.25,
        competition_boost: float = 0.0,  # 竞品活动加成
    ) -> IntradaySession:
        """
        执行日内出价调整

        Args:
            current_hour:     当前 ET 时间（0-23）
            performance:       最近 N 小时的表现数据
            keywords:          {关键词: 当前出价}
            target_acos:        目标 ACOS
            competition_boost: 竞品活动强度（0-1）

        Returns:
            IntradaySession: 包含所有调整指令的会话
        """
        now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        slot    = self._get_time_slot(current_hour)
        session = IntradaySession(
            timestamp_utc=now_str,
            market_session=SLOT_TO_SESSION.get(slot, MarketSession.NORMAL),
        )

        for keyword, current_bid in keywords.items():
            adj = self._calculate_adjustment(
                keyword=keyword,
                current_bid=current_bid,
                slot=slot,
                performance=performance,
                target_acos=target_acos,
                competition_boost=competition_boost,
            )
            session.adjustments.append(adj)

        # 更新会话级 ACOS
        if performance:
            total_spend = sum(p.spend for p in performance)
            total_sales = sum(p.sales for p in performance)
            session.session_acos = total_spend / total_sales if total_sales > 0 else 0.0

        self._history.append(session)
        logger.info(session.summary())
        return session

    def get_hourly_schedule(self) -> dict[int, float]:
        """
        返回 24h 出价倍数表（用于可视化/审核）
        """
        return {h: TIME_SLOT_RULES[self._get_time_slot(h)] for h in range(24)}

    def get_bid_recommendation(
        self,
        base_bid: float,
        hour_et: int,
    ) -> float:
        """
        给定基准出价，查询某小时的推荐出价（不含表现层）
        """
        slot = self._get_time_slot(hour_et)
        recommended = base_bid * TIME_SLOT_RULES[slot]
        return round(float(np.clip(recommended, self.min_floor, self.max_cap)), 2)

    def summary_report(self) -> dict:
        """生成日内调价摘要报告"""
        if not self._history:
            return {"status": "no_sessions", "message": "暂无调价记录"}

        all_adj = [adj for s in self._history for adj in s.adjustments]
        total_up   = sum(1 for a in all_adj if a.adjustment_pct > 0)
        total_down = sum(1 for a in all_adj if a.adjustment_pct < 0)
        total_same = sum(1 for a in all_adj if a.adjustment_pct == 0)
        avg_change = np.mean([abs(a.adjustment_pct) for a in all_adj]) if all_adj else 0.0

        return {
            "total_sessions":    len(self._history),
            "total_adjustments": len(all_adj),
            "bid_ups":           total_up,
            "bid_downs":         total_down,
            "bid_no_change":     total_same,
            "avg_change_pct":    round(avg_change, 4),
            "layer_breakdown":   self._layer_breakdown(all_adj),
        }

    # ─── 私有方法 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _get_time_slot(hour: int) -> TimeSlot:
        """映射小时到时段"""
        if   0  <= hour < 5:  return TimeSlot.DEEP_NIGHT
        elif 5  <= hour < 7:  return TimeSlot.EARLY_MORNING
        elif 7  <= hour < 9:  return TimeSlot.MORNING_RAMP
        elif 9  <= hour < 11: return TimeSlot.PEAK_AM
        elif 11 <= hour < 13: return TimeSlot.LUNCH
        elif 13 <= hour < 15: return TimeSlot.AFTERNOON
        elif 15 <= hour < 18: return TimeSlot.LATE_AFTERNOON
        elif 18 <= hour < 21: return TimeSlot.PEAK_EVE
        else:                  return TimeSlot.NIGHT_WINDOWN

    def _calculate_adjustment(
        self,
        keyword: str,
        current_bid: float,
        slot: TimeSlot,
        performance: list[HourlyPerformance],
        target_acos: float,
        competition_boost: float,
    ) -> BidAdjustment:
        """
        三层叠加出价计算

        公式：
            final_multiplier = L1(slot) × L2(performance) × L3(competition)
            new_bid = current_bid × final_multiplier
        """
        # ── Layer 1: 时段基础倍数 ─────────────────────────────────────────
        l1 = TIME_SLOT_RULES[slot]

        # ── Layer 2: 表现修正 ─────────────────────────────────────────────
        l2 = 1.0
        if self.enable_performance and performance:
            l2 = self._performance_multiplier(performance, target_acos)

        # ── Layer 3: 竞品加成 ─────────────────────────────────────────────
        l3 = 1.0
        if self.enable_competition and competition_boost > 0:
            l3 = 1.0 + competition_boost * 0.3   # 最多+30%

        # ── 合成倍数 ───────────────────────────────────────────────────────
        final_mult = l1 * l2 * l3
        new_bid    = current_bid * final_mult

        # ── 边界约束 ───────────────────────────────────────────────────────
        change_pct = (new_bid - current_bid) / current_bid
        if abs(change_pct) > self.max_change:
            new_bid = current_bid * (1.0 + self.max_change * (1 if change_pct > 0 else -1))

        new_bid = float(np.clip(new_bid, self.min_floor, self.max_cap))

        # ── 触发原因 ───────────────────────────────────────────────────────
        reasons = []
        if l1 != 1.0:
            direction = "↑" if l1 > 1.0 else "↓"
            reasons.append(f"L1时段{direction}{abs(l1-1):.0%}")
        if abs(l2 - 1.0) > 0.01:
            direction = "↑" if l2 > 1.0 else "↓"
            reasons.append(f"L2表现{direction}{abs(l2-1):.0%}")
        if competition_boost > 0:
            reasons.append(f"L3竞品+{competition_boost:.0%}")

        return BidAdjustment(
            keyword=keyword,
            current_bid=round(current_bid, 2),
            new_bid=round(new_bid, 2),
            adjustment_pct=round((new_bid - current_bid) / current_bid, 4),
            trigger_reason=" | ".join(reasons) if reasons else "无显著变化",
            layer="schedule" if l1 != 1.0 else "performance",
            confidence=0.85,
        )

    @staticmethod
    def _performance_multiplier(
        performance: list[HourlyPerformance],
        target_acos: float,
    ) -> float:
        """
        Layer 2: 基于最近表现计算出价修正系数

        规则：
        - ACOS < 目标:  小幅加价（抢夺更多流量）
        - ACOS > 目标:  小幅减价（控制成本）
        - CTR 异常:     调整（CTR过低可能是排名问题）
        - CVR 异常:     调整（可能是落地页问题）
        """
        if not performance:
            return 1.0

        # 取最近1-3小时平均
        recent = performance[-3:] if len(performance) >= 3 else performance
        avg_acos = np.mean([p.acos for p in recent if p.sales > 0]) or 0.0
        avg_ctr  = np.mean([p.ctr  for p in recent]) or 0.0
        avg_cvr  = np.mean([p.cvr  for p in recent]) or 0.0

        mult = 1.0

        # ── ACOS 反馈 ────────────────────────────────────────────────────
        bounds = PERFORMANCE_BOUNDS["acos"]
        if avg_acos > 0:
            if avg_acos < bounds["low"]:
                mult *= 1.08    # ACOS过低，有提价空间
            elif avg_acos > bounds["high"]:
                mult *= 0.92    # ACOS过高，收紧出价
            else:
                # 在目标区间，微调跟随市场
                deviation = (avg_acos - target_acos) / target_acos
                mult *= (1.0 - deviation * 0.5)

        # ── CTR 反馈（位置竞争信号）─────────────────────────────────────
        ctr_bounds = PERFORMANCE_BOUNDS["ctr"]
        if avg_ctr > 0:
            if avg_ctr < ctr_bounds["low"]:
                mult *= 1.05    # CTR低，可能排名靠后，加价争位置
            elif avg_ctr > ctr_bounds["high"]:
                mult *= 0.97    # CTR过高（可能是泛流量），适当降低

        # ── CVR 反馈 ──────────────────────────────────────────────────────
        cvr_bounds = PERFORMANCE_BOUNDS["cvr"]
        if avg_cvr > 0:
            if avg_cvr < cvr_bounds["low"]:
                mult *= 0.95    # CVR低，说明转化差，减少投入
            elif avg_cvr > cvr_bounds["high"]:
                mult *= 1.05    # CVR高，加大投入

        return float(np.clip(mult, 0.70, 1.30))

    @staticmethod
    def _layer_breakdown(adjustments: list[BidAdjustment]) -> dict[str, int]:
        """统计各层调整数量"""
        return {
            "schedule":     sum(1 for a in adjustments if a.layer == "schedule"),
            "performance": sum(1 for a in adjustments if a.layer == "performance"),
            "competition": sum(1 for a in adjustments if a.layer == "competition"),
        }


# ─── 定时任务生成器 ───────────────────────────────────────────────────────────

def generate_cron_schedule() -> list[dict]:
    """
    生成 Intraday 调价 Cron 表（每小时执行一次）

    Returns:
        list of {"hour_et": int, "action": str, "description": str}
    """
    schedule = []
    for h in range(24):
        slot = IntradayBidder._get_time_slot(h)
        mult = TIME_SLOT_RULES[slot]
        direction = "↑加价" if mult > 1.0 else "↓降价" if mult < 1.0 else "→持稳"
        schedule.append({
            "hour_et": h,
            "slot": slot.value,
            "multiplier": mult,
            "action": direction,
            "description": _SLOT_DESCRIPTIONS[slot],
        })
    return schedule


_SLOT_DESCRIPTIONS = {
    TimeSlot.DEEP_NIGHT:    "美国深夜，亚太主导，竞争极低，大幅降出价",
    TimeSlot.EARLY_MORNING: "美国凌晨，缓慢抬升",
    TimeSlot.MORNING_RAMP:  "卖家上班，竞争开始升温",
    TimeSlot.PEAK_AM:       "美国上午购物高峰（9-11 ET），最高溢价",
    TimeSlot.LUNCH:         "午间平稳，保持溢价",
    TimeSlot.AFTERNOON:     "下午正常流量",
    TimeSlot.LATE_AFTERNOON:"晚间前奏，流量上升",
    TimeSlot.PEAK_EVE:      "美国晚间黄金时段（18-21 ET），最高转化",
    TimeSlot.NIGHT_WINDOWN: "流量回落，逐步降出价",
}


# ─── 快速入口 ─────────────────────────────────────────────────────────────────

def quick_intraday(
    keywords: dict[str, float],
    hour_et: int,
    performance: Optional[list[HourlyPerformance]] = None,
    target_acos: float = 0.25,
) -> IntradaySession:
    """
    一行执行日内调价

    Example:
        session = quick_intraday(
            keywords={"wireless earbuds": 1.50, "bluetooth headphones": 2.00},
            hour_et=10,
            target_acos=0.25,
        )
        for adj in session.adjustments:
            print(f"{adj.keyword}: ${adj.current_bid:.2f} → ${adj.new_bid:.2f} ({adj.adjustment_pct:+.0%})")
    """
    bidder = IntradayBidder()
    return bidder.adjust_bids(
        current_hour=hour_et,
        performance=performance or [],
        keywords=keywords,
        target_acos=target_acos,
    )
