"""
data/__init__.py — 真实数据层
真实度三级：local_store（SQLite 导入）→ sp_api（SP-API 在线）→ demo（模板回退）
"""
from .store import SellerDataStore
from .ingest import ingest_file, ingest_dir
from .sp_api_client import SPAPIClient, SPAPIConfig
from .provider import DataProvider, get_provider, reset_provider, SOURCE_LOCAL, SOURCE_SPAPI, SOURCE_DEMO

__all__ = [
    "SellerDataStore", "ingest_file", "ingest_dir",
    "SPAPIClient", "SPAPIConfig",
    "DataProvider", "get_provider", "reset_provider",
    "SOURCE_LOCAL", "SOURCE_SPAPI", "SOURCE_DEMO",
]
