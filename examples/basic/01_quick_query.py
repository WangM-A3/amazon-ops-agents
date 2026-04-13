"""
示例1：快速查询（Quick Query）
适用场景：用自然语言快速查询运营数据，无需指定Agent
"""

import httpx

BASE_URL = "http://localhost:8080"
client = httpx.Client(base_url=BASE_URL, timeout=30.0)


def demo_health_check():
    """健康检查"""
    resp = client.get("/health")
    data = resp.json()
    print(f"✅ 服务状态: {data['status']}")
    print(f"   Agent数量: {data['agents']}")
    print(f"   版本: {data['version']}")


def demo_sales_query():
    """查询今日销量"""
    resp = client.post("/api/v1/execute", json={
        "task": "帮我查一下今天美国站的销量情况",
        "marketplace": "US"
    })
    data = resp.json()
    print(f"📊 销量查询 [{data.get('agent', 'N/A')}]:")
    print(f"   结果: {data.get('result', '')[:200]}")
    print(f"   引擎: {data.get('engine', 'N/A')}")


def demo_keyword_query():
    """查询竞品关键词"""
    resp = client.post("/api/v1/execute", json={
        "task": "竞品 ASIN B0XXXXXX 的主要关键词有哪些",
        "asin": "B0XXXXXX"
    })
    data = resp.json()
    print(f"🔍 关键词查询 [{data.get('agent', 'N/A')}]:")
    print(f"   结果: {data.get('result', '')[:200]}")


def demo_inventory_query():
    """查询库存状态"""
    resp = client.post("/api/v1/execute", json={
        "task": "SKU ABC123 库存还能维持几天",
        "sku": "ABC123"
    })
    data = resp.json()
    print(f"📦 库存查询 [{data.get('agent', 'N/A')}]:")
    print(f"   结果: {data.get('result', '')[:200]}")


def demo_natural_query():
    """自然语言综合查询"""
    queries = [
        "我的广告ACOS最近有点高，怎么回事",
        "帮我分析一下这个产品能不能做：无线蓝牙耳机",
        "收到一个差评说质量问题，怎么回复比较好",
    ]
    for q in queries:
        resp = client.post("/api/v1/execute", json={"task": q})
        data = resp.json()
        print(f"\n💬 查询: {q}")
        print(f"   Agent: {data.get('agent', 'N/A')}")
        print(f"   结果: {data.get('result', '')[:150]}...")


if __name__ == "__main__":
    print("=" * 60)
    print("亚马逊运营硅基军团 - 快速查询示例")
    print("=" * 60)

    demo_health_check()
    print()
    demo_sales_query()
    print()
    demo_keyword_query()
    print()
    demo_inventory_query()
    print()
    demo_natural_query()

    print("\n✅ 示例完成！")
