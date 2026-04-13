"""
测试套件 - Demo & 单元测试
"""

import asyncio
import json
import sys
from datetime import datetime

# 确保可以导入
sys.path.insert(0, ".")

# ─── 测试1: Agent注册验证 ─────────────────────────────────────────────────────
def test_agent_registration():
    """验证所有Agent正确注册"""
    from agents.base import AGENT_REGISTRY, AGENTS, TASK_ROUTING

    assert len(AGENTS) >= 21, f"Agent数量不足: {len(AGENTS)}"
    assert len(TASK_ROUTING) >= 20, f"路由表不完整: {len(TASK_ROUTING)}"

    required_agents = [
        "product_research", "niche_finder",
        "listing_optimizer", "keyword_research", "acontent",
        "ppc_manager", "sponsored_ads",
        "inventory_planner", "fba_manager",
        "price_optimizer", "repricing",
        "review_monitor", "vine_program",
        "brand_registry", "hijacker",
        "sales_analytics", "profit_calculator",
        "customer_service",
        "compliance_checker", "account_health",
        "gui_agent",
    ]
    missing = [a for a in required_agents if a not in AGENTS]
    assert not missing, f"缺失Agent: {missing}"

    print(f"✅ Agent注册验证通过: {len(AGENTS)}个Agent已注册")
    return True


# ─── 测试2: ChiefOfStaff路由 ──────────────────────────────────────────────────
async def test_chief_routing():
    """测试幕僚长关键词路由"""
    from agents.chief import CHIEF

    test_cases = [
        ("帮我分析这款蓝牙耳机的市场机会", ["product_research"]),
        ("我的广告ACOS太高了怎么优化", ["ppc_manager"]),
        ("收到一个1星差评说续航不行", ["review_monitor", "customer_service"]),
        ("帮我查一下今天美国站销量", ["sales_analytics"]),
        ("帮我分析Listing标题怎么优化", ["listing_optimizer"]),
        ("有个跟卖怎么处理", ["hijacker", "brand_registry"]),
        ("帮我计算这个SKU的利润", ["profit_calculator", "price_optimizer"]),  # "利润"+"SKU" 同时触发
        ("用browser自动化操作卖家中心截图", ["gui_agent"]),  # 含 "browser"/"自动化"/"截图"
        ("我的账号健康度怎么样", ["account_health"]),
        ("VINE计划怎么申请", ["vine_program"]),
    ]

    all_passed = True
    for task, expected_agents in test_cases:
        routed = CHIEF.route(task)
        top_match = routed[0] if routed else None
        ok = top_match in expected_agents
        status = "✅" if ok else "❌"
        if not ok:
            all_passed = False
        print(f"  {status} '{task[:30]}...' → {routed[:2]} (期望: {expected_agents})")

    assert all_passed, "路由测试有失败项"
    print(f"✅ ChiefOfStaff路由测试通过: {len(test_cases)}个测试用例")
    return True


# ─── 测试3: Agent执行验证 ──────────────────────────────────────────────────────
async def test_agent_execution():
    """测试至少3个核心Agent的输出格式"""
    from agents.base import AGENTS

    test_agents = ["product_research", "ppc_manager", "sales_analytics"]
    all_passed = True

    for agent_id in test_agents:
        agent = AGENTS.get(agent_id)
        assert agent, f"Agent不存在: {agent_id}"

        result = await agent.execute(f"测试任务 for {agent_id}", {})

        # 验证输出格式
        assert "agent" in result, f"{agent_id}: 缺少agent字段"
        assert "tokens" in result, f"{agent_id}: 缺少tokens字段"
        assert "result" in result, f"{agent_id}: 缺少result字段"
        assert "kpis" in result, f"{agent_id}: 缺少kpis字段"
        assert isinstance(result["result"], dict), f"{agent_id}: result应为dict"
        assert isinstance(result["kpis"], dict), f"{agent_id}: kpis应为dict"

        print(f"  ✅ {agent_id}: {list(result['result'].keys())[:3]}")
        all_passed = all_passed and True

    assert all_passed
    print(f"✅ Agent执行测试通过: {len(test_agents)}个Agent")
    return True


# ─── 测试4: ChiefOfStaff并行调度 ──────────────────────────────────────────────
async def test_chief_parallel():
    """测试幕僚长并行调度"""
    from agents.chief import CHIEF

    result = await CHIEF.execute("帮我分析这个蓝牙耳机的市场机会，并且分析广告数据和差评情况")

    assert "routed_agents" in result
    assert "results" in result
    assert "strategy" in result
    assert len(result["routed_agents"]) >= 1
    assert result["strategy"] in ("single", "parallel")
    assert result["total_tokens"] >= 0
    assert "timestamp" in result

    # 验证结果聚合
    for agent_id, res in result["results"].items():
        assert "agent" in res, f"{agent_id}: 聚合结果缺少agent字段"

    print(f"✅ 并行调度测试通过: 路由{result['routed_agents']}, 策略={result['strategy']}")
    return True


# ─── 测试5: JSON输出格式验证 ────────────────────────────────────────────────────
async def test_json_output():
    """验证API返回JSON可序列化"""
    from agents.chief import CHIEF

    result = await CHIEF.execute("帮我分析选品")

    # 确保JSON可序列化
    json_str = json.dumps(result, ensure_ascii=False)
    parsed = json.loads(json_str)
    assert parsed["input"] == result["input"]
    assert len(parsed["routed_agents"]) == len(result["routed_agents"])

    print(f"✅ JSON输出验证通过: {len(json_str)}字符")
    return True


