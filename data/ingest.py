"""
data/ingest.py — 卖家数据导入（CSV / JSON）
=============================================
把卖家提供的销量/库存/广告/产品表导入 SellerDataStore，是"无需 SP-API 即可接真实数据"的
最短路径：用户把运营报表导出为 CSV，即可让 Agent 基于真实数字工作。

支持的列名（自动识别，兼容中英文/大小写）：
- products:  sku/asin/title/市场(marketplace)/成本(unit_cost)/售价(price)/佣金率/仓储费
- sales:     sku/日期(date)/销量(units)/订单(orders)/销售额(revenue)/访问(sessions)
- inventory: sku/库存(stock)/预留(reserved)/在途(inbound)
- ads:       campaign_id/日期(date)/sku/广告类型(ad_type)/展示(impressions)/点击(clicks)/花费(spend)/销售额(sales)/订单(orders)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .store import SellerDataStore


def _norm_key(k: str) -> str:
    m = {
        "sku": "sku", "asin": "asin", "title": "title", "名称": "title",
        "marketplace": "marketplace", "市场": "marketplace", "站点": "marketplace",
        "unit_cost": "unit_cost", "成本": "unit_cost", "采购成本": "unit_cost",
        "price": "price", "售价": "price", "价格": "price",
        "referral_rate": "referral_rate", "佣金率": "referral_rate",
        "fba_fee": "fba_fee", "fba费用": "fba_fee", "仓储费": "fba_fee",
        "date": "date", "日期": "date", "day": "date", "时间": "date",
        "units": "units", "销量": "units", "件数": "units",
        "orders": "orders", "订单": "orders", "订单数": "orders",
        "revenue": "revenue", "销售额": "revenue", "销售": "revenue", "gmv": "revenue",
        "sessions": "sessions", "访问": "sessions", "流量": "sessions",
        "stock": "stock", "库存": "stock", "可售": "stock",
        "reserved": "reserved", "预留": "reserved",
        "inbound": "inbound", "在途": "inbound",
        "campaign_id": "campaign_id", "活动id": "campaign_id", "campaign": "campaign_id",
        "ad_type": "ad_type", "广告类型": "ad_type",
        "impressions": "impressions", "展示": "impressions", "曝光": "impressions",
        "clicks": "clicks", "点击": "clicks",
        "spend": "spend", "花费": "spend", "广告花费": "spend", "cost": "spend",
        "sales": "sales", "广告销售额": "sales",
    }
    key = str(k).strip().lower().replace(" ", "").replace("_", "")
    # 中英别名直接映射，其余按去除分隔符后的归一化键查表
    for kk, vv in m.items():
        if key == kk.replace("_", "").lower():
            return vv
    # 拼音/英文近似
    if key in ("campaignid", "campaigns"):
        return "campaign_id"
    if key in ("adtype",):
        return "ad_type"
    return str(k).strip()


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        return [{_norm_key(k): v for k, v in row.items()} for row in reader]


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("rows", "data", "items", "records"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError(f"JSON 必须是列表或含 rows/data/items 字段的对象: {path}")
    return [{_norm_key(k): v for k, v in row.items()} for row in data]


def _classify(rows: list[dict[str, Any]]) -> str:
    """按列名把一组行分派到 products / sales / inventory / ads"""
    keys = {k for r in rows for k in r.keys()}
    if "campaign_id" in keys:
        return "ads"
    if "stock" in keys or "inbound" in keys:
        return "inventory"
    if "unit_cost" in keys or ("price" in keys and "title" in keys):
        return "products"
    return "sales"


def ingest_file(store: SellerDataStore, path: str | Path) -> dict[str, int]:
    """导入单个文件（按列名自动识别表）"""
    path = Path(path)
    if path.suffix.lower() == ".json":
        rows = _read_json_rows(path)
    else:
        rows = _read_csv_rows(path)
    if not rows:
        return {"rows": 0, "table": "none"}
    kind = _classify(rows)
    if kind == "products":
        n = store.upsert_products(rows)
    elif kind == "inventory":
        n = store.upsert_inventory(rows)
    elif kind == "ads":
        n = store.upsert_ads(rows)
    else:
        n = store.upsert_sales(rows)
    return {"rows": n, "table": kind}


def ingest_dir(store: SellerDataStore, data_dir: str | Path) -> list[dict[str, Any]]:
    """批量导入目录下所有 .csv/.json（按文件名前缀提示类别）"""
    results = []
    for f in sorted(Path(data_dir).glob("*.csv")) + sorted(Path(data_dir).glob("*.json")):
        try:
            results.append({"file": f.name, **ingest_file(store, f)})
        except Exception as exc:  # noqa: BLE001
            results.append({"file": f.name, "error": str(exc)})
    return results
