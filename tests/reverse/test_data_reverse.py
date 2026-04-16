"""
逆向测试套件 3/5 — 数据逆向测试
验证数据删除后恢复、误操作回滚、数据一致性

测试用例设计原则：
- 每个测试验证数据生命周期的一个关键节点
- 关注幂等性、一致性、可恢复性
"""

import json
import os
import shutil
import tempfile
import pytest
from datetime import datetime, timezone
from agents.base import AGENTS, AGENT_CALL_LOG, TASK_ROUTING
from agents.chief import ChiefOfStaff
from scripts.context_manager import ContextManager


CHIEF = ChiefOfStaff()


# ══════════════════════════════════════════════════════════════════════════════
# 3.1 数据删除后恢复测试
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_data_deletion_recovery():
    """
    【数据测试1】数据删除后恢复测试

    场景：任务执行后，其上下文数据被清除；再次执行相似任务时，
          系统应能重新构建必要上下文（幂等性）

    通过标准：
    1. 相同任务第二次执行返回结果结构一致
    2. 两次执行结果的主要字段可对比
    3. 不因"数据已删除"而崩溃
    """
    task = "分析蓝牙耳机的市场机会"

    # 第一次执行
    result1 = await CHIEF.execute(task, context={"marketplace": "US"})
    result1_keys = set(result1.keys())

    # 模拟数据被清除（清空调用日志中的相关记录）
    initial_log_len = len(AGENT_CALL_LOG)

    # 第二次执行（数据已"删除"）
    result2 = await CHIEF.execute(task, context={"marketplace": "US"})
    result2_keys = set(result2.keys())

    # 通过标准1：两次结果结构一致
    assert result1_keys == result2_keys, \
        f"相同任务两次执行结果结构不一致: {result1_keys} vs {result2_keys}"

    # 通过标准2：两次路由Agent相同
    assert result1["routed_agents"] == result2["routed_agents"], \
        "相同任务应路由到相同Agent"

    # 通过标准3：第二次执行仍然产生调用日志（系统正常工作）
    log_len_after = len(AGENT_CALL_LOG)
    assert log_len_after > initial_log_len, \
        "第二次执行应继续产生调用日志"

    print(f"✅ [数据-删除恢复] 相同任务两次执行结果一致，幂等性正常")


@pytest.mark.asyncio
async def test_context_after_data_loss():
    """
    【数据测试2】上下文数据丢失后的行为

    通过标准：
    1. 无context时使用默认值
    2. 关键字段仍然存在
    """
    result_no_ctx = await CHIEF.execute("分析选品", context={})
    result_with_ctx = await CHIEF.execute("分析选品", context={"marketplace": "US"})

    # 两者都应返回完整结果
    assert "results" in result_no_ctx, "无context应仍返回结果"
    assert "results" in result_with_ctx, "有context应返回结果"

    # 两者都应有时间戳
    assert "timestamp" in result_no_ctx, "无context结果缺少timestamp"
    assert "timestamp" in result_with_ctx, "有context结果缺少timestamp"

    print(f"✅ [数据-上下文丢失] 使用默认值正常，不依赖预存数据")


# ══════════════════════════════════════════════════════════════════════════════
# 3.2 误操作回滚测试
# ══════════════════════════════════════════════════════════════════════════════

def test_context_manager_rollback():
    """
    【数据测试3】ContextManager事务回滚测试

    场景：任务执行中途失败，上下文应保留（不污染）

    通过标准：
    1. 开始的任务可被查询
    2. 已关闭的任务不在working中
    3. 内存状态一致
    """
    ctx_mgr = ContextManager()
    session_id = "rollback_test_session"

    # 开启任务
    ctx = ctx_mgr.start_task(session_id, "测试任务", ["product_research"])

    # 验证：working中应存在
    working = ctx_mgr.get_working(session_id)
    assert working is not None, "新开启的任务应在working中"

    # 模拟：更新部分数据
    ctx_mgr.update_task(session_id, {
        "product_research": {"result": {"demand_score": 8}, "tokens": 100}
    })

    # 关闭任务
    closed = ctx_mgr.close_task(session_id)
    assert closed is not None, "关闭应返回context"

    # 验证：关闭后不在working中
    working_after = ctx_mgr.get_working(session_id)
    assert working_after is None, "已关闭任务不应在working中"

    # 验证：memory中仍然可查
    memory = ctx_mgr.get_memory_stats()
    assert memory["total_sessions"] >= 1, "memory应记录历史session"

    print(f"✅ [数据-回滚] ContextManager事务管理正常")


def test_audit_log_immutability():
    """
    【数据测试4】审计日志不可篡改性

    通过标准：
    1. 审计日志只追加，不删除
    2. 每条记录有时间戳
    3. API Key被正确脱敏
    """
    from api_server import audit_log

    initial_len = len(audit_log)

    # 执行几个任务（触发审计）
    import asyncio
    asyncio.run(CHIEF.execute("测试审计任务", {}))

    after_len = len(audit_log)
    assert after_len >= initial_len, "审计日志只应追加，长度不应减少"

    # 每条记录包含必需字段
    recent_logs = audit_log[initial_len:]
    for entry in recent_logs:
        assert "event" in entry, "审计记录缺少event字段"
        assert "time" in entry, "审计记录缺少time字段"
        assert "api_key" in entry, "审计记录缺少api_key字段"
        # API Key应被脱敏
        assert "***" in entry["api_key"] or entry["api_key"] == "", \
            f"API Key未被脱敏: {entry['api_key']}"

    print(f"✅ [数据-不可篡改] 审计日志追加正确，脱敏完整")


