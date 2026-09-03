"""
data/store.py — 卖家数据 SQLite 存储
=====================================
真实数据层的本地落点：产品 / 日销量 / 库存 / 广告投放。

- 数据来源: 用户上传 CSV/JSON（data/ingest.py）或 SP-API 同步（data/sp_api_client.py）
- 查询接口供 DataProvider（data/provider.py）统一暴露给 Agent
- 全部基于标准库 sqlite3，无外部依赖
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional


DEFAULT_DATA_DIR = os.getenv("AMAZON_OPS_DATA_DIR", "data/seller")


def _d(s: str | None) -> str:
    """规范化日期字符串 YYYY-MM-DD"""
    if not s:
        return date.today().isoformat()
    s = str(s).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    for fmt in ("%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s[:10]


def _f(v: Any) -> float:
    try:
        return float(str(v).replace("$", "").replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return 0.0


def _default_data_dir() -> str:
    """实例化时读取，保证测试/多环境可用 env 隔离"""
    return os.getenv("AMAZON_OPS_DATA_DIR", "data/seller")


class SellerDataStore:
    """SQLite 卖家数据存储"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path(_default_data_dir()) / "seller.db"
        else:
            db_path = Path(db_path)
            # 目录或无扩展名 -> 视为数据目录，追加 seller.db
            if db_path.is_dir() or not db_path.suffix:
                db_path = db_path / "seller.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    sku TEXT PRIMARY KEY,
                    asin TEXT, title TEXT, marketplace TEXT DEFAULT 'US',
                    unit_cost REAL DEFAULT 0, price REAL DEFAULT 0,
                    referral_rate REAL DEFAULT 0.15, fba_fee REAL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS sales_daily (
                    sku TEXT NOT NULL, date TEXT NOT NULL,
                    units INTEGER DEFAULT 0, orders INTEGER DEFAULT 0,
                    revenue REAL DEFAULT 0, sessions INTEGER DEFAULT 0,
                    PRIMARY KEY (sku, date)
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    sku TEXT PRIMARY KEY,
                    stock INTEGER DEFAULT 0, reserved INTEGER DEFAULT 0,
                    inbound INTEGER DEFAULT 0, updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS ads_daily (
                    campaign_id TEXT NOT NULL, date TEXT NOT NULL,
                    sku TEXT DEFAULT '', ad_type TEXT DEFAULT 'sp',
                    impressions INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0,
                    spend REAL DEFAULT 0, sales REAL DEFAULT 0, orders INTEGER DEFAULT 0,
                    PRIMARY KEY (campaign_id, date)
                );
                CREATE INDEX IF NOT EXISTS idx_sales_sku_date ON sales_daily(sku, date);
                CREATE INDEX IF NOT EXISTS idx_ads_date ON ads_daily(date);
                """
            )

    # ── 写入 ──────────────────────────────────────────────────────────────────
    def upsert_products(self, rows: list[dict[str, Any]]) -> int:
        with self._conn:
            n = 0
            for r in rows:
                self._conn.execute(
                    """INSERT INTO products(sku, asin, title, marketplace, unit_cost, price, referral_rate, fba_fee)
                       VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(sku) DO UPDATE SET
                         asin=excluded.asin, title=excluded.title, marketplace=excluded.marketplace,
                         unit_cost=excluded.unit_cost, price=excluded.price,
                         referral_rate=excluded.referral_rate, fba_fee=excluded.fba_fee""",
                    (r.get("sku"), r.get("asin", ""), r.get("title", ""),
                     r.get("marketplace", "US"), _f(r.get("unit_cost")), _f(r.get("price")),
                     _f(r.get("referral_rate", 0.15)), _f(r.get("fba_fee"))),
                )
                n += 1
        return n

    def upsert_sales(self, rows: list[dict[str, Any]]) -> int:
        with self._conn:
            n = 0
            for r in rows:
                self._conn.execute(
                    """INSERT INTO sales_daily(sku, date, units, orders, revenue, sessions)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(sku, date) DO UPDATE SET
                         units=excluded.units, orders=excluded.orders,
                         revenue=excluded.revenue, sessions=excluded.sessions""",
                    (r.get("sku"), _d(r.get("date")), int(_f(r.get("units"))),
                     int(_f(r.get("orders", r.get("units")))), _f(r.get("revenue")),
                     int(_f(r.get("sessions")))),
                )
                n += 1
        return n

    def upsert_inventory(self, rows: list[dict[str, Any]]) -> int:
        with self._conn:
            n = 0
            now = datetime.now().isoformat(timespec="seconds")
            for r in rows:
                self._conn.execute(
                    """INSERT INTO inventory(sku, stock, reserved, inbound, updated_at)
                       VALUES(?,?,?,?,?)
                       ON CONFLICT(sku) DO UPDATE SET
                         stock=excluded.stock, reserved=excluded.reserved,
                         inbound=excluded.inbound, updated_at=excluded.updated_at""",
                    (r.get("sku"), int(_f(r.get("stock"))), int(_f(r.get("reserved"))),
                     int(_f(r.get("inbound"))), now),
                )
                n += 1
        return n

    def upsert_ads(self, rows: list[dict[str, Any]]) -> int:
        with self._conn:
            n = 0
            for r in rows:
                self._conn.execute(
                    """INSERT INTO ads_daily(campaign_id, date, sku, ad_type, impressions, clicks, spend, sales, orders)
                       VALUES(?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(campaign_id, date) DO UPDATE SET
                         sku=excluded.sku, ad_type=excluded.ad_type,
                         impressions=excluded.impressions, clicks=excluded.clicks,
                         spend=excluded.spend, sales=excluded.sales, orders=excluded.orders""",
                    (r.get("campaign_id"), _d(r.get("date")), r.get("sku", ""),
                     r.get("ad_type", "sp"), int(_f(r.get("impressions"))),
                     int(_f(r.get("clicks"))), _f(r.get("spend")), _f(r.get("sales")),
                     int(_f(r.get("orders")))),
                )
                n += 1
        return n

    # ── 查询 ──────────────────────────────────────────────────────────────────
    def count_rows(self) -> dict[str, int]:
        with self._conn:
            out = {}
            for t in ("products", "sales_daily", "inventory", "ads_daily"):
                out[t] = self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return out

    def get_sales_summary(self, marketplace: str | None = None, days: int = 30) -> dict[str, Any]:
        """近 N 天销售汇总（按 sku 聚合）"""
        since = (date.today() - timedelta(days=days)).isoformat()
        sql = """SELECT s.sku, p.title, p.marketplace, p.price,
                        SUM(s.units) AS units, SUM(s.orders) AS orders, SUM(s.revenue) AS revenue,
                        AVG(s.units) AS avg_daily_units, SUM(s.sessions) AS sessions
                 FROM sales_daily s LEFT JOIN products p ON p.sku = s.sku
                 WHERE s.date >= ? """
        params: list[Any] = [since]
        if marketplace:
            sql += "AND (p.marketplace = ? OR p.marketplace IS NULL) "
            params.append(marketplace)
        sql += " GROUP BY s.sku ORDER BY revenue DESC"
        with self._conn:
            rows = [dict(r) for r in self._conn.execute(sql, params).fetchall()]
        return {
            "days": days,
            "marketplace": marketplace or "ALL",
            "items": rows,
            "total_revenue": sum(r["revenue"] for r in rows),
            "total_units": sum(r["units"] for r in rows),
        }

    def get_inventory(self) -> list[dict[str, Any]]:
        with self._conn:
            rows = [dict(r) for r in self._conn.execute(
                """SELECT i.sku, p.title, i.stock, i.reserved, i.inbound, i.updated_at
                   FROM inventory i LEFT JOIN products p ON p.sku = i.sku
                   ORDER BY i.stock ASC""").fetchall()]
        # 附带近 14 天日均销量
        since = (date.today() - timedelta(days=14)).isoformat()
        with self._conn:
            for r in rows:
                row = self._conn.execute(
                    "SELECT AVG(units) AS avg_units FROM sales_daily WHERE sku=? AND date>=?",
                    (r["sku"], since)).fetchone()
                r["daily_sales"] = round(float(row["avg_units"] or 0), 1)
        return rows

    def get_ads_metrics(self, days: int = 30) -> dict[str, Any]:
        since = (date.today() - timedelta(days=days)).isoformat()
        with self._conn:
            rows = [dict(r) for r in self._conn.execute(
                """SELECT campaign_id, sku, ad_type,
                          SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                          SUM(spend) AS spend, SUM(sales) AS sales, SUM(orders) AS orders
                   FROM ads_daily WHERE date >= ?
                   GROUP BY campaign_id ORDER BY spend DESC""", (since,)).fetchall()]
        total = {"impressions": 0, "clicks": 0, "spend": 0.0, "sales": 0.0, "orders": 0}
        for r in rows:
            for k in total:
                total[k] += r.get(k, 0)
        total["ctr"] = (total["clicks"] / total["impressions"]) if total["impressions"] else 0.0
        total["acos"] = (total["spend"] / total["sales"]) if total["sales"] else 0.0
        total["roas"] = (total["sales"] / total["spend"]) if total["spend"] else 0.0
        return {"days": days, "campaigns": rows, "total": total}

    def get_profit_inputs(self, sku: str | None = None) -> list[dict[str, Any]]:
        """利润核算输入：成本/售价/FBA/佣金 + 近 30 天销量"""
        since = (date.today() - timedelta(days=30)).isoformat()
        sql = """SELECT p.sku, p.title, p.unit_cost, p.price, p.referral_rate, p.fba_fee,
                        COALESCE(SUM(s.units),0) AS units_30d,
                        COALESCE(SUM(s.revenue),0) AS revenue_30d
                 FROM products p LEFT JOIN sales_daily s ON s.sku = p.sku AND s.date >= ?
                 WHERE 1=1 """
        params: list[Any] = [since]
        if sku:
            sql += "AND p.sku = ? "
            params.append(sku)
        sql += " GROUP BY p.sku"
        with self._conn:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def close(self) -> None:
        self._conn.close()
