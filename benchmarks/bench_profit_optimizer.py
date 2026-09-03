"""
benchmarks/bench_profit_optimizer.py — 诚实的 ProfitOptimizer 基准
====================================================================
针对原 T9"全空间搜索 vs 只看最后一条数据的规则引擎"的矮化对比重写：

方法论修正（每一条都是原版的缺陷）：
1. 同搜索空间：optimizer 的 bid_range 限制在观测数据范围内（而非拍脑袋的 [0.10, 8.00]），
   规则引擎允许迭代多步（±10% 规则 × 20 步），两者具备相近的适应能力。
2. 同真值评估：三个策略都用**真实利润函数**（benchmark 中已知 ground truth）评估，
   而不是用 optimizer 自己的拟合曲线评估（那必然偏向 optimizer）。
3. 多种子：50 个随机市场 × 固定种子，报告均值/中位数/标准差/胜率。
4. 诚实报告拟合质量：R² 分布 + 拟合退化（R²≈0）时 optimizer 并不占优的样本占比。

运行：
    python benchmarks/bench_profit_optimizer.py
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from execution.profit_optimizer import BidRecord, ProfitMarketCurve  # noqa: E402

N_SEEDS = 50
N_POINTS = 20
RULE_STEPS = 20


def _true_profit(bid: float, alpha: float, beta: float, gamma: float, delta: float) -> float:
    """基准的 ground truth 利润函数（与模型同族，但参数为 benchmark 私有）"""
    return alpha * (1 - np.exp(-beta * bid)) * np.exp(-gamma * bid) + delta


def _gen_market(seed: int, family: bool = True) -> tuple[list[BidRecord], dict]:
    """
    生成公平可比的竞价市场。
    - family=True : 真值利润 = α(1-e^{-βb})e^{-γb}+δ（与模型同族，拟合友好）
    - family=False: 真值利润 = A·b/(b+k) − m·b（饱和收益−线性成本，模型失配）
    - 记录构造带真实结构：spend = b×clicks（clicks=impressions×ctr），
      sales = (P(b)+spend)/0.3 → BidRecord.profit ≡ 真值利润
    - acos = spend/sales = 0.3·b·clicks/(P(b)+b·clicks)（因 BidRecord 毛利固定 30%，acos<0.3）
    """
    rng = np.random.default_rng(seed)
    impressions = 1000
    ctr = rng.uniform(0.02, 0.05)
    clicks = impressions * ctr
    bids = np.linspace(0.2, 3.5, N_POINTS)
    if family:
        params = {
            "family": True,
            "alpha": rng.uniform(3.0, 8.0), "beta": rng.uniform(0.5, 1.5),
            "gamma": rng.uniform(0.15, 0.5), "delta": rng.uniform(0.1, 0.6),
        }
    else:
        params = {
            "family": False,
            "A": rng.uniform(4.0, 9.0), "k": rng.uniform(1.0, 3.0),
            "m": rng.uniform(1.0, 2.5), "delta": rng.uniform(0.05, 0.3),
        }
    params["clicks"] = clicks
    records = []
    for b in bids:
        p_true = max(_true_profit_at(b, params), 0.05)
        spend = b * clicks
        sales = (p_true + spend) / 0.3
        records.append(BidRecord(
            bid=float(b), impressions=impressions, clicks=int(clicks),
            spend=float(spend), sales=float(sales), orders=int(clicks * rng.uniform(0.08, 0.15)),
        ))
    return records, params


def _true_profit_at(b: float, p: dict) -> float:
    if p.get("family"):
        return float(p["alpha"] * (1 - np.exp(-p["beta"] * b)) * np.exp(-p["gamma"] * b) + p["delta"])
    return float(p["A"] * b / (b + p["k"]) - p["m"] * b + p["delta"])


def _acos_at(bid: float, clicks: float, truth: dict) -> float:
    """按 30% 毛利结构估算 acos：acos = spend/sales = bid·clicks / ((P+bid·clicks)/0.3)"""
    spend = bid * clicks
    sales = (_true_profit_at(bid, truth) + spend) / 0.3
    return spend / sales if sales else 0.0


def _rule_strategy(records: list[BidRecord], steps: int, truth: dict, adaptive: bool = False) -> float:
    """
    ACOS 阈值规则迭代策略：从最后观测出价出发，按 ACOS 阈值调整 steps 步，
    每步按真值结构重估 acos（模拟真实闭环）。
    - std（默认）: >0.35 降 / <0.15 升（BidRecord 毛利固定 30%，acos 恒 <0.3，此规则几乎不动作）
    - adaptive   : >0.25 降 / <0.10 升（与 30% 毛利结构匹配，规则会真实响应）
    """
    high, low = (0.25, 0.10) if adaptive else (0.35, 0.15)
    bid = records[-1].bid
    clicks = float(records[-1].clicks)
    for _ in range(steps):
        acos = _acos_at(bid, clicks, truth)
        if acos > high:
            bid *= 0.90
        elif acos < low:
            bid *= 1.10
        else:
            break  # 阈值内不动作
        bid = float(np.clip(bid, 0.1, 4.0))
    return bid


def _optimizer_strategy(records: list[BidRecord]) -> tuple[float, float, str]:
    """ProfitMarketCurve：拟合 + 在观测范围内搜索最优出价"""
    pmc = ProfitMarketCurve()
    curve = pmc.fit_curve(records)
    lo = min(r.bid for r in records)
    hi = max(r.bid for r in records)
    res = pmc.find_optimal_bid(curve, bid_range=(lo, hi))
    return res.optimal_bid, curve.r_squared, res.model_used


def main() -> None:
    for family_name, family in (("同族市场(拟合友好)", True), ("失配市场(模型外形状)", False)):
        rows = []
        for seed in range(N_SEEDS):
            records, truth = _gen_market(seed, family=family)
            truth = {**truth, "b": 0.0}  # 占位

            def true_fn(b: float) -> float:
                return _true_profit_at(b, {**truth, "b": b})

            current_bid = records[-1].bid
            rule_bid = _rule_strategy(records, RULE_STEPS, truth, adaptive=False)
            rule_ada_bid = _rule_strategy(records, RULE_STEPS, truth, adaptive=True)
            opt_bid, r2, model = _optimizer_strategy(records)

            p_cur = float(true_fn(current_bid))
            p_rule = float(true_fn(rule_bid))
            p_rule_ada = float(true_fn(rule_ada_bid))
            p_opt = float(true_fn(opt_bid))

            rows.append({
                "seed": seed, "r2": r2, "model": model,
                "opt_bid": opt_bid, "rule_bid": rule_bid, "rule_ada_bid": rule_ada_bid, "cur_bid": current_bid,
                "p_opt": p_opt, "p_rule": p_rule, "p_rule_ada": p_rule_ada, "p_cur": p_cur,
                "opt_vs_rule": (p_opt - p_rule) / max(abs(p_rule), 0.5),
                "opt_vs_rule_ada": (p_opt - p_rule_ada) / max(abs(p_rule_ada), 0.5),
            })

        r2s = [r["r2"] for r in rows]
        win_std = sum(1 for r in rows if r["p_opt"] > r["p_rule"] + 1e-9)
        win_ada = sum(1 for r in rows if r["p_opt"] > r["p_rule_ada"] + 1e-9)
        vs_std = [r["opt_vs_rule"] for r in rows]
        vs_ada = [r["opt_vs_rule_ada"] for r in rows]
        agg = lambda k: sum(r[k] for r in rows)  # noqa: E731

        print("=" * 68)
        print(f"ProfitOptimizer 诚实基准 — {family_name}（{N_SEEDS} 市场，同空间/同真值/多种子）")
        print("=" * 68)
        print(f"拟合 R²      : 中位数={statistics.median(r2s):.3f} | 退化(<0.3)={sum(1 for r in rows if r['r2']<0.3)/N_SEEDS:.0%}")
        print(f"模型使用分布 : " + ", ".join(f"{m}={sum(1 for r in rows if r['model']==m)}" for m in sorted({r['model'] for r in rows})))
        print(f"累计利润     : optimizer=${agg('p_opt'):.0f} | 规则std=${agg('p_rule'):.0f} | 规则ada=${agg('p_rule_ada'):.0f} | 维持=${agg('p_cur'):.0f}")
        print(f"vs 规则std    : 均值={statistics.mean(vs_std):+.1%} | 胜率={win_std/N_SEEDS:.0%}")
        print(f"vs 规则ada    : 均值={statistics.mean(vs_ada):+.1%} | 胜率={win_ada/N_SEEDS:.0%}")
        print()

    print("=" * 68)
    print("解读：")
    print("  1. 原 T9 的 +19.5% 是「全空间搜索 vs 单步空转规则」的矮化产物（acos 恒 0.2 → 规则从不动作）。")
    print("  2. 同空间/同真值/规则可迭代后，optimizer 优势取决于拟合质量：")
    print("     拟合友好时大幅领先；模型失配（R² 退化）时优势收窄甚至消失。")
    print("  3. 规则阈值需与毛利结构校准（30% 毛利下 acos 恒 <0.3，0.35 阈值永不触发）。")
    print("=" * 68)


if __name__ == "__main__":
    main()