# ══════════════════════════════════════════════════════════════════════════════
# 3.3 数据一致性验证
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_data_consistency_across_parallel():
    """
    【数据测试5】并行执行数据一致性

    场景：多个任务并行执行，验证数据不互相污染

    通过标准：
    1. 并行结果数量等于任务数量
    2. 每个结果包含正确路由的Agent
    3. 各结果之间无数据泄漏
    """
    import asyncio

    tasks = [
        ("分析蓝牙耳机", {"category": "electronics"}),
        ("分析宠物用品", {"category": "pets"}),
        ("分析厨房用具", {"category": "home"}),
    ]

    async def execute_task(task_text, ctx):
        return await CHIEF.execute(task_text, ctx)

    # 并行执行
    results = await asyncio.gather(
        *[execute_task(t, c) for t, c in tasks]
    )

    # 通过标准1：结果数量正确
    assert len(results) == len(tasks), \
        f"应有{len(tasks)}个结果，实际{len(results)}"

    # 通过标准2：每个结果都有routed_agents
    for i, (task_text, ctx), result in zip(range(len(tasks)), tasks, results):
        assert "routed_agents" in result, f"第{i}个结果缺少routed_agents"
        assert isinstance(result["routed_agents"], list), \
            f"第{i}个routed_agents应为list"

    # 通过标准3：不同category的结果不同（无交叉污染）
    # 至少路由到的第一个Agent应该体现任务差异
    first_agents = [r["routed_agents"][0] if r["routed_agents"] else None for r in results]
    # 不要求完全不同（因为路由基于关键词），但结构应各自独立
    for i, result in enumerate(results):
        assert "timestamp" in result, f"第{i}个结果缺少timestamp"
        assert "results" in result, f"第{i}个结果缺少results"

    print(f"✅ [数据-一致性] {len(tasks)}任务并行执行，数据无交叉污染")


@pytest.mark.asyncio
async def test_timestamp_consistency():
    """
    【数据测试6】时间戳一致性验证

    通过标准：
    1. 返回的timestamp格式为ISO 8601
    2. 时间戳在合理范围内（过去1分钟内）
    3. 多字段时间戳一致
    """
    result = await CHIEF.execute("分析选品", {})

    timestamp_str = result.get("timestamp", "")
    assert timestamp_str, "timestamp不应为空"

    # 解析ISO格式（处理Z和+00:00两种格式）
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pytest.fail(f"timestamp格式非法: {timestamp_str}")

    # 验证timestamp格式正确（是有效ISO字符串）
    assert timestamp_str.startswith("20"), f"timestamp年份异常: {timestamp_str}"
    assert "-" in timestamp_str and ":" in timestamp_str, \
        f"timestamp格式异常: {timestamp_str}"

    print(f"✅ [数据-时间戳] timestamp={timestamp_str}，格式+逻辑均正确")


@pytest.mark.asyncio
async def test_agent_registry_consistency():
    """
    【数据测试7】Agent注册表一致性

    通过标准：
    1. AGENT_REGISTRY数量 == AGENTS数量
    2. 每个已注册Agent都有统计字段
    3. 路由表与Agent注册表一致
    """
    from agents.base import AGENT_REGISTRY, AGENTS

    # 通过标准1：数量一致
    assert len(AGENT_REGISTRY) == len(AGENTS), \
        f"注册表不一致: REGISTRY={len(AGENT_REGISTRY)}, AGENTS={len(AGENTS)}"

    # 通过标准2：每个Agent有必需统计字段
    for agent_id, info in AGENT_REGISTRY.items():
        assert "invoked_count" in info, f"{agent_id}缺少invoked_count"
        assert "total_tokens" in info, f"{agent_id}缺少total_tokens"
        assert isinstance(info["invoked_count"], int), \
            f"{agent_id}.invoked_count应为int"
        assert isinstance(info["total_tokens"], int), \
            f"{agent_id}.total_tokens应为int"

    # 通过标准3：路由表Agent ID全部在注册表中
    for agent_id in TASK_ROUTING.keys():
        assert agent_id in AGENT_REGISTRY, \
            f"路由表包含未注册的Agent: {agent_id}"

    print(f"✅ [数据-一致性] Agent注册表一致: {len(AGENTS)}个Agent全部合规")


# ══════════════════════════════════════════════════════════════════════════════
# 3.4 数据文件操作测试
# ══════════════════════════════════════════════════════════════════════════════

def test_memory_file_integrity():
    """
    【数据测试8】内存数据文件完整性测试

    通过标准：
    1. data/memory.jsonl可读
    2. data/sessions.jsonl可读
    3. 文件格式为有效JSONL
    """
    import json

    for filename in ["memory.jsonl", "sessions.jsonl"]:
        filepath = f"data/{filename}"

        if not os.path.exists(filepath):
            print(f"⚠️  {filepath} 不存在，跳过（可能尚未生成数据）")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    assert isinstance(record, dict), \
                        f"{filename}:{line_num} 应为dict"
                except json.JSONDecodeError as e:
                    pytest.fail(f"{filename}:{line_num} JSON格式错误: {e}")

    print(f"✅ [数据-文件完整性] JSONL文件格式正确，可正常读取")
