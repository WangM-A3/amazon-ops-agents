"""
agents/real_data.py — 基于真实数据的 Agent 结果构建器
======================================================
供数据型 Agent（sales_analytics / inventory_planner / ppc_manager / profit_calculator
/ fba_manager / supply_chain）在 DataProvider 返回真实数据时，把原始数据组装成与
模板相同结构的结果 dict；无真实数据时回退到各 Agent 内置模板（保持原行为）。
"""
from __future__ import annotations

from typing import Any

from data.provider import SOURCE_LOCAL, SOURCE_SPAPI, SOURCE_DEMO

_SOURCE_LABEL = {
    SOURCE_LOCAL: "✅ 真实数据（本地导入 store）",
    SOURCE_SPAPI: "✅ 真实数据（SP-API 在线）",
    SOURCE_DEMO: "⚠️ 演示数据（未接入真实数据源）",
}


def source_tag(source: str) -> str:
    return _SOURCE_LABEL.get(source, source)


def build_sales_result(summary: dict[str, Any], source: str) -> dict[str, Any]:
    items = summary.get("items", [])
    total_rev = summary.get("total_revenue", 0.0)
    total_units = summary.get("total_units", 0)
    daily_avg = (total_rev / summary.get("days", 30)) if summary.get("days") else 0.0
    top = items[:5] if items else []
    return {
        "result": {
            "data_source": source_tag(source),
            "summary": {
                "period_days": summary.get("days", 30),
                "marketplace": summary.get("marketplace", "ALL"),
                "total_revenue": round(total_rev, 2),
                "total_units": int(total_units),
                "daily_avg_revenue": round(daily_avg, 2),
                "active_skus": len(items),
            },
            "top_products": [
                {
                    "sku": r["sku"], "title": r.get("title") or "",
                    "units": int(r["units"] or 0), "orders": int(r["orders"] or 0),
                    "revenue": round(r["revenue"] or 0, 2),
                    "avg_daily_units": round(r["avg_daily_units"] or 0, 1),
                    "share_pct": round((r["revenue"] or 0) / total_rev * 100, 1) if total_rev else 0,
                }
                for r in top
            ],
        },
        "kpis": {
            "total_revenue": round(total_rev, 2),
            "total_units": int(total_units),
            "daily_avg_revenue": round(daily_avg, 2),
            "top_sku": top[0]["sku"] if top else None,
        },
    }


def build_inventory_result(items: list[dict[str, Any]], source: str) -> dict[str, Any]:
    enriched = []
    for r in items:
        stock = int(r.get("stock") or 0)
        daily = float(r.get("daily_sales") or 0)
        days_left = int(stock / daily) if daily > 0 else 999
        status = "🚨 紧急" if days_left <= 10 else ("⚠️ 预警" if days_left <= 30 else "✅ 健康")
        enriched.append({
            "sku": r["sku"], "title": r.get("title") or "",
            "stock": stock, "reserved": int(r.get("reserved") or 0),
            "inbound": int(r.get("inbound") or 0),
            "daily_sales": daily, "days_left": days_left, "status": status,
            "updated_at": r.get("updated_at"),
        })
    stockout_risk = sum(1 for x in enriched if "紧急" in x["status"])
    return {
        "result": {
            "data_source": source_tag(source),
            "current_inventory": enriched,
            "stockout_risk_count": stockout_risk,
        },
        "kpis": {
            "skus": len(enriched),
            "stockout_risk_count": stockout_risk,
            "critical_skus": [x["sku"] for x in enriched if "紧急" in x["status"]][:5],
        },
    }


def build_ads_result(metrics: dict[str, Any], source: str) -> dict[str, Any]:
    total = metrics.get("total", {})
    camps = metrics.get("campaigns", [])
    breakdown = [
        {
            "campaign_id": c["campaign_id"], "sku": c.get("sku", ""), "type": c.get("ad_type", "sp"),
            "spend": round(c.get("spend") or 0, 2), "sales": round(c.get("sales") or 0, 2),
            "orders": int(c.get("orders") or 0), "impressions": int(c.get("impressions") or 0),
            "clicks": int(c.get("clicks") or 0),
            "acos": round((c.get("spend") or 0) / (c.get("sales") or 0), 4) if c.get("sales") else None,
        }
        for c in camps
    ]
    return {
        "result": {
            "data_source": source_tag(source),
            "campaign_overview": {
                "total_spend": round(total.get("spend") or 0, 2),
                "total_sales": round(total.get("sales") or 0, 2),
                "total_orders": int(total.get("orders") or 0),
                "total_clicks": int(total.get("clicks") or 0),
                "acos": round(total.get("acos") or 0, 4),
                "roas": round(total.get("roas") or 0, 4),
                "ctr": round(total.get("ctr") or 0, 4),
            },
            "campaign_breakdown": breakdown,
        },
        "kpis": {
            "acos": round(total.get("acos") or 0, 4),
            "roas": round(total.get("roas") or 0, 4),
            "campaigns": len(camps),
        },
    }


def build_profit_result(inputs: list[dict[str, Any]], source: str) -> dict[str, Any]:
    rows = []
    for r in inputs:
        price = float(r.get("price") or 0)
        cost = float(r.get("unit_cost") or 0)
        fba = float(r.get("fba_fee") or 0)
        ref_rate = float(r.get("referral_rate") or 0.15)
        referral = price * ref_rate
        total_cost = cost + fba + referral
        gross = price - total_cost
        margin = (gross / price) if price else 0.0
        rows.append({
            "sku": r["sku"], "title": r.get("title") or "",
            "selling_price": round(price, 2), "unit_cost": round(cost, 2),
            "fba_fee": round(fba, 2), "referral_fee": round(referral, 2),
            "total_cost": round(total_cost, 2),
            "gross_profit_per_unit": round(gross, 2),
            "gross_margin": round(margin, 4),
            "units_30d": int(r.get("units_30d") or 0),
            "revenue_30d": round(r.get("revenue_30d") or 0, 2),
        })
    return {
        "result": {
            "data_source": source_tag(source),
            "items": rows,
        },
        "kpis": {
            "skus": len(rows),
            "avg_margin": round(sum(x["gross_margin"] for x in rows) / len(rows), 4) if rows else 0.0,
        },
    }
