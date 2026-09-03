"""
execution/tests/test_profit_optimizer.py
========================================
ProfitOptimizer 算法单元测试套件

运行方式：
    cd amazon-ops-agents
    python -m execution.tests.test_profit_optimizer
    pytest execution/tests/test_profit_optimizer.py -v
    pytest execution/tests/test_profit_optimizer.py -v --tb=short

测试覆盖
--------
✅ T1: BidRecord 指标计算
✅ T2: CurveParameters 序列化
✅ T3: ProfitMarketCurve.fit_curve — 正常数据拟合
✅ T4: ProfitMarketCurve.fit_curve — 数据不足降级
✅ T5: find_optimal_bid — 利润最大化出价
✅ T6: solve_bid_for_target_acos — ACOS约束求解
✅ T7: optimize_portfolio — 批量关键词优化
✅ T8: quick_optimize — 快捷入口
✅ T9: 性能基准 vs 规则引擎（传统方法）
✅ T10: 边界条件（出价极端值）
✅ T11: 转化率预测器 (ConversionPredictor)
✅ T12: 综合转化预测
✅ T13: IntradayBidder L1 时段调整
✅ T14: IntradayBidder L2 表现层
✅ T15: IntradayBidder 三层合成
"""

import sys
import os
import time
from datetime import datetime
from typing import cast

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# ─── 导入被测模块 ─────────────────────────────────────────────────────────────
from execution.profit_optimizer import (
    BidRecord,
    CurveParameters,
    ProfitMarketCurve,
    quick_optimize,
)
from execution.conversion_predictor import (
    ConversionFeatures,
    ConversionPredictor,
    quick_predict,
    batch_predict,
)
from execution.intraday_bidder import (
    IntradayBidder,
    HourlyPerformance,
    quick_intraday,
    generate_cron_schedule,
)


# ══════════════════════════════════════════════════════════════════════════════
# 辅助：断言装饰器
# ══════════════════════════════════════════════════════════════════════════════

def assert_eq(actual, expected, msg=""):
    if abs(actual - expected) > 1e-6 and actual != expected:
        raise AssertionError(f"{msg}: expected {expected}, got {actual}")


def assert_in(value, container, msg=""):
    if value not in container:
        raise AssertionError(f"{msg}: {value} not in {container}")


# ══════════════════════════════════════════════════════════════════════════════
# T1: BidRecord 指标计算
# ══════════════════════════════════════════════════════════════════════════════

def test_bid_record_metrics():
    """BidRecord 派生指标正确性"""
    r = BidRecord(
        bid=1.0, impressions=1000, clicks=50,
        spend=50.0, sales=250.0, orders=5, date="2024-01-01",
    )

    assert abs(r.ctr   - 0.05)  < 1e-9, "CTR 计算错误"
    assert abs(r.cvr   - 0.10)  < 1e-9, "CVR 计算错误"
    assert abs(r.cpc   - 1.00)  < 1e-9, "CPC 计算错误"
    assert abs(r.acos  - 0.20)  < 1e-9, "ACOS 计算错误"
    assert abs(r.roas  - 5.00)  < 1e-9, "ROAS 计算错误"
    assert abs(r.profit - 25.0) < 1e-9, "利润计算错误（250*0.3-50=25）"

    # 边界：零除
    r_zero = BidRecord(bid=0, impressions=0, clicks=0, spend=0, sales=0, orders=0)
    assert r_zero.ctr  == 0.0, "零曝光 CTR 应为 0"
    assert r_zero.cvr  == 0.0, "零点击 CVR 应为 0"
    assert r_zero.cpc  == 0.0, "零点击 CPC 应为 0"
    assert r_zero.acos == 0.0, "零销售额 ACOS 应为 0"
    assert r_zero.roas == 0.0, "零花费 ROAS 应为 0"
    assert r_zero.profit == 0.0, "零花费利润应为 0（不报错）"

    print("✅ T1: BidRecord 指标计算 — PASS")


# ══════════════════════════════════════════════════════════════════════════════
# T2: CurveParameters 序列化
# ══════════════════════════════════════════════════════════════════════════════

