"""
tests/test_experience_memory.py — v2.1 经验记忆闭环测试
==========================================================
覆盖：
1. ExperienceStore CRUD + 关键词匹配检索
2. 质量门：负反馈样本足够且成功率低 → 不再注入
3. 打分回写：连续低分自动停用（active=0）
4. 注入集成：LLMExecutor stub 客户端下，经验文本进入 prompt 且透出 experience_used
5. API：/api/v1/memory/experience 增查、/api/v1/memory/rating 打分闭环
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.experience_store import (  # noqa: E402
    NEG_SAMPLE_BEFORE_GATE,
    ExperienceStore,
    apply_rating,
    create_experience,
    deactivate_experience,
    list_experiences,
    retrieve_experiences,
)


# ─── 1. 存储与检索 ───────────────────────────────────────────────────────────

def test_store_crud_and_keyword_retrieve(tmp_path):
    store = ExperienceStore(tmp_path)
    eid = store.add(
        "ppc_manager", "高ACOS处理", "先否定高花费无转化词，再提SB预算",
        keywords=["acos", "广告"],
    )
    assert eid > 0

    # 关键词命中 → 检索到
    hits = store.retrieve("ppc_manager", "我的广告ACOS太高了怎么优化")
    assert len(hits) == 1
    assert hits[0]["id"] == eid
    assert hits[0]["title"] == "高ACOS处理"

    # 无关任务 → 不命中
    assert store.retrieve("ppc_manager", "帮我看看库存") == []

    # 其他 Agent 不共享
    assert store.retrieve("sales_analytics", "广告ACOS太高") == []

    # 停用后不再命中
    store.set_active(eid, False)
    assert store.retrieve("ppc_manager", "广告ACOS太高") == []


def test_store_retrieve_orders_by_more_keyword_hits(tmp_path):
    store = ExperienceStore(tmp_path)
    a = store.add("ppc_manager", "通用建议", "通用", keywords=["广告"])
    b = store.add("ppc_manager", "精准建议", "精准", keywords=["广告", "acos"])
    hits = store.retrieve("ppc_manager", "广告acos怎么降")
    assert hits[0]["id"] == b  # 命中 2 词的经验排前面


# ─── 2. 质量门与打分闭环 ─────────────────────────────────────────────────────

def test_low_success_rate_experience_is_skipped(tmp_path):
    store = ExperienceStore(tmp_path)
    eid = store.add("ppc_manager", "烂经验", "错误策略", keywords=["acos"])
    # 打 4 次分：全部差评（<=2）
    for r in (1, 2, 2, 1):
        store.rate(eid, r)
    # 样本足够 + 成功率 0% < 50% → 检索自动跳过（软过滤）
    assert store.retrieve("ppc_manager", "acos怎么优化") == []
    # 同时自动停用
    exp = store.get(eid)
    assert exp["active"] == 0
    assert exp["neg_count"] == 4


def test_good_experience_stays_active_and_counts(tmp_path):
    store = ExperienceStore(tmp_path)
    eid = store.add("sales_analytics", "好经验", "按SKU拆分看", keywords=["销售"])
    store.rate(eid, 5)
    store.rate(eid, 4)
    hits = store.retrieve("sales_analytics", "销售情况")
    assert [h["id"] for h in hits] == [eid]
    exp = store.get(eid)
    assert exp["pos_count"] == 2
    assert exp["neg_count"] == 0
    assert exp["success_rate"] == 1.0
    # hit_count 已累加
    assert exp["hit_count"] >= 1


def test_rating_requires_enough_samples_to_deactivate(tmp_path):
    store = ExperienceStore(tmp_path)
    eid = store.add("ppc_manager", "边缘经验", "策略", keywords=["acos"])
    store.rate(eid, 1)  # 仅 1 条负反馈，样本不足 → 不停用
    assert store.get(eid)["active"] == 1


# ─── 3. 模块级便捷函数 ──────────────────────────────────────────────────────

def test_module_functions(tmp_path, monkeypatch):
    monkeypatch.setenv("AMAZON_OPS_DATA_DIR", str(tmp_path))
    # 模块级函数默认走 env 目录
    from memory import experience_store as mod
    mod._store = None  # 重置单例，指向 tmp
    exp = create_experience("ppc_manager", "经验X", "内容X", ["acos"])
    assert exp["id"] > 0
    assert list_experiences(agent_id="ppc_manager")[0]["id"] == exp["id"]
    updated = apply_rating(exp["id"], 5)
    assert updated["pos_count"] == 1
    assert deactivate_experience(exp["id"]) is True
    assert retrieve_experiences("ppc_manager", "acos问题") == []
    mod._store = None  # 还原，避免污染后续


# ─── 4. 注入集成（LLMExecutor + stub 客户端）────────────────────────────────

class _CaptureClient:
    """捕获 prompt 并返回合法 JSON 的 stub 客户端"""

    def __init__(self):
        self.captured = ""
        self.model = "stub"

    @property
    def available(self):
        return True

    async def chat_json(self, messages, max_tokens=1024):
        self.captured = "\n".join(m.get("content", "") for m in messages)
        payload = {"result": {"summary": "ok"}, "kpis": {}}
        return payload, {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5}


@pytest.mark.asyncio
async def test_experience_injected_into_llm_prompt(tmp_path, monkeypatch):
    from routing.llm_executor import LLMExecutor

    monkeypatch.setenv("AMAZON_OPS_DATA_DIR", str(tmp_path))
    from memory import experience_store as mod
    mod._store = None
    create_experience(
        "ppc_manager", "先否定再提预算",
        "高ACOS：先否定高花费无转化词，再提高SB预算",
        ["acos", "广告"],
    )

    stub = _CaptureClient()
    ex = LLMExecutor(client=stub)
    out = await ex.execute("ppc_manager", "我的广告ACOS太高了，怎么优化", {})
    # 经验文本注入到 prompt
    assert "高ACOS：先否定高花费无转化词" in stub.captured
    # 命中记录透出
    assert out["experience_used"] and out["experience_used"][0]["title"] == "先否定再提预算"
    # 无关经验不注入
    stub2 = _CaptureClient()
    await LLMExecutor(client=stub2).execute("sales_analytics", "看看销量", {})
    assert "高ACOS：先否定高花费无转化词" not in stub2.captured
    mod._store = None


# ─── 5. API 闭环 ────────────────────────────────────────────────────────────

def test_memory_api_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("AMAZON_OPS_DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from api_server import app, auth_manager

    # AuthManager 是模块级单例，可能在别的测试先 import 时已初始化 → 显式注册 key
    auth_manager.register_key("mem-test-key", "dev_secret", "professional", "test")

    client = TestClient(app)
    h = {"X-API-Key": "mem-test-key", "Content-Type": "application/json"}

    # 新增经验
    r = client.post("/api/v1/memory/experience", headers=h, json={
        "agent_id": "ppc_manager",
        "title": "否定词优先",
        "content": "先否定再提预算",
        "keywords": ["acos"],
    })
    assert r.status_code == 200, r.text
    exp_id = r.json()["experience"]["id"]

    # 列表
    r = client.get("/api/v1/memory/experience", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # 无鉴权 → 401
    r = client.get("/api/v1/memory/experience")
    assert r.status_code == 401

    # 打分回写（直接指定 experience_ids）
    r = client.post("/api/v1/memory/rating", headers=h, json={
        "experience_ids": [exp_id], "rating": 5,
    })
    assert r.status_code == 200, r.text
    assert r.json()["updated"][0]["pos_count"] == 1

    # 任务级回写：execute 未命中经验（LLM 关）→ task_id 无命中记录 → 404
    r = client.post("/api/v1/memory/rating", headers=h, json={
        "task_id": "nope-0000", "rating": 3,
    })
    assert r.status_code == 404

    # 停用
    r = client.post(f"/api/v1/memory/experience/{exp_id}/deactivate", headers=h)
    assert r.status_code == 200
    r = client.get("/api/v1/memory/experience", headers=h)
    assert r.json()["total"] == 0  # 默认只列启用中的
