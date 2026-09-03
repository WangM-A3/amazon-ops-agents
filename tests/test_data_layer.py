"""
tests/test_data_layer.py — 真实数据层测试
===========================================
覆盖：SQLite 存储、CSV/JSON 导入、DataProvider 三级降级、
数据型 Agent 接入真实数据后的输出。
"""
import asyncio
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.provider import reset_provider, SOURCE_DEMO, SOURCE_LOCAL  # noqa: E402
from data.store import SellerDataStore  # noqa: E402
from data.ingest import ingest_file  # noqa: E402

_SALES_CSV = """sku,date,units,orders,revenue,sessions
P1,2026-08-20,10,9,180.0,120
P1,2026-08-21,12,11,216.0,140
P2,2026-08-20,4,4,60.0,50
"""
_PRODUCTS_CSV = """sku,title,marketplace,unit_cost,price
P1,样品A,US,3.0,18.0
P2,样品B,US,2.5,15.0
"""
_INV_CSV = """sku,stock,reserved,inbound
P1,50,2,100
P2,8,1,0
"""


@pytest.fixture()
def tmp_store(tmp_path):
    db = tmp_path / "db"
    store = SellerDataStore(db)
    yield store
    store.close()


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch, tmp_path):
    """每个测试独立数据目录，避免污染全局单例"""
    d = tmp_path / "seller"
    d.mkdir(exist_ok=True)
    monkeypatch.setenv("AMAZON_OPS_DATA_DIR", str(d))
    reset_provider()
    yield
    reset_provider()


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_ingest_csv_and_counts(tmp_store, tmp_path):
    ingest_file(tmp_store, _write(tmp_path, "sales.csv", _SALES_CSV))
    ingest_file(tmp_store, _write(tmp_path, "products.csv", _PRODUCTS_CSV))
    ingest_file(tmp_store, _write(tmp_path, "inventory.csv", _INV_CSV))
    counts = tmp_store.count_rows()
    assert counts["sales_daily"] == 3
    assert counts["products"] == 2
    assert counts["inventory"] == 2


def test_provider_mode_demo_when_empty():
    reset_provider()
    from data.provider import get_provider
    prov = get_provider()
    assert prov.mode == "demo"
    sales, src = prov.get_sales_summary()
    assert src == SOURCE_DEMO


def test_provider_mode_local_after_ingest(tmp_path):
    reset_provider()
    from data.provider import get_provider
    prov = get_provider()
    ingest_file(prov.store, _write(tmp_path, "sales.csv", _SALES_CSV))
    assert prov.mode == "local_store"
    sales, src = prov.get_sales_summary(days=30)
    assert src == SOURCE_LOCAL
    assert sales["total_units"] == 26
    assert sales["total_revenue"] == 456.0


@pytest.mark.asyncio
async def test_agents_use_real_data(tmp_path):
    reset_provider()
    from data.provider import get_provider
    prov = get_provider()
    for name, content in (("sales.csv", _SALES_CSV), ("products.csv", _PRODUCTS_CSV), ("inventory.csv", _INV_CSV)):
        ingest_file(prov.store, _write(tmp_path, name, content))
    from agents.base import AGENTS
    r = await AGENTS["sales_analytics"].execute("查销量", {"marketplace": "US"})
    assert r["result"]["data_source"].startswith("✅")
    assert r["result"]["summary"]["total_units"] == 26
    r2 = await AGENTS["inventory_planner"].execute("库存预警", {})
    assert r2["result"]["data_source"].startswith("✅")
    # P2 库存 8 件，日均 4 件 → days_left=2 → 紧急
    p2 = [x for x in r2["result"]["current_inventory"] if x["sku"] == "P2"][0]
    assert "紧急" in p2["status"]


def test_sp_api_client_degrades_without_credentials():
    from data.sp_api_client import SPAPIClient, SPAPIConfig
    cfg = SPAPIConfig(client_id="", client_secret="", refresh_token="")
    client = SPAPIClient(cfg)
    assert client.available is False