def test_curve_parameters_serialization():
    """CurveParameters 序列化 round-trip"""
    params = CurveParameters(alpha=1.2345, beta=0.8765, gamma=0.5432, delta=-0.1234, r_squared=0.8765)
    d = params.to_dict()

    assert d["alpha"]     == 1.2345,  "alpha 序列化"
    assert d["beta"]      == 0.8765,  "beta 序列化"
    assert d["gamma"]     == 0.5432,  "gamma 序列化"
    assert d["delta"]     == -0.1234, "delta 序列化"
    assert d["r_squared"] == 0.8765,  "r_squared 序列化"

    print("✅ T2: CurveParameters 序列化 — PASS")


# ══════════════════════════════════════════════════════════════════════════════
# T3: fit_curve — 正常数据拟合
# ══════════════════════════════════════════════════════════════════════════════

def test_fit_curve_normal():
    """有足够数据时能正确拟合曲线"""
    records = [
        # bid, impressions, clicks, spend, sales, orders
        BidRecord(bid=0.3,  impressions=200, clicks=4,  spend=1.2,  sales=6.0,   orders=1),
        BidRecord(bid=0.6,  impressions=600, clicks=15, spend=9.0,  sales=45.0,  orders=3),
        BidRecord(bid=1.0,  impressions=1200,clicks=36, spend=36.0, sales=120.0, orders=8),
        BidRecord(bid=1.5,  impressions=2000,clicks=70, spend=105.0,sales=280.0, orders=14),
        BidRecord(bid=2.0,  impressions=2500,clicks=100,spend=200.0,sales=350.0, orders=15),
        BidRecord(bid=3.0,  impressions=3000,clicks=150,spend=450.0,sales=450.0, orders=12),
    ]

    pmc     = ProfitMarketCurve()
    params  = pmc.fit_curve(records)

    assert params.alpha > 0,   "alpha 必须为正"
    assert params.beta  > 0,   "beta  必须为正"
    assert params.gamma > 0,   "gamma 必须为正"
    assert 0.0 <= params.r_squared <= 1.0, "R² 必须在 [0,1]"

    # 验证 profit_model 可调用
    profit_at_1 = pmc._profit_model(1.0, params.alpha, params.beta, params.gamma, params.delta)
    assert isinstance(profit_at_1, float), "profit_model 返回类型"

    print(f"✅ T3: fit_curve 正常拟合 | α={params.alpha:.3f} β={params.beta:.3f} γ={params.gamma:.3f} R²={params.r_squared:.3f}")


# ══════════════════════════════════════════════════════════════════════════════
# T4: fit_curve — 数据不足降级
# ══════════════════════════════════════════════════════════════════════════════

def test_fit_curve_insufficient_data():
    """数据不足时回退到启发式参数"""
    pmc = ProfitMarketCurve()

    # 单点
    single = [BidRecord(bid=1.0, impressions=100, clicks=5, spend=5.0, sales=25.0, orders=1)]
    params  = pmc.fit_curve(single)
    assert params.alpha == 1.0, "单点回退 alpha=1.0"
    assert params.r_squared == 0.0, "单点 R²=0（无拟合）"

    # 空数据
    empty_params = pmc.fit_curve([])
    assert empty_params.alpha == 1.0, "空数据回退 alpha=1.0"

    print("✅ T4: fit_curve 数据不足降级 — PASS")


# ══════════════════════════════════════════════════════════════════════════════
# T5: find_optimal_bid — 利润最大化
# ══════════════════════════════════════════════════════════════════════════════

