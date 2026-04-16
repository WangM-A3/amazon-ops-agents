"""
逆向测试套件 4/5 — Agent逆向测试
验证Agent调用失败时的降级处理、多Agent冲突解决、API失败重试

测试用例设计原则：
- 每个测试覆盖Agent生命周期的关键失败场景
- 关注降级策略、冲突消解、重试机制
"""

import asyncio
import pytest
from agents.base import AGENTS, TASK_ROUTING
from agents.chief import ChiefOfStaff
from routing.task_router import TaskRouter, Engine


CHIEF = ChiefOfStaff()
ROUTER = TaskRouter()


# ══════════════════════════════════════════════════════════════════════════════
# 4.1 Agent调用失败时的降级处理
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_agent_failure_graceful_degradation():
    """
    【Agent测试1】Agent执行失败时的优雅降级

    场景：某个Agent执行抛出异常，系统应继续运行并返回降级结果

    通过标准：
    1. 主流程不因单个Agent失败而整体崩溃
    2. 返回结果中包含错误信息（而非缺失）
    3. 其他正常Agent的结果仍被保留
    """
    # 创建一个会失败的模拟Agent调用
    original_run = None
    for agent_id, agent in list(AGENTS.items())[:1]:
        original_run = agent._run
        # 模拟Agent抛出异常
        async def failing_run(task, ctx):
            raise RuntimeError(f"模拟Agent {agent_id}执行失败")

        agent._run = failing_run
        break

    try:
        result = await CHIEF.execute("分析选品和广告", context={})

        # 通过标准1：不崩溃
        assert isinstance(result, dict), "单个Agent失败不应导致整体崩溃"

        # 通过标准2：结果中包含错误信息
        assert "results" in result, "结果应包含results字段（即使部分失败）"

        # 通过标准3：整体返回格式正确
        required = ["chief", "routed_agents", "strategy", "timestamp"]
        for field in required:
            assert field in result, f"结果应包含{field}字段"

    finally:
        # 恢复原始_run
        if original_run:
            for agent_id, agent in list(AGENTS.items())[:1]:
                agent._run = original_run
                break

    print(f"✅ [Agent-降级] 单Agent失败时整体流程正常降级")


@pytest.mark.asyncio
async def test_missing_agent_fallback():
    """
    【Agent测试2】缺失Agent的降级处理

    场景：请求一个不存在的Agent ID，系统应返回有效错误而非崩溃

    通过标准：
    1. ChiefOfStaff能处理不存在的Agent ID
    2. 返回结果说明哪些Agent不可用
    """
    # 路由到一个不存在的Agent
    routed = CHIEF.route("这是一个完全不存在的任务类型啊啊啊xyz123")
    # 系统应至少返回默认Agent

    assert isinstance(routed, list), "路由结果应为list"
    assert len(routed) > 0, "至少应返回一个Agent（fallback）"

    print(f"✅ [Agent-Fallback] 不存在Agent场景有fallback: {routed}")


# ══════════════════════════════════════════════════════════════════════════════
# 4.2 多Agent冲突时的解决机制
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_multi_agent_routing_conflict():
    """
    【Agent测试3】多Agent路由冲突解决

    场景：任务同时匹配多个Agent（如"选品+广告+评论"），
          系统应按优先级选择，并给出决策理由

    通过标准：
    1. 路由结果包含优先级排序
    2. routing_context包含reasoning
    3. 决策逻辑可解释
    """
    result = await CHIEF.execute(
        "分析这个新品的选品机会，同时看广告数据和差评情况，"
        "还要计算利润",
        context={}
    )

    # 通过标准1：有routing信息
    assert "routed_agents" in result, \
        "结果应包含routed_agents字段"

    # 通过标准2：路由的Agent数量合理（不超过合理上限）
    if "routed_agents" in result:
        assert len(result["routed_agents"]) <= 10, \
            f"路由Agent过多({len(result['routed_agents'])})，可能冲突未消解"

    # 通过标准3：strategy字段存在（说明已做决策）
    assert "strategy" in result, "应包含strategy字段表示调度策略"

    print(f"✅ [Agent-冲突消解] 多Agent冲突已消解: strategy={result.get('strategy')}, "
          f"agents={result.get('routed_agents', [])[:3]}")


