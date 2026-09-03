"""
data/provider.py — 统一数据提供层（DataProvider）
====================================================
Agent 的唯一数据入口。三级真实度自动降级：

1. REAL_STORE  : 本地 SQLite（用户上传/导入的真实数据）      -> data_source: "local_store"
2. REAL_SPAPI  : SP-API 在线拉取（有凭据时）                 -> data_source: "sp_api"
3. DEMO        : 内置模板演示数据（无任何真实数据时）         -> data_source: "demo"

用法（Agent 内）：
    from data.provider import get_provider
    prov = get_provider()
    sales = prov.get_sales_summary(marketplace="US", days=30)
    # -> (payload, source) 其中 source 标记数据真实度
"""
from __future__ import annotations

import logging
from typing import Any

from .store import SellerDataStore
from .sp_api_client import SPAPIClient

logger = logging.getLogger("amazon_ops.data_provider")

SOURCE_LOCAL = "local_store"
SOURCE_SPAPI = "sp_api"
SOURCE_DEMO = "demo"


class DataProvider:
    def __init__(self, store: SellerDataStore | None = None, sp: SPAPIClient | None = None) -> None:
        self.store = store or SellerDataStore()
        self.sp = sp or SPAPIClient()

    # ── 真实度判断 ────────────────────────────────────────────────────────────
    def has_local_data(self) -> bool:
        counts = self.store.count_rows()
        return counts["sales_daily"] > 0 or counts["inventory"] > 0 or counts["ads_daily"] > 0

    @property
    def mode(self) -> str:
        if self.sp.available:
            return "sp_api"
        if self.has_local_data():
            return "local_store"
        return "demo"

    # ── 业务查询（统一返回 (payload, source)）────────────────────────────────
    def get_sales_summary(self, marketplace: str | None = None, days: int = 30) -> tuple[dict[str, Any], str]:
        if self.has_local_data():
            return self.store.get_sales_summary(marketplace=marketplace, days=days), SOURCE_LOCAL
        return {}, SOURCE_DEMO

    def get_inventory(self) -> tuple[list[dict[str, Any]], str]:
        if self.has_local_data():
            return self.store.get_inventory(), SOURCE_LOCAL
        return [], SOURCE_DEMO

    def get_ads_metrics(self, days: int = 30) -> tuple[dict[str, Any], str]:
        if self.has_local_data():
            return self.store.get_ads_metrics(days=days), SOURCE_LOCAL
        return {"campaigns": [], "total": {}}, SOURCE_DEMO

    def get_profit_inputs(self, sku: str | None = None) -> tuple[list[dict[str, Any]], str]:
        if self.has_local_data():
            return self.store.get_profit_inputs(sku=sku), SOURCE_LOCAL
        return [], SOURCE_DEMO

    def get_supplier_quotes(self, product_keyword: str = "") -> tuple[list[dict[str, Any]], str]:
        """供应链（供应商交期/报价）：真实模式无外部源时返回空，由 supply_chain Agent 回退模板"""
        return [], SOURCE_DEMO


_provider: DataProvider | None = None


def get_provider() -> DataProvider:
    """全局单例（可用 AMAZON_OPS_DATA_DIR 指向不同数据目录做测试隔离）"""
    global _provider
    if _provider is None:
        _provider = DataProvider()
    return _provider


def reset_provider() -> None:
    global _provider
    if _provider is not None:
        try:
            _provider.store.close()
        except Exception:  # noqa: BLE001
            pass
    _provider = None
