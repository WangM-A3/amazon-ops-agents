"""
示例6：外部API集成
适用场景：集成Helium 10、Jungle Scout、Keepa、船长ERP等第三方工具
"""

import httpx
import os


BASE_URL = os.environ.get("AMAZON_OPS_URL", "http://localhost:8080")
client = httpx.Client(base_url=BASE_URL, timeout=90.0)


def demo_helium10_integration():
    """集成 Helium 10 进行选品分析"""
    print("🔧 Helium 10 集成示例")

    # 模拟 Helium 10 API 调用（实际使用时替换为真实 API Key）
    api_key = os.environ.get("HELIUM10_API_KEY", "demo_key")

    resp = client.post("/api/v1/execute", json={
        "task": "使用Helium 10分析厨房用品类目，找到月销>1000、竞争度低的产品",
        "tool": "helium10",
        "api_key": api_key,
        "category": "Kitchen & Dining",
        "filters": {
            "monthly_revenue_min": 5000,
            "review_count_max": 100,
            "bsr_range": "1-50000",
            "fba_only": True,
            "prime_only": True
        },
        "sort_by": "opportunity_score"
    })
    data = resp.json()
    print(f"  Agent: {data.get('agent')}")
    print(f"  结果: {data.get('result', '')[:300]}")


def demo_keepa_integration():
    """集成 Keepa 分析价格趋势"""
    print("\n📈 Keepa 集成示例")

    api_key = os.environ.get("KEEPA_API_KEY", "demo_key")

    resp = client.post("/api/v1/execute", json={
        "task": "用Keepa分析竞品B0XXXXXX的180天价格历史和BuyBox价格",
        "tool": "keepa",
        "api_key": api_key,
        "asin": "B0XXXXXX",
        "days": 180,
        "include": ["price_history", "buybox_history", "rating_history"]
    })
    data = resp.json()
    print(f"  Agent: {data.get('agent')}")
    print(f"  结果: {data.get('result', '')[:300]}")


def demo_junglescout_integration():
    """集成 Jungle Scout 进行产品数据库查询"""
    print("\n🔍 Jungle Scout 集成示例")

    api_key = os.environ.get("JUNGLESCOUT_API_KEY", "demo_key")

    resp = client.post("/api/v1/execute", json={
        "task": "用Jungle Scout查询宠物用品类目月销前20的产品",
        "tool": "junglescout",
        "api_key": api_key,
        "category": "Pet Supplies",
        "filters": {
            "monthly_sales_min": 1000,
            "review_count_max": 200,
            "price_min": 15,
            "price_max": 80
        },
        "limit": 20
    })
    data = resp.json()
    print(f"  Agent: {data.get('agent')}")
    print(f"  结果: {data.get('result', '')[:300]}")


def demo_captain_erp_integration():
    """集成 船长ERP（Captain ERP）进行数据同步"""
    print("\n🚢 船长ERP集成示例")

    api_key = os.environ.get("CAPTAIN_API_KEY", "demo_key")
    store_id = os.environ.get("CAPTAIN_STORE_ID", "demo_store")

    # 库存同步
    resp = client.post("/api/v1/execute", json={
        "task": "从船长ERP同步最新库存数据",
        "tool": "captain_erp",
        "api_key": api_key,
        "store_id": store_id,
        "operation": "inventory_sync",
        "data_types": ["stock_levels", "inbound_shipments", "reserved_quantity"]
    })
    data = resp.json()
    print(f"  库存同步: {data.get('result', '')[:200]}")

    # 订单同步
    resp = client.post("/api/v1/execute", json={
        "task": "同步船长ERP中的最近7天订单数据",
        "tool": "captain_erp",
        "api_key": api_key,
        "store_id": store_id,
        "operation": "order_sync",
        "days": 7
    })
    data = resp.json()
    print(f"  订单同步: {data.get('result', '')[:200]}")


def demo_google_sheets_integration():
    """集成 Google Sheets 导出运营数据"""
    print("\n📊 Google Sheets 集成示例")

    # 模拟 Google Sheets API 调用
    spreadsheet_id = os.environ.get("GOOGLE_SHEETS_ID", "demo_sheet")

    resp = client.post("/api/v1/execute", json={
        "task": "将今日销量数据导出到Google Sheets",
        "tool": "google_sheets",
        "spreadsheet_id": spreadsheet_id,
        "sheet_name": "销量日报",
        "data_type": "sales_summary",
        "marketplace": "US",
        "date": "today"
    })
    data = resp.json()
    print(f"  Agent: {data.get('agent')}")
    print(f"  结果: {data.get('result', '')[:200]}")


def demo_webhook_notification():
    """配置Webhook告警通知"""
    print("\n🔔 Webhook告警配置示例")

    resp = client.post("/api/v1/execute", json={
        "task": "配置库存预警Webhook，当库存低于21天时发送通知",
        "config": {
            "type": "webhook",
            "url": "https://your-server.com/webhook/amazon-alerts",
            "events": [
                "inventory_low",
                "new_negative_review",
                "hijacker_detected",
                "acos_spike",
                "account_health_alert"
            ],
            "channels": ["dingtalk", "wecom", "email"]
        }
    })
    data = resp.json()
    print(f"  Agent: {data.get('agent')}")
    print(f"  结果: {data.get('result', '')[:200]}")


if __name__ == "__main__":
    print("=" * 60)
    print("亚马逊运营硅基军团 - 外部API集成示例")
    print("=" * 60)
    print("提示：设置环境变量以使用真实API")
    print()

    demo_helium10_integration()
    demo_keepa_integration()
    demo_junglescout_integration()
    demo_captain_erp_integration()
    demo_google_sheets_integration()
    demo_webhook_notification()

    print("\n✅ 示例完成！")
