"""
示例3：批量任务处理
适用场景：一次提交多个独立任务并行执行，提升效率
"""

import httpx
import asyncio
from typing import List, Dict, Any


BASE_URL = "http://localhost:8080"


async def batch_tasks(tasks: List[Dict[str, Any]]) -> List[Dict]:
    """批量提交任务（异步）"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        resp = await client.post("/api/v1/batch", json={"tasks": tasks})
        data = resp.json()
        return data.get("results", [])


async def demo_basic_batch():
    """基础批量任务"""
    tasks = [
        {"task": "分析无线蓝牙耳机市场趋势", "marketplace": "US"},
        {"task": "优化 SKU-001 的五点描述", "sku": "SKU-001"},
        {"task": "检查账号健康状态", "marketplace": "US"},
        {"task": "计算 SKU-002 的利润", "sku": "SKU-002"},
        {"task": "分析竞品 ASIN B0XXXXXX 的流量词", "asin": "B0XXXXXX"},
    ]

    print("📋 批量任务执行中...")
    results = await batch_tasks(tasks)

    print(f"\n✅ 完成 {len(results)} 个任务:\n")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] {r.get('agent', 'N/A')}: {r.get('result', '')[:100]}...")


async def demo_morning_routine():
    """早晨例行检查 - 批量获取多个指标"""
    tasks = [
        # 销量概览
        {"task": "今日美国站销量和GMV"},
        # 库存预警
        {"task": "哪些SKU库存低于30天，需要补货"},
        # 差评检查
        {"task": "过去24小时有没有新的差评"},
        # 广告健康
        {"task": "广告ACOS有没有异常飙升"},
        # 跟卖检测
        {"task": "核心ASIN有没有被跟卖"},
    ]

    print("🌅 执行早晨例行检查...\n")
    results = await batch_tasks(tasks)

    labels = ["📊 销量概览", "📦 库存预警", "⭐ 差评检查", "📢 广告健康", "🔒 跟卖检测"]
    for label, r in zip(labels, results):
        status = "✅" if r.get("success") else "❌"
        print(f"{status} {label}: {r.get('result', '')[:120]}...")


async def demo_competitor_analysis():
    """竞品分析 - 批量收集多个竞品数据"""
    asins = ["B0XXXXX1", "B0XXXXX2", "B0XXXXX3"]

    tasks = [
        {"task": f"分析 ASIN {asin} 的市场定位和优劣势", "asin": asin}
        for asin in asins
    ]

    print(f"🔍 批量竞品分析: {len(tasks)} 个ASIN...\n")
    results = await batch_tasks(tasks)

    for asin, r in zip(asins, results):
        print(f"  📌 ASIN {asin}:")
        print(f"     {r.get('result', '')[:150]}...\n")


async def demo_listing_optimization_batch():
    """批量Listing优化 - 一次优化多个SKU"""
    skus = ["SKU-001", "SKU-002", "SKU-003", "SKU-004"]

    tasks = [
        {
            "task": f"优化 {sku} 的标题和五点描述",
            "sku": sku,
            "optimization_focus": "seo_keywords"
        }
        for sku in skus
    ]

    print(f"📝 批量优化 {len(tasks)} 个Listing...\n")
    results = await batch_tasks(tasks)

    for sku, r in zip(skus, results):
        agent = r.get("agent", "N/A")
        status = "✅" if r.get("success") else "❌"
        print(f"{status} {sku} [{agent}]: {r.get('result', '')[:80]}...")


if __name__ == "__main__":
    print("=" * 60)
    print("亚马逊运营硅基军团 - 批量任务示例")
    print("=" * 60)

    print("\n[示例1] 基础批量任务")
    asyncio.run(demo_basic_batch())

    print("\n[示例2] 早晨例行检查")
    asyncio.run(demo_morning_routine())

    print("\n[示例3] 竞品批量分析")
    asyncio.run(demo_competitor_analysis())

    print("\n[示例4] 批量Listing优化")
    asyncio.run(demo_listing_optimization_batch())

    print("\n✅ 示例完成！")
