"""
示例5：多Agent协同链式调用
适用场景：复杂任务需要多个Agent顺序协作，上一步输出作为下一步输入
"""

import httpx


BASE_URL = "http://localhost:8080"
client = httpx.Client(base_url=BASE_URL, timeout=60.0)


def run_agent(task: str, **kwargs) -> dict:
    """执行单个Agent任务"""
    payload = {"task": task}
    payload.update(kwargs)
    resp = client.post("/api/v1/execute", json=payload)
    return resp.json()


def demo_new_product_chain():
    """
    从选品到Listing上线的完整流程：
    Step 1: 市场调研 → Step 2: 关键词研究 → Step 3: Listing创建 → Step 4: A+内容
    """
    print("=" * 60)
    print("🆕 新品上市完整链路（4步协同）")
    print("=" * 60)

    # Step 1: 市场调研 - 找到有潜力的品类
    print("\n[Step 1/4] 🔍 市场调研...")
    r1 = run_agent(
        "分析宠物喂食器市场，找到3个有潜力的细分品类",
        marketplace="US",
        tool="junglescout"
    )
    print(f"  Agent: {r1.get('agent')}")
    print(f"  结果: {r1.get('result', '')[:200]}")
    niches = r1.get("result", "")

    # Step 2: 关键词研究 - 基于选品结果挖掘关键词
    print("\n[Step 2/4] 🔑 关键词研究...")
    r2 = run_agent(
        "针对【自动宠物喂食器带摄像头】细分品类，挖掘50个长尾关键词",
        niche="automatic pet feeder with camera",
        marketplace="US",
        keyword_limit=50
    )
    print(f"  Agent: {r2.get('agent')}")
    print(f"  结果: {r2.get('result', '')[:200]}")
    keywords = r2.get("result", "")

    # Step 3: Listing创建 - 整合选品和关键词
    print("\n[Step 3/4] 📝 Listing创建...")
    r3 = run_agent(
        "创建宠物喂食器(自动款带摄像头)的完整Listing",
        keywords=keywords,
        marketplace="US",
        product_category="Pet Supplies > Pet Food & Treat Dispensers"
    )
    print(f"  Agent: {r3.get('agent')}")
    print(f"  结果: {r3.get('result', '')[:200]}")
    listing = r3.get("result", "")
    asin = r3.get("asin", "B0XXXXXX")  # 假设返回了ASIN

    # Step 4: A+内容生成
    print("\n[Step 4/4] 🎨 A+内容生成...")
    r4 = run_agent(
        "为宠物喂食器生成A+页面内容，包含品牌故事和产品优势图",
        asin=asin,
        brand_story="让每一个宠物主人随时随地关爱宠物",
        include_comparison_chart=True
    )
    print(f"  Agent: {r4.get('agent')}")
    print(f"  结果: {r4.get('result', '')[:200]}")

    print("\n✅ 完整链路执行完成！")


def demo_review_recovery_chain():
    """
    差评恢复完整链路：
    差评发现 → 原因分析 → 应对方案 → 差评回复 → 预防措施
    """
    print("\n" + "=" * 60)
    print("⭐ 差评恢复完整链路（5步协同）")
    print("=" * 60)

    asin = "B0XXXXXX"

    # Step 1: 差评发现
    print("\n[Step 1/5] 📊 差评发现...")
    r1 = run_agent(f"查看ASIN {asin} 最近30天的差评", asin=asin)
    print(f"  Agent: {r1.get('agent')}")
    print(f"  结果: {r1.get('result', '')[:200]}")

    # Step 2: 原因分析
    print("\n[Step 2/5] 🔬 差评原因分析...")
    r2 = run_agent(
        f"分析ASIN {asin} 差评的根本原因，是质量问题、物流问题还是产品描述不符",
        asin=asin
    )
    print(f"  Agent: {r2.get('agent')}")
    print(f"  结果: {r2.get('result', '')[:200]}")

    # Step 3: 应对方案
    print("\n[Step 3/5] 💡 制定应对方案...")
    r3 = run_agent(
        f"针对ASIN {asin} 的差评问题，制定改善计划",
        root_cause=r2.get("result", ""),
        asin=asin
    )
    print(f"  Agent: {r3.get('agent')}")
    print(f"  结果: {r3.get('result', '')[:200]}")

    # Step 4: 差评回复
    print("\n[Step 4/5] 💬 差评回复...")
    r4 = run_agent(
        "帮我写一个专业的差评回复，内容是：'Battery lasted only 2 hours, very disappointed'",
        asin=asin,
        review_text="Battery lasted only 2 hours, very disappointed",
        response_tone="apologetic_solution"
    )
    print(f"  Agent: {r4.get('agent')}")
    print(f"  结果: {r4.get('result', '')[:200]}")

    # Step 5: 预防措施
    print("\n[Step 5/5] 🛡️ 预防措施...")
    r5 = run_agent(
        f"制定预防ASIN {asin} 再次出现差评的措施",
        improvement_plan=r3.get("result", "")
    )
    print(f"  Agent: {r5.get('agent')}")
    print(f"  结果: {r5.get('result', '')[:200]}")

    print("\n✅ 差评恢复链路执行完成！")


def demo_profit_optimization_chain():
    """
    利润优化完整链路：
    利润诊断 → 成本分析 → 定价策略 → 竞品对标 → 优化建议
    """
    print("\n" + "=" * 60)
    print("💰 利润优化完整链路（5步协同）")
    print("=" * 60)

    sku = "ABC123"

    # Step 1: 利润诊断
    print("\n[Step 1/5] 📊 利润诊断...")
    r1 = run_agent(f"诊断SKU {sku} 的利润状况", sku=sku)
    print(f"  Agent: {r1.get('agent')}")
    print(f"  结果: {r1.get('result', '')[:200]}")

    # Step 2: 成本分析
    print("\n[Step 2/5] 💡 成本分析...")
    r2 = run_agent(
        f"详细分析SKU {sku} 的各项成本：产品成本/物流/FBA/广告/退货",
        sku=sku
    )
    print(f"  Agent: {r2.get('agent')}")
    print(f"  结果: {r2.get('result', '')[:200]}")

    # Step 3: 定价策略
    print("\n[Step 3/5] 🎯 定价策略制定...")
    r3 = run_agent(
        f"为SKU {sku} 制定最优定价策略",
        sku=sku,
        current_price=49.99,
        target_margin=0.30
    )
    print(f"  Agent: {r3.get('agent')}")
    print(f"  结果: {r3.get('result', '')[:200]}")

    # Step 4: 竞品对标
    print("\n[Step 4/5] 📈 竞品价格对标...")
    r4 = run_agent(
        f"分析SKU {sku} 竞品的价格区间",
        sku=sku
    )
    print(f"  Agent: {r4.get('agent')}")
    print(f"  结果: {r4.get('result', '')[:200]}")

    # Step 5: 综合优化建议
    print("\n[Step 5/5] ✅ 综合优化建议...")
    r5 = run_agent(
        f"综合成本分析、定价策略和竞品对标，给出SKU {sku} 的综合优化建议",
        cost_analysis=r2.get("result", ""),
        pricing_strategy=r3.get("result", ""),
        competitor_data=r4.get("result", "")
    )
    print(f"  Agent: {r5.get('agent')}")
    print(f"  结果: {r5.get('result', '')[:200]}")

    print("\n✅ 利润优化链路执行完成！")


if __name__ == "__main__":
    demo_new_product_chain()
    demo_review_recovery_chain()
    demo_profit_optimization_chain()
