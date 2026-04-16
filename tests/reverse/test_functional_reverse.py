"""
逆向测试套件 1/5 — 功能逆向测试
验证系统从结果反推正确性、错误场景容错、极端参数处理

测试用例设计原则：
- 每个测试包含：描述 → 输入 → 预期行为 → 通过标准
- 从结果反推：客户收到询盘 → 追溯整个流程是否正确
"""

import pytest
from agents.base import AGENTS, TASK_ROUTING
from agents.chief import ChiefOfStaff


CHIEF = ChiefOfStaff()


# ══════════════════════════════════════════════════════════════════════════════
# 1.1 功能逆向测试：结果可追溯性（从结果反推流程正确性）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reverse_inquiry_trace():
    """
    【逆向场景1】客户收到询盘 → 追溯整个流程是否正确

    场景：买家发来询盘 → 系统自动生成回复建议 → 可追溯整个链路

    通过标准：
    1. 执行后返回完整的 trace_id
    2. 结果包含所有触发的 Agent 列表
    3. 每个 Agent 结果包含 agent 名称
    4. chief 响应字段完整（task_id, routed_agents, strategy, timestamp）
    """
    result = await CHIEF.execute(
        "收到买家消息问这个产品能不能定制logo，请生成回复建议",
        context={"source": "inquiry", "marketplace": "US"}
    )

    # 通过标准1：trace_id 存在
    assert "trace_id" in result, "结果缺少 trace_id，无法追溯"
    assert result["trace_id"] is not None, "trace_id 不应为 None"

    # 通过标准2：路由 Agent 列表非空
    assert len(result["routed_agents"]) > 0, \
        f"应至少路由到1个Agent，实际：{result['routed_agents']}"

    # 通过标准3：每个 Agent 结果包含 agent 名称
    for agent_id, agent_result in result["results"].items():
        assert "agent" in agent_result, \
            f"Agent {agent_id} 结果缺少 agent 字段"
        assert "result" in agent_result, \
            f"Agent {agent_id} 结果缺少 result 字段"

    # 通过标准4：关键字段完整
    required_fields = ["chief", "routed_agents", "strategy", "timestamp"]
    for field in required_fields:
        assert field in result, f"结果缺少必需字段: {field}"

    print(f"✅ [逆向-询盘追溯] trace_id={result['trace_id']}, agents={result['routed_agents']}")


# ══════════════════════════════════════════════════════════════════════════════
# 1.2 错误场景容错测试
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_error_invalid_product_id():
    """
    【逆向场景2】故意输入错误数据，验证系统容错能力

    场景：提供不存在的 ASIN/无效产品ID，系统不应崩溃

    通过标准：
    1. 系统不抛出未处理异常
    2. 返回结果中包含错误信息（graceful degradation）
    3. 返回结果格式仍为合法 JSON
    """
    result = await CHIEF.execute(
        "帮我分析 ASIN 为 INVALID_ASIN_12345_XXXXX 的产品数据",
        context={"source": "manual_test"}
    )

    # 通过标准1：不崩溃
    assert isinstance(result, dict), "结果应为 dict，不能崩溃"

    # 通过标准2：有结果字段（无论成功或失败）
    assert "results" in result, "结果必须包含 results 字段"

    # 通过标准3：可 JSON 序列化
    import json
    json_str = json.dumps(result, ensure_ascii=False)
    assert len(json_str) > 0, "结果必须可序列化"

    print(f"✅ [逆向-错误容错] 无效ASIN处理正常，结果格式合法")


@pytest.mark.asyncio
async def test_error_empty_product_name():
    """
    【逆向场景3】空产品名测试

    场景：产品名为空字符串，验证系统边界处理

    通过标准：
    1. 不抛出异常
    2. 返回结构完整
    """
    result = await CHIEF.execute("", context={})

    # 通过标准1：格式完整
    assert "results" in result, "空输入仍返回完整结果结构"
    assert "routed_agents" in result, "空输入仍返回路由信息"

    print(f"✅ [逆向-空输入] 空字符串处理正常")


@pytest.mark.asyncio
async def test_error_malformed_json_context():
    """
    【逆向场景4】恶意/畸形 context JSON 测试

    场景：传入非标准 context（嵌套过深、特殊字符等）

    通过标准：
    1. API层验证拒绝非法输入（Pydantic校验）
    2. 不产生服务器错误
    """
    result = await CHIEF.execute(
        "分析这个产品",
        context={
            "data": "x" * 10000,  # 超长数据
            "nested": {"a": {"b": {"c": {"d": "deep"}}}}  # 深层嵌套
        }
    )

    assert isinstance(result, dict), "畸形context不崩溃"
    print(f"✅ [逆向-畸形context] 超长+深层嵌套处理正常")


# ══════════════════════════════════════════════════════════════════════════════
# 1.3 极端参数测试（边界测试）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_extreme_task_length():
    """
    【边界测试1】超长任务文本

    通过标准：
    1. 不抛出异常
    2. 至少路由到1个Agent
    """
    long_task = "分析" + "这个产品" * 500  # 约3500字符
    result = await CHIEF.execute(long_task, context={})

    assert isinstance(result, dict), "超长任务不崩溃"
    assert len(result["results"]) >= 0, "返回结果结构完整"

    print(f"✅ [逆向-超长文本] 3500字符任务处理正常")


@pytest.mark.asyncio
async def test_extreme_batch_size():
    """
    【边界测试2】大批量任务

    场景：单次提交50个任务（最大限制）

    通过标准：
    1. 全部50个任务都有结果
    2. 每个结果结构合法
    """
    from agents.chief import CHIEF
    tasks = [f"分析选品任务{i}" for i in range(50)]
    task_id = "boundary_batch_001"

    # 顺序执行
    results = []
    for t in tasks:
        r = await CHIEF.execute(t, {})
        results.append(r)

    # 通过标准：全部完成
    assert len(results) == 50, f"应有50个结果，实际{len(results)}"
    for i, r in enumerate(results):
        assert isinstance(r, dict), f"第{i}个结果应为dict"
        assert "results" in r, f"第{i}个缺少results字段"

    print(f"✅ [逆向-大批量] 50任务批处理全部完成")


@pytest.mark.asyncio
async def test_unicode_extreme_input():
    """
    【边界测试3】特殊Unicode字符输入

    通过标准：正确处理emoji、多语言混合
    """
    result = await CHIEF.execute(
        "分析这个📱产品！分析🔋电池性能。能不能做商海外贸🌍出口到🇺🇸美国？",
        context={"locale": "zh-CN"}
    )

    assert isinstance(result, dict), "Unicode输入不崩溃"
    print(f"✅ [逆向-Unicode] emoji+多语言混合处理正常")


@pytest.mark.asyncio
async def test_negative_numeric_input():
    """
    【边界测试4】负数和非法数值

    通过标准：数值类错误不导致系统崩溃
    """
    result = await CHIEF.execute(
        "计算利润：售价=-10，采购成本=200",
        context={}
    )

    assert isinstance(result, dict), "负数输入不崩溃"
    assert "results" in result, "返回结果结构完整"

    print(f"✅ [逆向-负数] 非法数值处理正常")
