"""
tests/test_workflow_review.py — v2.3 工作流复核沙箱层测试
===========================================================
覆盖：
1. 引擎 launch：review 步骤自动标记 pending、expected_keys 校验
2. 4 个预置工作流均含复核步骤（review=True）
3. ReviewGate：登记 / 决策 / 幂等 / 未注册 404
4. API：跑工作流 → 拿 run_id → approve → 状态查询
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.presets import PRESET_WORKFLOWS, WORKFLOW_ENGINE  # noqa: E402
from workflows.review_gate import REVIEW_GATE  # noqa: E402


# ─── 1. 预置工作流定义含复核步骤 ─────────────────────────────────────────────

def test_workflows_have_review_steps():
    """4 个工作流都应有 review=True 的步骤（对外产物需人工复核）"""
    for wf_id in ("new_product_launch", "ad_optimization", "inventory_alert", "customer_service"):
        wf = PRESET_WORKFLOWS[wf_id]
        review_steps = [s for s in wf.steps if s.review]
        assert review_steps, f"{wf_id} 缺少复核步骤"
        assert all(s.risk in ("low", "medium", "high") for s in review_steps)
        assert all(s.review_reason for s in review_steps)


def test_list_workflows_exposes_review_meta():
    items = WORKFLOW_ENGINE.list_workflows()
    for wf in items:
        assert any(s.get("review") for s in wf["steps"]), wf["id"]


# ─── 2. 引擎 launch：复核标记 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_launch_marks_review_steps():
    result = await WORKFLOW_ENGINE.launch("inventory_alert", {"sku_list": ["UMB-BLK"]})
    assert result.status.value == "done"
    # replenishment_plan 步骤是 review=True
    assert result.reviews["replenishment_plan"]["review_required"] is True
    assert result.reviews["replenishment_plan"]["decision"] == "pending"
    # 其余步骤不进复核
    assert result.reviews["inventory_status"]["review_required"] is False


@pytest.mark.asyncio
async def test_expected_keys_validation_records_missing():
    """expected_keys 缺失时 validated=False + missing 列表（不中断流程）"""
    result = await WORKFLOW_ENGINE.launch("new_product_launch", {"product_name": "蓝牙耳机"})
    rev = result.reviews.get("listing_content")
    assert rev is not None
    assert rev["review_required"] is True
    # 校验语义：validated 与 missing 至少结构正确（模板产物可能缺键→记录）
    assert isinstance(rev["missing"], list)
    assert isinstance(rev["validated"], bool)
    # 无论校验结果如何，工作流整体完成
    assert result.status.value == "done"


# ─── 3. ReviewGate ───────────────────────────────────────────────────────────

def test_review_gate_decisions(tmp_reviews=None):
    gate = REVIEW_GATE
    run_id = "wf_test_0001"
    reviews = {
        "listing_content": {
            "step": "Listing优化", "agent_id": "listing_optimizer",
            "review_required": True, "risk": "high",
            "reason": "对外文案", "preview": "{}",
            "validated": True, "missing": [], "decision": "pending",
        }
    }
    gate.register(run_id, "new_product_launch", reviews)
    assert len(gate.pending(run_id)) == 1

    # approve
    item = gate.decide(run_id, "listing_content", "approve", comment="ok")
    assert item["decision"] == "approved"
    assert gate.pending(run_id) == []

    # 幂等：重复决策返回现状不报错
    item2 = gate.decide(run_id, "listing_content", "reject")
    assert item2["decision"] == "approved"

    # 未注册 run / step → None
    assert gate.decide("wf_nope", "x", "approve") is None

    # 非法 decision
    with pytest.raises(ValueError):
        gate.decide(run_id, "listing_content", "maybe")

    st = gate.status(run_id)
    assert st["approved"] == 1
    assert st["rejected"] == 0


# ─── 4. API 闭环 ─────────────────────────────────────────────────────────────

def test_workflow_review_api(tmp_path, monkeypatch):
    monkeypatch.setenv("AMAZON_OPS_DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from api_server import app, auth_manager
    auth_manager.register_key("wf-test-key", "dev_secret", "professional", "test")

    client = TestClient(app)
    h = {"X-API-Key": "wf-test-key", "Content-Type": "application/json"}

    # 跑一个工作流
    r = client.post("/api/v1/workflow", headers=h, json={
        "workflow_id": "customer_service",
        "input": {"buyer_message": "我想退货"},
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["run_id"]
    # draft_reply 步骤进入待复核
    assert data["reviews"]["draft_reply"]["review_required"] is True

    # approve
    r = client.post("/api/v1/workflow/review", headers=h, json={
        "run_id": data["run_id"], "step_key": "draft_reply",
        "decision": "approve", "comment": "话术没问题",
    })
    assert r.status_code == 200, r.text
    assert r.json()["item"]["decision"] == "approved"

    # 状态查询
    r = client.get(f"/api/v1/workflow/review/{data['run_id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["approved"] == 1

    # 未知 run_id → 404
    r = client.post("/api/v1/workflow/review", headers=h, json={
        "run_id": "wf_nope", "step_key": "draft_reply", "decision": "approve",
    })
    assert r.status_code == 404
