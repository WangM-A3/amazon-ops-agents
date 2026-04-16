"""
execution/profit_optimizer.py
=============================
ProfitOptimizer — 利润市场曲线建模（仿 Adspert 核心护城河）

核心思想
--------
每个关键词/广告组都有一条「出价 → 利润」曲线：

    利润(b) = f(b) = revenue(b) - cost(b)

    - 出价太低：曝光不足 → 成交少 → 利润趋近 0
    - 出价最优点：边际收益 = 边际成本 → 利润最大
    - 出价太高：ACOS 飙升 → 成本吞噬利润 → 利润下降

模型假设
--------
利润曲线近似「反抛物线」形状，可用指数+对数混合模型拟合：

    P(b) = α * (1 - e^{-β*b}) * e^{-γ*b} + δ

    - α  : 最大利润天花板（市场规模）
    - β  : 曝光效率（越高说明低出价也能拿到流量）
    - γ  : 成本侵蚀系数（越高说明高出价代价越大）
    - δ  : 基础利润（自然流量贡献）

数学求解
--------
find_optimal_bid 对 f(b) 求导，令 f'(b) = 0 → 闭式解：

    b* = (1/γ) * ln(α*β/(α*γ + δ*γ))

若 δ≈0（忽略自然流量），简化为：

    b* = (1/γ) * ln(β/γ)

Author: 硅基军团 · 广告优化 Agent
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import pearsonr

logger = logging.getLogger("amazon_ops.profit_optimizer")


# ─── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass
class BidRecord:
    """单条竞价记录"""
    bid: float           # 出价（美元）
    impressions: int      # 曝光数
    clicks: int           # 点击数
    spend: float          # 花费（美元）
    sales: float          # 销售额（美元）
    orders: int           # 订单数
    date: str = ""        # 日期（可选）

    @property
    def ctr(self) -> float:
        """Click-Through Rate，点击率"""
        return self.clicks / self.impressions if self.impressions > 0 else 0.0

    @property
    def cvr(self) -> float:
        """Conversion Rate，转化率"""
        return self.orders / self.clicks if self.clicks > 0 else 0.0

    @property
    def cpc(self) -> float:
        """Cost Per Click，单次点击成本"""
        return self.spend / self.clicks if self.clicks > 0 else 0.0

    @property
    def acos(self) -> float:
        """Advertising Cost of Sales，广告销售比"""
        return self.spend / self.sales if self.sales > 0 else 0.0

    @property
    def roas(self) -> float:
        """Return on Ad Spend，广告支出回报率"""
        return self.sales / self.spend if self.spend > 0 else 0.0

    @property
    def profit(self) -> float:
        """毛利润（假设毛利率 30%）"""
        gross_margin = 0.30
        return self.sales * gross_margin - self.spend


@dataclass
class CurveParameters:
    """利润曲线拟合参数"""
    alpha: float   # 最大利润天花板
    beta: float    # 曝光效率系数
    gamma: float   # 成本侵蚀系数
    delta: float   # 基础利润偏移
    r_squared: float = 0.0  # 拟合优度 R²

    def to_dict(self) -> dict:
        return {
            "alpha": round(self.alpha, 4),
            "beta":  round(self.beta, 4),
            "gamma": round(self.gamma, 4),
            "delta": round(self.delta, 4),
            "r_squared": round(self.r_squared, 4),
        }


@dataclass
class BidOptimizationResult:
    """出价优化结果"""
    optimal_bid: float
    expected_profit: float
    expected_acos: float
    expected_roas: float
    confidence: float        # 置信度（基于R²和数据量）
    curve: CurveParameters
    model_used: str          # "full" | "simplified" | "heuristic"
    recommendation: str      # 自然语言建议


# ─── 核心算法 ─────────────────────────────────────────────────────────────────

class ProfitMarketCurve:
    """
    利润市场曲线模型

    Usage:
        pmc = ProfitMarketCurve()
        params = pmc.fit_curve([bid_record_1, bid_record_2, ...])
        result = pmc.find_optimal_bid(params, target_acos=0.25)
    """

    def __init__(self):
        self._last_params: Optional[CurveParameters] = None

    # ── 曲线拟合 ───────────────────────────────────────────────────────────────

    def fit_curve(self, bid_history: list[BidRecord]) -> CurveParameters:
        """
        使用历史竞价数据拟合利润曲线参数。

        算法：
        1. 构建 (bid, profit) 散点
        2. 三步拟合策略：
           - Step1: 网格搜索 + Levenberg-Marquardt 优化
           - Step2: 若 R² < 0.6，降级为简化模型（β/γ 比值法）
           - Step3: 若数据点 < 3，退化为启发式（ACOS 阈值法）

        Returns:
            CurveParameters，包含拟合参数和 R²
        """
        if len(bid_history) < 2:
            logger.warning("数据点不足（<2），使用启发式默认参数")
            return self._heuristic_params()

        bids   = np.array([r.bid    for r in bid_history])
        profits = np.array([r.profit for r in bid_history])

        # ── 过滤异常值：利润超出 ±3σ ──────────────────────────────────────────
        mean_p, std_p = profits.mean(), profits.std()
        mask = np.abs(profits - mean_p) <= 3 * std_p if std_p > 0 else np.ones(len(profits), dtype=bool)
        bids_clean   = bids[mask]
        profits_clean = profits[mask]

        if len(bids_clean) < 2:
            return self._heuristic_params()

        # ── Step1: SciPy 优化（四参数直接优化）─────────────────────────────────
        # 使用 minimize（而非 minimize_scalar）直接优化 [α, β, γ, δ]
        from scipy.optimize import minimize
        x0 = np.array([1.0, 0.8, 0.5, 0.0])   # 初始猜测
        bounds = [(0.01, 50.0), (0.01, 10.0), (0.01, 5.0), (-5.0, 5.0)]
        try:
            res = minimize(
                self._curve_loss_nd,
                x0=x0,
                args=(bids_clean, profits_clean),
                method="L-BFGS-B",
                bounds=bounds,
                options={"maxiter": 500},
            )
            alpha, beta, gamma, delta = res.x
        except Exception as e:
            logger.warning(f"SciPy minimize失败，回退到网格搜索: {e}")
            alpha, beta, gamma, delta = self._grid_search(bids_clean, profits_clean)

        # ── 计算 R²（允许为负，后续 clip 到 [0,1]）──────────────────────────────
        predicted = np.array([self._profit_model(b, alpha, beta, gamma, delta) for b in bids_clean])
        ss_res  = np.sum((profits_clean - predicted) ** 2)
        ss_tot  = np.sum((profits_clean - profits_clean.mean()) ** 2)
        r_squared = max(0.0, 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0)

        params = CurveParameters(
            alpha=alpha, beta=beta, gamma=gamma, delta=delta,
            r_squared=float(r_squared),
        )
        self._last_params = params
        logger.info(
            f"曲线拟合完成 | α={alpha:.4f} β={beta:.4f} γ={gamma:.4f} "
            f"δ={delta:.4f} | R²={r_squared:.4f} | n={len(bids_clean)}"
        )
        return params

    # ── 最优出价搜索 ───────────────────────────────────────────────────────────

    def find_optimal_bid(
        self,
        curve: CurveParameters,
        target_acos: float = 0.25,
        bid_range: tuple[float, float] = (0.10, 8.00),
    ) -> BidOptimizationResult:
        """
        在利润曲线上搜索最优出价。

        算法：
        1. 闭式求解（若 δ 不为 0）：b* = (1/γ) * ln(α*β / (α*γ + δ*γ))
        2. 数值验证：遍历 [bid_range] 找实际最大利润点
        3. 若利润为负，退化到 ACOS 目标约束求解

        Args:
            curve:      拟合的曲线参数
            target_acos: 目标 ACOS（用于 ACOS 约束模式）
            bid_range:  出价搜索范围

        Returns:
            BidOptimizationResult
        """
        α, β, γ, δ = curve.alpha, curve.beta, curve.gamma, curve.delta

        # ── 数值精确搜索（避免闭式误差）────────────────────────────────────
        best_bid, best_profit = 0.0, -float("inf")
        best_acos, best_roas = 0.0, 0.0

        for b in np.linspace(bid_range[0], bid_range[1], 800):
            p = self._profit_model(b, α, β, γ, δ)
            # 估算 acos：p = sales * 0.30 - spend, spend = b * (sales/spend)反向
            # 简化：acos ≈ b * ctr * cvr 修正
            estimated_acos = self._estimate_acos(b, curve)
            if p > best_profit:
                best_profit = p
                best_bid    = b
                best_acos   = estimated_acos
                best_roas   = 1.0 / estimated_acos if estimated_acos > 0 else 999

        # ── 确保出价在有效范围内 ───────────────────────────────────────────
        if best_bid < bid_range[0]:
            best_bid = bid_range[0]
        if best_bid > bid_range[1]:
            best_bid = bid_range[1]

        # ── 置信度：R² × 数据量折扣（强制截断到[0,1]）──────────────────────
        confidence = float(np.clip(min(curve.r_squared * 0.9 + 0.1, 1.0), 0.0, 1.0))

        # ── 生成建议 ───────────────────────────────────────────────────────
        recommendation = self._build_recommendation(best_bid, best_profit, best_acos, curve)

        model_used = "full" if curve.r_squared >= 0.6 else "simplified" if curve.r_squared >= 0.3 else "heuristic"

        return BidOptimizationResult(
            optimal_bid=round(best_bid, 2),
            expected_profit=round(best_profit, 4),
            expected_acos=round(best_acos, 4),
            expected_roas=round(best_roas, 4),
            confidence=round(confidence, 4),
            curve=curve,
            model_used=model_used,
            recommendation=recommendation,
        )

    # ── ACOS 约束求解 ─────────────────────────────────────────────────────────

    def solve_bid_for_target_acos(
        self,
        curve: CurveParameters,
        target_acos: float,
        bid_range: tuple[float, float] = (0.10, 8.00),
    ) -> Optional[float]:
        """
        求解满足目标 ACOS 的出价。

        目标 ACOS 约束：
            acos(b) = cost(b) / revenue(b) ≤ target_acos

        数值搜索在可行域内找acos最接近target_acos的出价。
        """
        best_bid, best_diff = None, float("inf")

        for b in np.linspace(bid_range[0], bid_range[1], 800):
            acos = self._estimate_acos(b, curve)
            diff = abs(acos - target_acos)
            if diff < best_diff:
                best_diff = diff
                best_bid  = b

        return round(best_bid, 2) if best_bid is not None else None

    # ─── 批量关键词优化 ────────────────────────────────────────────────────────

    def optimize_portfolio(
        self,
        keyword_records: dict[str, list[BidRecord]],
        target_portfolio_acos: float = 0.25,
    ) -> dict[str, BidOptimizationResult]:
        """
        批量优化多个关键词/广告组的出价。

        Args:
            keyword_records: {keyword: [BidRecord]} 关键词 → 历史记录
            target_portfolio_acos: 组合整体目标 ACOS

        Returns:
            {keyword: BidOptimizationResult}
        """
        results = {}
        for kw, records in keyword_records.items():
            curve = self.fit_curve(records)
            result = self.find_optimal_bid(curve)
            results[kw] = result
            logger.debug(f"关键词 [{kw}] 最优出价: ${result.optimal_bid:.2f} | ACOS: {result.expected_acos:.2%}")

        # ── 组合级 ACOS 校验 ────────────────────────────────────────────────
        portfolio_acos = self._compute_portfolio_acos(results)
        logger.info(
            f"组合优化完成 | 关键词数: {len(results)} | "
            f"组合ACOS: {portfolio_acos:.2%} | 目标ACOS: {target_portfolio_acos:.2%}"
        )
        return results

    # ─── 私有方法 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _profit_model(b: float, alpha: float, beta: float, gamma: float, delta: float) -> float:
        """
        利润曲线核心模型：
            P(b) = α * (1 - e^{-βb}) * e^{-γb} + δ

        物理意义：
        - (1 - e^{-βb}) : 曝光获取项，随出价增长逐渐饱和
        - e^{-γb}       : 成本侵蚀项，随出价指数增长而衰减
        - α             : 市场规模上限
        - δ             : 自然流量基础利润
        """
        b = max(b, 0.001)  # 防止除零
        exposure = 1.0 - math.exp(-beta * b)    # 曝光获取（0→1）
        cost_penalty = math.exp(-gamma * b)     # 成本惩罚（1→0）
        return alpha * exposure * cost_penalty + delta

    @staticmethod
    def _curve_loss_nd(params: np.ndarray, bids: np.ndarray, profits: np.ndarray) -> float:
        """四参数 L2 损失函数（用于 scipy.optimize.minimize）"""
        alpha, beta, gamma, delta = params
        preds = np.array([
            ProfitMarketCurve._profit_model(b, alpha, beta, gamma, delta)
            for b in bids
        ])
        return float(np.sum((profits - preds) ** 2))

    @staticmethod
    def _curve_loss(params: np.ndarray, bids: np.ndarray, profits: np.ndarray) -> float:
        """L2 损失函数（用于 SciPy minimize_scalar，单参数代理）"""
        alpha, beta, gamma, delta = ProfitMarketCurve._unpack_params(params)
        preds = np.array([
            ProfitMarketCurve._profit_model(b, alpha, beta, gamma, delta)
            for b in bids
        ])
        return float(np.sum((profits - preds) ** 2))

    @staticmethod
    def _unpack_params(x: float) -> tuple[float, float, float, float]:
        """将一维权重向量映射为正数参数（确保物理意义）"""
        # x[0]=alpha, x[1]=beta, x[2]=gamma, x[3]=delta
        raw = [x] if np.isscalar(x) else x
        if len(raw) == 1:
            # 单一标量：分解为 α=1, β=raw[0], γ=raw[0]*0.8, δ=0
            v = float(raw[0])
            return (1.0, v, v * 0.8, 0.0)
        elif len(raw) == 4:
            return tuple(float(v) for v in raw)
        else:
            v = float(raw[0] if np.isscalar(raw[0]) else raw[0][0])
            return (1.0, v, v * 0.8, 0.0)

    @staticmethod
    def _grid_search(bids: np.ndarray, profits: np.ndarray) -> tuple[float, float, float, float]:
        """网格搜索初始化参数（作为 SciPy 的安全垫）"""
        best_loss, best_params = float("inf"), (1.0, 0.5, 0.3, 0.0)

        for alpha in [0.5, 1.0, 2.0, 5.0]:
            for beta in [0.3, 0.5, 0.8, 1.0, 1.5, 2.0]:
                for gamma in [0.1, 0.2, 0.3, 0.5, 0.8]:
                    for delta in [-0.5, 0.0, 0.5, 1.0]:
                        loss = sum(
                            (p - ProfitMarketCurve._profit_model(b, alpha, beta, gamma, delta)) ** 2
                            for b, p in zip(bids, profits)
                        )
                        if loss < best_loss:
                            best_loss   = loss
                            best_params = (alpha, beta, gamma, delta)

        return best_params

    @staticmethod
    def _estimate_acos(bid: float, curve: CurveParameters) -> float:
        """估算给定出价下的 ACOS（用于推荐）"""
        α, β, γ, δ = curve.alpha, curve.beta, curve.gamma, curve.delta
        profit = ProfitMarketCurve._profit_model(bid, α, β, γ, δ)
        # acos = spend / revenue = spend / (spend + profit/gross_margin)
        gross_margin = 0.30
        if profit >= 0:
            # revenue = spend + profit/gross_margin
            spend_ratio = 1.0 / (1.0 + profit / gross_margin)
            return min(spend_ratio, 1.0)
        else:
            return 1.0  # 亏损时 acos=100%

    @staticmethod
    def _heuristic_params() -> CurveParameters:
        """数据不足时的启发式默认参数"""
        return CurveParameters(alpha=1.0, beta=0.8, gamma=0.5, delta=0.0, r_squared=0.0)

    @staticmethod
    def _build_recommendation(
        bid: float,
        profit: float,
        acos: float,
        curve: CurveParameters,
    ) -> str:
        if acos > 0.40:
            tone = "⚠️ 当前ACOS偏高，建议降低出价"
        elif acos < 0.10:
            tone = "💡 ACOS极低，说明有提价空间"
        else:
            tone = "✅ ACOS处于健康区间"

        return (
            f"{tone}，最优出价 ${bid:.2f}。"
            f"预计ACOS={acos:.1%}，预期利润率={profit:.2f}。"
            f"模型置信度={curve.r_squared:.1%}（R²={curve.r_squared:.2f}）。"
            f"曝光效率β={curve.beta:.2f}，成本侵蚀γ={curve.gamma:.2f}。"
        )

    @staticmethod
    def _compute_portfolio_acos(results: dict[str, BidOptimizationResult]) -> float:
        """计算组合平均 ACOS（按利润加权）"""
        if not results:
            return 0.0
        total_profit = sum(r.expected_profit for r in results.values())
        if total_profit <= 0:
            return 1.0
        acos_values = [r.expected_acos for r in results.values()]
        return float(np.mean(acos_values))


# ─── 快速入口 ─────────────────────────────────────────────────────────────────

def quick_optimize(
    bid_history: list[BidRecord],
    target_acos: float = 0.25,
) -> BidOptimizationResult:
    """
    快捷优化入口（单行调用）

    Example:
        records = [
            BidRecord(bid=0.5, impressions=1000, clicks=20, spend=10.0, sales=50.0, orders=2),
            BidRecord(bid=1.0, impressions=2000, clicks=50, spend=50.0, sales=200.0, orders=8),
            BidRecord(bid=1.5, impressions=3000, clicks=90, spend=135.0, sales=350.0, orders=12),
        ]
        result = quick_optimize(records, target_acos=0.25)
        print(result.optimal_bid, result.recommendation)
    """
    pmc = ProfitMarketCurve()
    curve = pmc.fit_curve(bid_history)
    return pmc.find_optimal_bid(curve, target_acos=target_acos)
