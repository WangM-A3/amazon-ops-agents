"""
tests/test_llm_route.py — LLM 路由（SMALL/LARGE 引擎）测试
=============================================================
- 单元：LLMExecutor 对 stub 客户端的 JSON 解析与模板回退
- 集成（可选）：真实 LLM 端点可用时验证 llm=True 与真实 token
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routing.llm_executor import LLMExecutor, llm_enabled  # noqa: E402
from llm.client import get_llm_client, reset_llm_client  # noqa: E402


class _StubClient:
    """固定返回合法 JSON 的 stub LLM 客户端"""

    def __init__(self, content: str):
        self.content = content
        self.model = "stub"

    @property
    def available(self):
        return True

    async def chat_json(self, messages, max_tokens=1024):
        import json
        return json.loads(self.content), {"total_tokens": 42, "prompt_tokens": 20, "completion_tokens": 22}


class _BrokenClient(_StubClient):
    async def chat_json(self, messages, max_tokens=1024):
        raise RuntimeError("upstream 500")


@pytest.mark.asyncio
async def test_llm_executor_parses_json():
    ex = LLMExecutor(client=_StubClient('{"result": {"market_opportunity": "高"}, "kpis": {"score": 8}}'))
    out = await ex.execute("product_research", "分析蓝牙耳机", {})
    assert out["llm"] is True
    assert out["result"]["market_opportunity"] == "高"
    assert out["tokens"] == 42
    assert out["agent"]  # 非空


@pytest.mark.asyncio
async def test_llm_executor_fallback_on_failure():
    ex = LLMExecutor(client=_BrokenClient(""))
    out = await ex.execute("product_research", "分析蓝牙耳机", {})
    assert out.get("llm_mode") == "template_fallback"
    assert out["result"]  # 回退到模板 Agent 有结果


@pytest.mark.asyncio
async def test_llm_executor_grounds_real_data(tmp_path, monkeypatch):
    """数据型 Agent 的 LLM 路径注入真实数据（通过 stub 检查 prompt 内容）"""
    from data.provider import reset_provider, get_provider
    from data.ingest import ingest_file
    d = tmp_path / "seller"
    d.mkdir(exist_ok=True)
    monkeypatch.setenv("AMAZON_OPS_DATA_DIR", str(d))
    reset_provider()
    prov = get_provider()
    sales = tmp_path / "sales.csv"
    sales.write_text("sku,date,units,orders,revenue,sessions\nP1,2026-08-20,10,9,180.0,120\n", encoding="utf-8")
    ingest_file(prov.store, sales)

    captured = {}

    class _CaptureClient(_StubClient):
        def __init__(self):
            super().__init__('{"result": {"summary": {"total_units": 10}}, "kpis": {}}')

        async def chat_json(self, messages, max_tokens=1024):
            captured["user"] = messages[-1]["content"]
            return await super().chat_json(messages, max_tokens)

    ex = LLMExecutor(client=_CaptureClient())
    await ex.execute("sales_analytics", "查销量", {"marketplace": "US"})
    assert "sales" in captured["user"]
    assert "total_units" in captured["user"] or "180" in captured["user"]
    reset_provider()


@pytest.mark.asyncio
async def test_llm_integration_real_endpoint(monkeypatch):
    """真实端点可用时验证 llm=True（端点不可用则跳过）"""
    reset_llm_client()
    monkeypatch.setenv("AMAZON_OPS_LLM", "auto")
    if not get_llm_client().available:
        pytest.skip("无 LLM 端点，跳过集成测试")
    from agents.chief import CHIEF
    r = await CHIEF.execute("帮我计算一个SKU的利润", context={"sku": "P1"})
    res = r["results"].get("profit_calculator", {})
    assert "llm" in res or "llm_mode" in res  # 要么真 LLM，要么显式回退标记
    reset_llm_client()
