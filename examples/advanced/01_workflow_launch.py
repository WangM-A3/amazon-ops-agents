"""
示例4：工作流启动
适用场景：一键启动端到端业务流程（新品上架/广告优化/库存预警/客服）
"""

import httpx
import time


BASE_URL = "http://localhost:8080"


def poll_workflow(workflow_id: str, max_wait: int = 120) -> dict:
    """轮询工作流状态直到完成"""
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    start = time.time()
    while time.time() - start < max_wait:
        resp = client.get(f"/api/v1/workflow/{workflow_id}")
        wf = resp.json()
        status = wf.get("status", "unknown")

        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] 状态: {status} | 步骤: {wf.get('current_step', 0)}/{wf.get('total_steps', 0)}")

        if status in ["done", "failed"]:
            return wf

        time.sleep(3)

    return {"status": "timeout", "workflow_id": workflow_id}


def demo_new_product_workflow():
    """🆕 新品上架工作流"""
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 启动新品上架工作流
    resp = client.post("/api/v1/workflow", json={
        "workflow_id": "new_product_launch",
        "input": {
            "product_name": "3D打印桌面灯",
            "category": "Home & Kitchen",
            "marketplace": "US",
            "target_keywords": ["3d printed lamp", "desk lamp", "bedroom decor"],
            "price_range": [25, 45],
            "competition_level": "medium"
        }
    })

    wf = resp.json()
    print(f"📦 新品上架工作流已启动:")
    print(f"   工作流ID: {wf['workflow_id']}")
    print(f"   步骤数: {wf['total_steps']}")
    print(f"   预计耗时: {wf['estimated_seconds']}秒")
    print()

    # 轮询直到完成
    result = poll_workflow(wf["workflow_id"])

    print(f"\n{'='*50}")
    print(f"✅ 工作流完成! 状态: {result.get('status')}")
    if result.get("output"):
        for key, val in result["output"].items():
            print(f"   {key}: {str(val)[:100]}...")


def demo_ad_optimization_workflow():
    """📈 广告优化工作流"""
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    resp = client.post("/api/v1/workflow", json={
        "workflow_id": "ad_optimization",
        "input": {
            "sku": "ABC123",
            "marketplace": "US",
            "current_acos": 0.42,
            "target_acos": 0.25,
            "campaign_ids": ["sp-001", "sb-002"]
        }
    })

    wf = resp.json()
    print(f"\n📢 广告优化工作流已启动:")
    print(f"   工作流ID: {wf['workflow_id']}")
    print(f"   步骤数: {wf['total_steps']}")
    print(f"   预计耗时: {wf['estimated_seconds']}秒")
    print()

    result = poll_workflow(wf["workflow_id"])

    print(f"\n{'='*50}")
    print(f"✅ 工作流完成! 状态: {result.get('status')}")


def demo_inventory_alert_workflow():
    """📦 库存预警工作流"""
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    resp = client.post("/api/v1/workflow", json={
        "workflow_id": "inventory_alert",
        "input": {
            "marketplace": "US",
            "low_stock_threshold_days": 21,
            "include_supplier_lead_time": True
        }
    })

    wf = resp.json()
    print(f"\n📦 库存预警工作流已启动:")
    print(f"   工作流ID: {wf['workflow_id']}")
    print(f"   步骤数: {wf['total_steps']}")
    print(f"   预计耗时: {wf['estimated_seconds']}秒")
    print()

    result = poll_workflow(wf["workflow_id"])

    print(f"\n{'='*50}")
    print(f"✅ 工作流完成! 状态: {result.get('status')}")


def demo_list_workflows():
    """列出所有可用工作流"""
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    resp = client.get("/api/v1/workflows")
    data = resp.json()

    print("\n📋 可用工作流:")
    print(f"{'ID':<25} {'名称':<20} {'步骤':<6} {'耗时':<8}")
    print("-" * 65)
    for wf in data.get("workflows", []):
        print(f"{wf['id']:<25} {wf['name']:<20} {wf['steps']:<6} ~{wf['estimated_seconds']}s")


if __name__ == "__main__":
    print("=" * 60)
    print("亚马逊运营硅基军团 - 工作流启动示例")
    print("=" * 60)

    # 先查看可用工作流
    demo_list_workflows()

    # 演示广告优化工作流（较快）
    demo_ad_optimization_workflow()