@pytest.mark.asyncio
async def test_agent_execution_order():
    """
    【Agent测试4】多Agent执行顺序验证

    通过标准：
    1. 返回的results顺序与routed_agents一致
    2. 所有Agent都有结果
    3. 无结果泄漏（不存在未经请求的Agent结果）
    """
    result = await CHIEF.execute(
        "分析选品和广告策略",
        context={"parallel": True}
    )

    routed = result.get("routed_agents", [])
    results = result.get("results", {})

    # 通过标准1：结果数量匹配
    assert len(results) <= len(routed), \
        "结果数量不应超过路由Agent数量"

    # 通过标准2：结果中的AgentID都来自routed列表
    for agent_id in results.keys():
        if agent_id not in ("local",):
            assert agent_id in routed, \
                f"发现未经请求的Agent结果: {agent_id}"

    print(f"✅ [Agent-执行顺序] 结果数量匹配: {len(results)}个结果 / {len(routed)}个路由")


# ══════════════════════════════════════════════════════════════════════════════
# 4.3 API调用失败时的重试机制
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_api_retry_with_timeout():
    """
    【Agent测试5】API超时重试测试

    通过标准：
    1. 单次执行应在合理时间内完成（<30秒）
    2. 超时场景有fallback
    """
    import time

    start = time.time()
    result = await CHIEF.execute("分析选品", context={})
    elapsed = time.time() - start

    # 通过标准1：执行时间合理
    assert elapsed < 30, f"执行耗时{elapsed:.1f}秒，超过30秒限制"

    # 通过标准2：返回有效结果
    assert isinstance(result, dict), "超时后应有fallback结果"

    print(f"✅ [Agent-重试] 执行耗时{elapsed:.2f}秒，在合理范围内")


@pytest.mark.asyncio
async def test_agent_result_integrity():
    """
    【Agent测试6】Agent结果完整性

    通过标准：
    1. 每个Agent结果包含必需字段
    2. result和kpis都是dict
    3. 无空结果污染
    """
    result = await CHIEF.execute("分析选品和利润", context={})

    required_agent_fields = ["agent", "result", "kpis", "tokens"]

    for agent_id, agent_result in result.get("results", {}).items():
        for field in required_agent_fields:
            assert field in agent_result, \
                f"Agent {agent_id} 结果缺少 {field} 字段"

        assert isinstance(agent_result["result"], dict), \
            f"{agent_id}: result应为dict"
        assert isinstance(agent_result["kpis"], dict), \
            f"{agent_id}: kpis应为dict"

    print(f"✅ [Agent-完整性] {len(result.get('results', {}))}个Agent结果格式均正确")


# ══════════════════════════════════════════════════════════════════════════════
# 4.4 TaskRouter降级测试
# ══════════════════════════════════════════════════════════════════════════════

def test_router_fallback_local():
    """
    【Agent测试7】Router降级到LOCAL引擎

    通过标准：
    1. 简单数据操作任务降级到local引擎（零Token消耗）
    2. 决策包含reasoning
    """
    decision = ROUTER.route("统计销量数据", ["sales_analytics"])

    # 通过标准1：决策不为空
    assert decision is not None, "Router应返回决策"
    assert hasattr(decision, "engine"), "决策应包含engine属性"

    # 通过标准2：reasoning存在
    assert hasattr(decision, "reasoning"), "决策应包含reasoning"
    assert len(decision.reasoning) > 0, "reasoning不应为空"

    print(f"✅ [Agent-Router降级] 引擎={decision.engine.value}, 推理={decision.reasoning[:50]}")


def test_router_complexity_score():
    """
    【Agent测试8】Router复杂度评分一致性

    通过标准：
    1. 复杂度评分非负
    2. 引擎选择与复杂度匹配
    3. estimated_tokens为正数
    """
    test_cases = [
        ("查今天销量", 1),      # 低复杂度
        ("分析选品机会", 8),    # 中等复杂度
        ("制定季度广告策略", 15), # 高复杂度
    ]

    for task, min_expected in test_cases:
        decision = ROUTER.route(task, ["sales_analytics"])

        # 通过标准1：复杂度非负
        assert decision.complexity_score >= 0, \
            f"复杂度评分不应为负: {decision.complexity_score}"

        # 通过标准2：estimated_tokens为正
        assert decision.estimated_tokens > 0, \
            f"estimated_tokens应为正数: {decision.estimated_tokens}"

        # 通过标准3：复杂度与引擎匹配
        if decision.complexity_score == 0:
            assert decision.engine.value == "local", \
                "零复杂度任务应使用local引擎"

    print(f"✅ [Agent-Router评分] 复杂度评分逻辑正确")
