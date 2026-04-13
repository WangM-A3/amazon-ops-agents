"""
示例2：单Agent直接调用
适用场景：明确知道需要哪个Agent时直接调用
"""

import httpx

BASE_URL = "http://localhost:8080"
client = httpx.Client(base_url=BASE_URL, timeout=60.0)


def demo_listing_optimizer():
    """Listing优化Agent"""
    resp = client.post("/api/v1/execute", json={
        "task": "优化这个蓝牙耳机的Listing标题，要求包含核心关键词",
        "agent": "listing_optimizer",
        "asin": "B0XXXXXX",
        "keywords": ["bluetooth earbuds", "wireless earphones", "noise cancelling"]
    })
    data = resp.json()
    print("📝 Listing优化结果:")
    print(f"   Agent: {data.get('agent', 'N/A')}")
    print(f"   结果: {data.get('result', '')[:300]}")


def demo_ppc_manager():
    """广告优化Agent"""
    resp = client.post("/api/v1/execute", json={
        "task": "我的广告ACOS 45%太高了，怎么优化到25%以内",
        "agent": "ppc_manager",
        "sku": "ABC123",
        "current_acos": 0.45,
        "target_acos": 0.25
    })
    data = resp.json()
    print("\n📢 广告优化结果:")
    print(f"   Agent: {data.get('agent', 'N/A')}")
    print(f"   结果: {data.get('result', '')[:300]}")


def demo_review_monitor():
    """差评处理Agent"""
    resp = client.post("/api/v1/execute", json={
        "task": "收到一个1星差评，说耳机续航不行，帮我写回复",
        "agent": "review_monitor",
        "asin": "B0XXXXXX",
        "review_text": "Battery life is terrible, only lasted 2 hours...",
        "review_rating": 1
    })
    data = resp.json()
    print("\n⭐ 差评回复结果:")
    print(f"   Agent: {data.get('agent', 'N/A')}")
    print(f"   结果: {data.get('result', '')[:300]}")


def demo_profit_calculator():
    """利润计算Agent"""
    resp = client.post("/api/v1/execute", json={
        "task": "计算这个产品的FBA利润",
        "agent": "profit_calculator",
        "sku": "ABC123",
        "product_cost": 15.0,
        "selling_price": 49.99,
        "shipping_cost": 2.5,
        "marketplace": "US"
    })
    data = resp.json()
    print("\n💰 利润分析结果:")
    print(f"   Agent: {data.get('agent', 'N/A')}")
    print(f"   结果: {data.get('result', '')[:300]}")


def demo_hijacker_detector():
    """跟卖检测Agent"""
    resp = client.post("/api/v1/execute", json={
        "task": "检测ASIN B0XXXXXX是否有跟卖",
        "agent": "hijacker_detector",
        "asin": "B0XXXXXX"
    })
    data = resp.json()
    print("\n🔒 跟卖检测结果:")
    print(f"   Agent: {data.get('agent', 'N/A')}")
    print(f"   结果: {data.get('result', '')[:300]}")


def demo_compliance_checker():
    """合规检查Agent"""
    resp = client.post("/api/v1/execute", json={
        "task": "检查我的主图是否合规",
        "agent": "compliance_checker",
        "sku": "ABC123",
        "check_types": ["main_image", "title", "bullets"]
    })
    data = resp.json()
    print("\n⚖️ 合规检查结果:")
    print(f"   Agent: {data.get('agent', 'N/A')}")
    print(f"   结果: {data.get('result', '')[:300]}")


if __name__ == "__main__":
    print("=" * 60)
    print("亚马逊运营硅基军团 - 单Agent调用示例")
    print("=" * 60)

    demo_listing_optimizer()
    demo_ppc_manager()
    demo_review_monitor()
    demo_profit_calculator()
    demo_hijacker_detector()
    demo_compliance_checker()

    print("\n✅ 示例完成！")