def test_find_optimal_bid():
    """最优出价搜索返回有效范围内的值"""
    records = [
        BidRecord(bid=0.3,  impressions=200, clicks=4,  spend=1.2,  sales=6.0,   orders=1),
        BidRecord(bid=0.6,  impressions=600, clicks=15, spend=9.0,  sales=45.0,  orders=3),
        BidRecord(bid=1.0,  impressions=1200,clicks=36, spend=36.0, sales=120.0, orders=8),
        BidRecord(bid=1.5,  impressions=2000,clicks=70, spend=105.0,sales=280.0, orders=14),
        BidRecord(bid=2.0,  impressions=2500,clicks=100,spend=200.0,sales=350.0, orders=15),
        BidRecord(bid=3.0,  impressions=3000,clicks=150,spend=450.0,sales=450.0, orders=12),
    ]

    pmc    = ProfitMarketCurve()
    curve  = pmc.fit_curve(records)
    result = pmc.find_optimal_bid(curve, target_acos=0.25)

    assert 0.10 <= result.optimal_bid <= 8.00, f"最优出价越界: {result.optimal_bid}"
    assert 0.0 <= result.expected_acos <= 1.5,  f"预期ACOS越界: {result.expected_acos}"
    assert 0.0 <= result.confidence <= 1.0,      "置信度越界"
    assert_in(result.model_used, ["full","simplified","heuristic"], "model_used")
    assert len(result.recommendation) > 10,       "推荐理由为空"

    print(f"✅ T5: find_optimal_bid | 最优出价=${result.optimal_bid:.2f} | ACOS={result.expected_acos:.2%} | 置信度={result.confidence:.2%} | {result.recommendation[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# T6: solve_bid_for_target_acos — ACOS约束求解
# ══════════════════════════════════════════════════════════════════════════════

def test_solve_bid_for_target_acos():
    """给定目标 ACOS 找到对应出价"""
    records = [
        BidRecord(bid=0.5, impressions=500, clicks=10, spend=5.0, sales=25.0, orders=2),
        BidRecord(bid=1.0, impressions=1200,clicks=30, spend=30.0, sales=120.0, orders=6),
        BidRecord(bid=2.0, impressions=2000,clicks=80, spend=160.0,sales=400.0, orders=16),
    ]

    pmc    = ProfitMarketCurve()
    curve  = pmc.fit_curve(records)
    bid_20 = pmc.solve_bid_for_target_acos(curve, target_acos=0.20)
    bid_30 = pmc.solve_bid_for_target_acos(curve, target_acos=0.30)
    bid_50 = pmc.solve_bid_for_target_acos(curve, target_acos=0.50)

    assert bid_20 is not None and 0.10 <= bid_20 <= 8.00, "bid_20 越界"
    assert bid_30 is not None and 0.10 <= bid_30 <= 8.00, "bid_30 越界"
    assert bid_50 is not None and 0.10 <= bid_50 <= 8.00, "bid_50 越界"

    # 目标ACOS越高 → 出价越高（成本增加）
    if bid_20 and bid_30:
        assert bid_30 >= bid_20, f"ACOS30%={bid_30} 应 >= ACOS20%={bid_20}"

    print(f"✅ T6: ACOS约束求解 | 20%→${bid_20:.2f} | 30%→${bid_30:.2f} | 50%→${bid_50:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# T7: optimize_portfolio — 批量关键词优化
# ══════════════════════════════════════════════════════════════════════════════

def test_optimize_portfolio():
    """批量优化多个关键词"""
    kw1 = [
        BidRecord(bid=0.5, impressions=500, clicks=10, spend=5.0,  sales=25.0,  orders=2),
        BidRecord(bid=1.0, impressions=1000,clicks=30, spend=30.0, sales=120.0, orders=6),
        BidRecord(bid=2.0, impressions=2000,clicks=80, spend=160.0,sales=400.0, orders=16),
    ]
    kw2 = [
        BidRecord(bid=1.0, impressions=300, clicks=6,  spend=6.0,  sales=30.0,  orders=2),
        BidRecord(bid=2.0, impressions=800, clicks=24, spend=48.0, sales=180.0, orders=9),
    ]

    pmc     = ProfitMarketCurve()
    results = pmc.optimize_portfolio({"kw1": kw1, "kw2": kw2}, target_portfolio_acos=0.30)

    assert set(results.keys()) == {"kw1", "kw2"}, "关键词映射错误"
    assert all(isinstance(r.optimal_bid, float) for r in results.values()), "出价类型"
    assert all(0.10 <= r.optimal_bid <= 8.00 for r in results.values()), "出价范围"

    print(f"✅ T7: 批量优化 | kw1→${results['kw1'].optimal_bid:.2f} | kw2→${results['kw2'].optimal_bid:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# T8: quick_optimize — 快捷入口
# ══════════════════════════════════════════════════════════════════════════════

def test_quick_optimize():
    """quick_optimize 单行入口返回正确类型"""
    records = [
        BidRecord(bid=0.5, impressions=500, clicks=10, spend=5.0,  sales=25.0,  orders=2),
        BidRecord(bid=1.0, impressions=1200,clicks=30, spend=30.0, sales=120.0, orders=6),
        BidRecord(bid=1.5, impressions=1800,clicks=54, spend=81.0, sales=270.0, orders=12),
    ]

    result = quick_optimize(records, target_acos=0.25)

    assert isinstance(result.optimal_bid, float), "返回类型错误"
    assert isinstance(result.curve, CurveParameters), "curve 类型错误"
    assert result.curve.alpha > 0, "alpha 验证"
    print(f"✅ T8: quick_optimize | 出价=${result.optimal_bid:.2f} | ACOS={result.expected_acos:.2%}")


# ══════════════════════════════════════════════════════════════════════════════
# T9: 性能基准 vs 规则引擎（传统方法）
# ══════════════════════════════════════════════════════════════════════════════

def test_performance_vs_rule_engine():
    """
    诚实的性能基准（替代原"全空间搜索 vs 单步空转规则"的矮化对比）：

    方法论（与 benchmarks/bench_profit_optimizer.py 一致）：
    - 同搜索空间：optimizer 的 bid_range 限制在观测数据范围内
    - 同真值评估：三个策略都用 benchmark 私有真值利润函数评估（非模型拟合值）
    - 规则引擎可迭代 20 步，且用与毛利结构匹配的自适应阈值（0.25/0.10）
    - 多市场多种子，报告 R² / 累计利润 / 胜率

    断言（宽松且诚实）：
    1. optimizer 累计利润 > 维持现状（"什么都不做"）
    2. optimizer 对自适应规则的胜率 > 60%（失配市场下不要求全胜）
    """
    import numpy as np
    from benchmarks.bench_profit_optimizer import (
        N_SEEDS, _gen_market, _true_profit_at, _rule_strategy, _optimizer_strategy,
    )

    agg_opt = agg_cur = agg_ada = 0.0
    win_ada = 0
    r2s = []
    for seed in range(N_SEEDS):
        records, truth = _gen_market(seed, family=False)  # 用失配市场（更严格）
        cur_bid = records[-1].bid
        rule_ada_bid = _rule_strategy(records, 20, truth, adaptive=True)
        opt_bid, r2, _model = _optimizer_strategy(records)
        p_opt = _true_profit_at(opt_bid, truth)
        p_cur = _true_profit_at(cur_bid, truth)
        p_ada = _true_profit_at(rule_ada_bid, truth)
        agg_opt += p_opt
        agg_cur += p_cur
        agg_ada += p_ada
        win_ada += 1 if p_opt > p_ada + 1e-9 else 0
        r2s.append(r2)

    med_r2 = float(np.median(r2s))
    win_rate = win_ada / N_SEEDS
    print(f"✅ T9: 诚实性能基准（失配市场 {N_SEEDS} 个）")
    print(f"   ├─ 拟合R²中位数={med_r2:.3f}")
    print(f"   ├─ 累计利润: optimizer=${agg_opt:.0f} | 规则ada=${agg_ada:.0f} | 维持=${agg_cur:.0f}")
    print(f"   └─ vs 自适应规则: 胜率={win_rate:.0%}（原+19.5%声明为矮化结果，见benchmarks/）")

    assert agg_opt > agg_cur, f"optimizer 累计利润应高于维持现状: {agg_opt:.2f} vs {agg_cur:.2f}"
    assert agg_opt > agg_ada, f"optimizer 累计利润应高于自适应规则: {agg_opt:.2f} vs {agg_ada:.2f}"
    assert win_rate > 0.60, f"optimizer 对自适应规则胜率应>60%: {win_rate:.0%}"
    return True


# ══════════════════════════════════════════════════════════════════════════════
# T10: 边界条件
# ══════════════════════════════════════════════════════════════════════════════

def test_edge_cases():
    """极端边界条件处理"""
    pmc = ProfitMarketCurve()

    # ── 出价范围边界 ───────────────────────────────────────────────────────
    records = [
        BidRecord(bid=0.02, impressions=50,  clicks=1,  spend=0.02, sales=0.10,  orders=0),
        BidRecord(bid=5.0,  impressions=5000,clicks=250,spend=1250.0,sales=2500.0,orders=10),
    ]
    result = pmc.find_optimal_bid(pmc.fit_curve(records))
    assert 0.10 <= result.optimal_bid <= 8.00, "出价越界"

    # ── 零销售额 ────────────────────────────────────────────────────────────
    zero_sales = BidRecord(bid=1.0, impressions=100, clicks=5, spend=5.0, sales=0.0, orders=0)
    assert zero_sales.acos == 0.0, "零销售额 ACOS"
    assert zero_sales.profit == -5.0, "零销售额利润 = -spend"

    # ── 高 ACOS 场景 ────────────────────────────────────────────────────────
    high_acos = BidRecord(bid=3.0, impressions=500, clicks=30, spend=90.0, sales=150.0, orders=3)
    assert high_acos.acos > 0.5, "高ACOS识别"
    result_ha = pmc.find_optimal_bid(pmc.fit_curve([high_acos]))
    assert 0.10 <= result_ha.optimal_bid <= 8.00, "高ACOS场景出价越界"

    print(f"✅ T10: 边界条件处理 | high_acos={high_acos.acos:.2%} | 建议出价=${result_ha.optimal_bid:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# T11: ConversionPredictor — 转化率预测
# ══════════════════════════════════════════════════════════════════════════════

def test_conversion_predictor_cvr():
    """ConversionPredictor CVR 预测范围正确"""
    predictor = ConversionPredictor()

    # 顶级Listing：高评分 + Top位置 + Exact匹配
    top_features = ConversionFeatures(
        rating=0.90,        # 4.5星
        ad_placement="top",
        match_type="exact",
        review_count=0.8,    # 高评论数
        competition_level=0.3,
        prime_eligible=True,
        age_of_product_listing=0.5,  # 成熟Listing
        product_category="electronics",
    )
    pred_top = predictor.predict_conversion_rate(top_features)

    # 低质量Listing
    low_features = ConversionFeatures(
        rating=0.40,        # 2星
        ad_placement="product",
        match_type="broad",
        review_count=0.1,
        competition_level=0.9,
        stock_status="low_stock",
        prime_eligible=False,
        age_of_product_listing=0.02,
    )
    pred_low = predictor.predict_conversion_rate(low_features)

    assert 0.001 <= pred_top  <= 0.999, f"top特征CVR越界: {pred_top}"
    assert 0.001 <= pred_low  <= 0.999, f"low特征CVR越界: {pred_low}"
    assert pred_top > pred_low, "优质Listing CVR应高于低质量Listing"

    print(f"✅ T11: CVR预测 | 优质={pred_top:.3f} | 低质量={pred_low:.3f} | 倍数={pred_top/max(pred_low,0.001):.1f}x")


# ══════════════════════════════════════════════════════════════════════════════
# T12: 综合转化预测（含AOV和风险识别）
# ══════════════════════════════════════════════════════════════════════════════

def test_conversion_prediction_full():
    """完整转化预测：CVR × AOV × 风险识别"""
    predictor = ConversionPredictor()

    features = ConversionFeatures(
        campaign_type="sp",
        product_category="electronics",
        price_range=2.5,     # ~$30商品
        rating=0.85,
        review_count=0.7,
        ad_placement="top",
        match_type="exact",
        prime_eligible=True,
        coupon_active=True,
        lightning_deal=False,
        competition_level=0.5,
        seasonality_index=1.2,
        stock_status="in_stock",
    )

    pred = predictor.predict(features)

    assert 0.0 < pred.cvr < 1.0,         "CVR 范围"
    assert 1.0 < pred.order_value < 5000, "AOV 范围"
    assert 0.0 < pred.total_value < pred.order_value, "综合价值"
    assert 0.0 < pred.confidence <= 1.0, "置信度"
    assert isinstance(pred.risk_flags, list), "风险列表类型"

    print(f"✅ T12: 综合转化预测 | {pred.summary()}")
    if pred.risk_flags:
        print(f"   风险标识: {pred.risk_flags}")

    # 在线学习更新
    predictor.update_from_actual(pred, actual_cvr=0.08, actual_aov=32.0)
    assert hasattr(predictor, "_cvr_bias"), "在线更新偏差"

    # 特征重要性
    importance = predictor.feature_importance_report()
    assert len(importance) == 22, "22维特征"
    assert sum(importance.values()) > 0, "重要性总和为正"

    print(f"✅ T12b: 在线更新 + 特征重要性 — PASS")


# ══════════════════════════════════════════════════════════════════════════════
# T13: IntradayBidder — L1 时段基础调整
# ══════════════════════════════════════════════════════════════════════════════

def test_intraday_l1_schedule():
    """Layer 1 时段规则正确"""
    bidder = IntradayBidder(enable_performance_layer=False)

    keywords = {"kw1": 1.0, "kw2": 2.0}

    # 深夜（ET 2点）→ 大幅降价
    session_night = bidder.adjust_bids(
        current_hour=2, performance=[], keywords=keywords
    )
    assert len(session_night.adjustments) == 2, "调整数量"
    for adj in session_night.adjustments:
        assert adj.adjustment_pct < 0, f"深夜应降价，当前={adj.adjustment_pct}"
        assert "L1时段" in adj.trigger_reason, "触发原因包含L1"

    # 高峰（ET 10点）→ 加价
    session_peak = bidder.adjust_bids(
        current_hour=10, performance=[], keywords=keywords
    )
    for adj in session_peak.adjustments:
        assert adj.adjustment_pct > 0, f"高峰应加价，当前={adj.adjustment_pct}"

    # 正常（ET 14点）→ ±0
    session_norm = bidder.adjust_bids(
        current_hour=14, performance=[], keywords=keywords
    )
    # 当前14点=AFTERNOON，规则是1.0，performance关闭时只有L1
    print(f"✅ T13: L1时段 | 深夜={session_night.adjustments[0].new_bid:.2f} | 高峰={session_peak.adjustments[0].new_bid:.2f} | 午后={session_norm.adjustments[0].new_bid:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# T14: IntradayBidder — L2 表现层
# ══════════════════════════════════════════════════════════════════════════════

def test_intraday_l2_performance():
    """Layer 2 表现层正确响应 ACOS/CTR/CVR"""
    bidder = IntradayBidder(enable_performance_layer=True, enable_competition_layer=False)

    keywords = {"kw1": 1.50}

    # 场景1：ACOS 持续偏高（50%+），CVR 偏低 → 应降价
    # 选午后时段(L1=1.0)避免 L1 干扰，突出 L2 效果
    perf_high_acos = [
        HourlyPerformance(hour_et=12, impressions=500, clicks=24, spend=12.0, sales=24.0, orders=1),
        HourlyPerformance(hour_et=13, impressions=600, clicks=30, spend=15.0, sales=30.0, orders=1),
    ]
    session_ha = bidder.adjust_bids(12, perf_high_acos, keywords, target_acos=0.25)
    assert session_ha.adjustments[0].adjustment_pct < 0, f"高ACOS应降价: {session_ha.adjustments[0].adjustment_pct}"

    # 场景2：ACOS 持续偏低（10%）→ 应加价
    perf_low_acos = [
        HourlyPerformance(hour_et=9,  impressions=500, clicks=25, spend=5.0,  sales=50.0, orders=2),
        HourlyPerformance(hour_et=10, impressions=600, clicks=30, spend=6.0,  sales=60.0, orders=3),
    ]
    session_la = bidder.adjust_bids(9, perf_low_acos, keywords, target_acos=0.25)
    assert session_la.adjustments[0].adjustment_pct > 0, f"低ACOS应加价: {session_la.adjustments[0].adjustment_pct}"

    print(f"✅ T14: L2表现层 | 高ACOS→{session_ha.adjustments[0].adjustment_pct:+.1%} | 低ACOS→{session_la.adjustments[0].adjustment_pct:+.1%}")


# ══════════════════════════════════════════════════════════════════════════════
# T15: IntradayBidder — 三层合成 + 边界约束
# ══════════════════════════════════════════════════════════════════════════════

def test_intraday_full_three_layers():
    """三层合成 + 30%变化上限 + 出价边界"""
    bidder = IntradayBidder(
        enable_performance_layer=True,
        enable_competition_layer=True,
        max_bid_change_pct=0.30,
        min_bid_floor=0.10,
        max_bid_cap=8.00,
    )

    # 用足够高的基准出价(0.50)，确保30%降价不会碰到下限0.10
    perf = [HourlyPerformance(hour_et=2, impressions=200, clicks=4, spend=2.0, sales=10.0, orders=1)]
    keywords = {"extreme_kw": 0.50}

    session = bidder.adjust_bids(
        current_hour=2,
        performance=perf,
        keywords=keywords,
        target_acos=0.25,
        competition_boost=0.5,
    )

    adj = session.adjustments[0]
    assert abs(adj.adjustment_pct) <= 0.30 + 1e-6, f"超出30%变化限制: {adj.adjustment_pct:.4f}"
    assert adj.new_bid >= 0.10, f"低于出价下限: {adj.new_bid}"
    assert adj.new_bid <= 8.00, f"高于出价上限: {adj.new_bid}"
    assert "L1" in adj.trigger_reason or "L2" in adj.trigger_reason or "L3" in adj.trigger_reason

    # Cron schedule 生成
    schedule = generate_cron_schedule()
    assert len(schedule) == 24, "24小时schedule"
    assert all("hour_et" in s and "multiplier" in s for s in schedule)

    print(f"✅ T15: 三层合成 | {adj.keyword}: ${adj.current_bid:.2f}→${adj.new_bid:.2f} ({adj.adjustment_pct:+.0%}) | {adj.trigger_reason}")
    print(f"✅ T15b: Cron Schedule | 时段覆盖24h | PASS")


# ══════════════════════════════════════════════════════════════════════════════
# T16: quick_intraday 快捷入口
# ══════════════════════════════════════════════════════════════════════════════

def test_quick_intraday():
    """quick_intraday 一行入口"""
    session = quick_intraday(
        keywords={"kw1": 1.0, "kw2": 1.5, "kw3": 2.0},
        hour_et=10,
        target_acos=0.20,
    )
    assert len(session.adjustments) == 3
    assert all(adj.adjustment_pct > 0 for adj in session.adjustments), "10点ET应全加价"
    print(f"✅ T16: quick_intraday | {session.summary()}")


# ══════════════════════════════════════════════════════════════════════════════
# 批量预测测试
# ══════════════════════════════════════════════════════════════════════════════

def test_batch_predict():
    """批量预测 + 跳过错误记录"""
    # 使用类目市场基准，让 electronics 的 CVR 自然高于 home
    benchmarks = {
        "electronics": {"cvr": 0.050, "aov": 35.0},
        "home":        {"cvr": 0.025, "aov": 22.0},
    }

    records = [
        {
            "campaign_type": "sp",
            "product_category": "electronics",
            "rating": 0.85,
            "review_count": 0.7,
            "ad_placement": "top",
        },
        {
            "campaign_type": "sp",
            "product_category": "home",
            "rating": 0.60,
            "review_count": 0.3,
            "ad_placement": "product",
        },
    ]

    results = batch_predict(records, benchmarks=benchmarks)
    assert len(results) == 2
    assert results[0].cvr > results[1].cvr, f"electronics应比home转化率高: {results[0].cvr:.3f} vs {results[1].cvr:.3f}"
    print(f"✅ Batch预测 | 电子={results[0].summary()} | 家居={results[1].summary()}")


# ══════════════════════════════════════════════════════════════════════════════
# 综合报告
# ══════════════════════════════════════════════════════════════════════════════

def run_all_tests():
    """运行所有测试并生成报告"""
    tests = [
        ("T1: BidRecord指标计算",             test_bid_record_metrics),
        ("T2: CurveParameters序列化",         test_curve_parameters_serialization),
        ("T3: fit_curve正常拟合",              test_fit_curve_normal),
        ("T4: fit_curve数据不足降级",           test_fit_curve_insufficient_data),
        ("T5: find_optimal_bid",              test_find_optimal_bid),
        ("T6: solve_bid_for_target_acos",      test_solve_bid_for_target_acos),
        ("T7: optimize_portfolio",             test_optimize_portfolio),
        ("T8: quick_optimize",                 test_quick_optimize),
        ("T9: 性能基准vs规则引擎",             test_performance_vs_rule_engine),
        ("T10: 边界条件",                      test_edge_cases),
        ("T11: ConversionPredictor CVR",       test_conversion_predictor_cvr),
        ("T12: 综合转化预测",                  test_conversion_prediction_full),
        ("T13: Intraday L1时段",              test_intraday_l1_schedule),
        ("T14: Intraday L2表现",              test_intraday_l2_performance),
        ("T15: Intraday 三层合成",             test_intraday_full_three_layers),
        ("T16: quick_intraday",                test_quick_intraday),
        ("T17: batch_predict",                 test_batch_predict),
    ]

    print("=" * 70)
    print("  ProfitOptimizer 算法测试套件")
    print("  亚马逊运营硅基军团 · 广告优化引擎")
    print("=" * 70)
    print()

    passed = 0
    failed = 0
    start_total = time.perf_counter()

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {name}: FAILED — {e}")
            import traceback
            traceback.print_exc()

    elapsed_total = time.perf_counter() - start_total
    print()
    print("=" * 70)
    print(f"  测试完成 | ✅ {passed} | ❌ {failed} | ⏱ {elapsed_total*1000:.1f}ms")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