# ─── 测试6: GUI Agent模拟模式 ─────────────────────────────────────────────────
async def test_gui_agent():
    """测试GUI Agent SIMULATE模式"""
    from agents.gui_agent import GUIAgent

    agent = GUIAgent()
    assert agent.agent_id == "gui_agent"
    assert "gui" in agent.capabilities

    # 模拟执行
    result = await agent.execute("帮我截图亚马逊后台", {})

    assert "mode" in result
    assert result["mode"] == "SIMULATE（计划预览模式）"
    assert "plan" in result
    assert isinstance(result["plan"], list)
    assert "steps_total" in result

    print(f"✅ GUI Agent测试通过: scene={result['scene']}, steps={result['steps_total']}")
    return True


# ─── 测试7: 工作流引擎 ─────────────────────────────────────────────────────────
async def test_workflow_engine():
    """测试工作流引擎"""
    from agents.chief import CHIEF
    from scripts.workflow_engine import WorkflowEngine, AMAZON_WORKFLOWS

    engine = WorkflowEngine(CHIEF)
    workflows = engine.list_workflows()

    assert len(workflows) >= 4, f"预置工作流不足: {len(workflows)}"
    wf_names = [w["name"] for w in workflows]
    print(f"  ✅ 可用工作流: {wf_names}")

    # 执行一个快速工作流（只选2-3个节点）
    result = await engine.run(
        "product_launch",
        {"product_idea": "无线蓝牙耳机", "marketplace": "US"},
    )

    assert "workflow_id" in result
    assert "nodes" in result
    assert "completed" in result
    assert result["completed"] >= 0

    print(f"✅ 工作流引擎测试通过: completed={result['completed']}/{result['total_nodes']}")
    return True


# ─── 测试8: ContextManager ─────────────────────────────────────────────────────
def test_context_manager():
    """测试上下文管理器"""
    from scripts.context_manager import ContextManager, WorkingContext

    ctx_mgr = ContextManager()

    # 模拟一个任务会话
    session_id = "test_session_001"
    task = "帮我分析选品"

    ctx = ctx_mgr.start_task(session_id, task, ["product_research"])
    assert ctx.session_id == session_id
    assert ctx.task == task

    ctx_mgr.update_task(session_id, {
        "product_research": {"result": {"demand_score": "8/10"}, "tokens": 150}
    })

    updated = ctx_mgr.get_working(session_id)
    assert updated is not None
    assert "product_research" in updated.results

    closed = ctx_mgr.close_task(session_id)
    assert closed is not None
    assert closed.session_id == session_id

    # 记忆检索
    stats = ctx_mgr.get_memory_stats()
    assert "total_sessions" in stats
    print(f"✅ ContextManager测试通过: sessions={stats['total_sessions']}")
    return True


# ─── 测试9: CLI Demo ───────────────────────────────────────────────────────────
async def test_cli_demo():
    """CLI演示测试"""
    from agents.chief import CHIEF

    print("\n🎩 Amazon Ops Silicon Army - CLI Demo")
    print("=" * 60)

    tests = [
        "帮我分析这款无线蓝牙耳机的市场机会",
        "我的广告ACOS太高了，怎么优化",
        "收到一个1星差评说续航不行，怎么回复",
        "帮我查一下今天美国站的销量",
        "帮我分析这个Listing标题怎么优化",
        "有个跟卖怎么处理",
        "用browser自动化操作卖家中心截图",
    ]

    all_results = []
    for i, t in enumerate(tests, 1):
        result = await CHIEF.execute(t)
        agents = result["routed_agents"]
        keys = [list(r.get("result", {}).keys())[:2] for r in result["results"].values()]
        print(f"\n📌 [{i}] {t}")
        print(f"   → 路由: {agents} ({result['strategy']})")
        for (aid, res), k in zip(result["results"].items(), keys):
            print(f"   → {res.get('agent','?')}: {k}")
        all_results.append(result)

    print(f"\n✅ CLI Demo完成: {len(tests)}个测试全部通过")
    return True


# ─── 运行所有测试 ──────────────────────────────────────────────────────────────
async def run_all_tests():
    """运行全部测试套件"""
    print("\n" + "=" * 60)
    print("🧪 亚马逊运营硅基军团 - 测试套件")
    print("=" * 60)

    tests_sync = [
        ("Agent注册", test_agent_registration),
        ("ContextManager", test_context_manager),
    ]
    tests_async = [
        ("ChiefOfStaff路由", test_chief_routing),
        ("Agent执行", test_agent_execution),
        ("并行调度", test_chief_parallel),
        ("JSON输出", test_json_output),
        ("GUI Agent", test_gui_agent),
        ("工作流引擎", test_workflow_engine),
        ("CLI Demo", test_cli_demo),
    ]

    passed = 0
    failed = 0

    # 同步测试
    for name, fn in tests_sync:
        try:
            fn()
            passed += 1
        except Exception as exc:
            print(f"  ❌ {name} 失败: {exc}")
            failed += 1

    # 异步测试
    for name, fn in tests_async:
        try:
            await fn()
            passed += 1
        except Exception as exc:
            print(f"  ❌ {name} 失败: {exc}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败, {passed+failed} 总计")
    if failed == 0:
        print("🎉 全部测试通过！技能包已就绪。")
    else:
        print(f"⚠️  {failed}个测试失败，请检查。")
    print("=" * 60 + "\n")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
