"""
Tracing 模块使用示例

演示内容：
1. 手动创建 TraceContext 并记录 span
2. 集成 ChiefOfStaff 自动追踪
3. 逆向查询（从结果追溯原因）
4. 按 Agent 聚合查询
5. 对比两条 trace
"""

import asyncio
import json

# ─── 1. 基础使用 ────────────────────────────────────────────────────────────────
def demo_basic():
    """最基础的 TraceContext 用法"""
    from tracing import start_trace, SpanType, SpanStatus

    # 启动 trace
    ctx = start_trace("用户: 批量导出销售报表")

    # 手动创建 span
    with ctx.span("DataExtract.extract", SpanType.EXECUTOR) as span:
        span.finish(output_summary="提取了 1200 条销售记录")

    with ctx.span("FormatConvert.to_csv", SpanType.EXECUTOR) as span:
        span.finish(output_summary="转换完成，CSV 3.2MB")

    # 记录错误
    ctx.record_error(
        "ExternalAPI.call",
        error="HTTP 503: Service Unavailable",
        span_type=SpanType.HTTP,
    )

    # flush 到审计日志
    summary = ctx.flush()
    ctx.close()

    print("✅ Trace 摘要:", json.dumps(summary, indent=2, ensure_ascii=False))


# ─── 2. 手动模拟完整链路 ───────────────────────────────────────────────────────
def demo_full_chain():
    """
    手动模拟一个完整的多 Agent 链路
    展示：TaskRouter → ChiefOfStaff → Agent × 2 → 完成
    """
    from tracing import start_trace, SpanType, SpanStatus

    ctx = start_trace("用户: 优化 PPC 广告并分析评论")

    # Step 1: TaskRouter 决策
    span_router = ctx.record_router(
        task="优化 PPC 广告的关键词出价策略，并分析最近 7 天评论",
        decision=type("obj", (), {
            "engine": type("E", (), {"value": "small_model"})(),
            "complexity_score": 52,
            "estimated_tokens": 120,
            "agent_ids": ["ppc_manager", "review_monitor"],
        })(),
    )
    span_router.finish()

    # Step 2: ChiefOfStaff 执行
    ctx.span("ChiefOfStaff.execute", SpanType.CHIEF, input_summary="...")._span.finish(
        output_summary="并行执行 2 个 Agent"
    )

    # Step 3: Agent 并行执行
    ctx.record_agent(
        agent_id="ppc_manager",
        task="优化 PPC 广告关键词出价策略",
        output={"keywords_optimized": 25, "estimated_acos": 18.5},
        tokens=110,
        success=True,
    )

    ctx.record_agent(
        agent_id="review_monitor",
        task="分析最近 7 天评论",
        output={"reviews_analyzed": 340, "negative_count": 12},
        tokens=90,
        success=True,
    )

    summary = ctx.flush()
    ctx.close()

    # 渲染时序图
    from tracing import TraceQueryResult
    result = TraceQueryResult(
        trace_id=summary["trace_id"],
        total_spans=summary["total_spans"],
        total_ms=summary["total_ms"],
        error_count=summary["error_count"],
        spans=summary["spans"],
    )
    print("\n📊 完整链路时序图:")
    print(result.render_timeline())


# ─── 3. 逆向查询（从结果追溯原因）─────────────────────────────────────────────
def demo_reverse_query():
    """
    典型根因分析场景：
    用户报告 "review_monitor 输出异常"，运维获取 span_id 后逆向查询。
    """
    from tracing.trace_query import query, TraceQuery

    tq = TraceQuery()

    # 方式A: 从 trace_id 查完整链路
    traces = tq.recent_errors(limit=5)
    if traces:
        latest = traces[0]
        print(f"\n🔍 最近错误 Trace: {latest.trace_id}")
        print(latest.render_timeline())

        # 方式B: 找到根因 span
        if latest.root_cause:
            print(f"\n🎯 根因分析:")
            print(f"   Error: {latest.root_cause.get('error', 'N/A')}")
            print(f"   Span:  {latest.root_cause.get('name')}")
            print(f"   Time:  {latest.root_cause.get('start_time')}")
            # 进一步逆向查询
            result = tq.reverse_from_result(latest.root_cause["span_id"])
            print(f"\n🔙 逆向链路:")
            for s in result.spans:
                icon = "❌" if s.get("status") == "error" else "✅"
                print(f"   {icon} {s.get('name')} ({s.get('duration_ms', 0):.1f}ms)")


# ─── 4. 按 Agent 聚合查询 ────────────────────────────────────────────────────
def demo_agent_aggregation():
    """查看某个 Agent 的所有执行记录"""
    from tracing.trace_query import TraceQuery

    tq = TraceQuery()

    # 查询 ppc_manager 最近 10 次执行
    print("\n📈 ppc_manager 执行记录:")
    records = tq.trace_by_agent("ppc_manager", limit=10)
    if records:
        for r in records[:5]:
            icon = "✅" if r.error_count == 0 else "❌"
            print(
                f"   {icon} trace={r.trace_id[:16]} | "
                f"spans={r.total_spans} | "
                f"duration={r.total_ms:.1f}ms | "
                f"errors={r.error_count}"
            )
    else:
        print("   (暂无数据)")


# ─── 5. 审计日志统计 ─────────────────────────────────────────────────────────
def demo_audit_stats():
    """查看审计日志健康状态"""
    from tracing import audit_log

    stats = audit_log.stats()
    print("\n📊 审计日志统计:")
    print(f"   总 Trace:     {stats['total_traces']}")
    print(f"   总 Span:      {stats['total_spans']}")
    print(f"   错误数:       {stats['error_spans']}")
    print(f"   错误率:       {stats['error_rate']:.2f}%")
    print(f"   总耗时:       {stats['total_ms']:.0f}ms")
    print(f"   SQLite路径:   {stats['sqlite_path']}")
    print(f"\n   各类型 Span 分布:")
    for t, info in stats.get("type_breakdown", {}).items():
        print(f"   - {t:<12}: {info['count']:>4} spans, avg={info['avg_ms']:.1f}ms")


# ─── 6. 慢 trace 分析 ─────────────────────────────────────────────────────────
def demo_slow_traces():
    """查找最慢的 trace"""
    from tracing.trace_query import TraceQuery

    tq = TraceQuery()
    print("\n🐢 最慢的 5 条 Trace:")
    slow = tq.slow_traces(threshold_ms=500, limit=5)
    if slow:
        for s in slow:
            print(
                f"   trace={s.trace_id[:16]} | "
                f"total_ms={s.total_ms:.0f}ms | "
                f"errors={s.error_count}"
            )
    else:
        print("   (暂无慢 trace)")


# ─── 7. 集成 ChiefOfStaff 演示 ────────────────────────────────────────────────
async def demo_chief_integration():
    """
    集成 ChiefOfStaff 的完整追踪示例

    ChiefOfStaff.execute() 会：
    1. 自动创建 TraceContext
    2. 记录 TaskRouter span
    3. 记录每个 Agent span
    4. 执行完成后自动 flush
    5. 在响应中返回 trace_id
    """
    # 注意：这里演示调用结构，实际运行需要完整的 Agent 注册
    # from agents.chief import CHIEF

    # 方式1: 自动生成 trace_id
    # response = await CHIEF.execute(
    #     task="分析本周 PPC 广告表现",
    #     context={"date_range": "7d"},
    # )
    # print(f"trace_id = {response['trace_id']}")

    # 方式2: 传入外部 trace_id（支持跨请求传播，如 HTTP header）
    # response = await CHIEF.execute(
    #     task="优化关键词出价",
    #     trace_id="external-trace-12345",  # 从 HTTP header X-Trace-ID 传入
    #     trace_root_name="POST /api/optimize",
    # )

    print("\n✅ ChiefOfStaff Tracing 集成说明:")
    print("   - 自动为每个 execute() 创建 trace")
    print("   - 路由决策记录为 router span")
    print("   - 每个 Agent 调用记录为 agent span")
    print("   - 响应 JSON 末尾包含 trace_id")
    print("   - 支持通过 trace_id 跨请求传播")


# ─── 8. trace_id 传播示例 ─────────────────────────────────────────────────────
def demo_trace_propagation():
    """
    演示如何在线程/协程之间传播 trace_id
    """
    from tracing import TraceContext, start_trace, get_current_trace

    print("\n🔗 Trace ID 传播示例:")

    # 父 trace
    ctx = start_trace("父请求: 批量处理 10 个 SKU")
    print(f"   父 trace_id: {ctx.trace_id}")

    # 场景1: 显式传递（推荐，用于多线程/进程）
    trace_id_to_pass = ctx.deflate()  # "abc123def456..."
    print(f"   压缩传递:    {trace_id_to_pass}")

    # 场景2: 在子协程中恢复
    def child_task(shared_trace_id: str):
        # 从消息队列/HTTP header 收到的 trace_id
        child_ctx = TraceContext.restore(
            trace_id=shared_trace_id,
            root_name="子任务: 处理单个 SKU",
        )
        child_ctx.span("SKU.process", SpanType=type("S", (), {"value": "step"})())._span.finish()
        summary = child_ctx.flush()
        child_ctx.close()
        return summary

    print(f"   场景: 在 worker 线程中恢复 trace 上下文")


# ─── 9. 根因分析完整流程 ───────────────────────────────────────────────────────
def demo_root_cause_flow():
    """
    完整根因分析流程

    场景: 监控告警触发 → 按 trace_id 查根因
    """
    from tracing.trace_query import TraceQuery

    tq = TraceQuery()

    print("\n🔬 根因分析完整流程:")
    print("=" * 50)
    print("Step 1: 监控发现异常 trace (trace_id=abc123)")
    print("Step 2: 查询完整链路")
    result = tq.trace_full_chain("abc123")  # 如果不存在则返回空

    print("Step 3: 渲染时序图")
    print(result.render_timeline()[:300] if result.spans else "(trace not found)")

    print("\nStep 4: 渲染树形结构（父子关系）")
    print(result.render_tree()[:300] if result.spans else "(trace not found)")

    print("\nStep 5: 生成 Markdown 报告")
    report = result.render_report()
    print(report[:500] if report else "(trace not found)")


# ─── 10. 清理旧数据 ────────────────────────────────────────────────────────────
def demo_cleanup():
    """清理 7 天前的审计数据"""
    from tracing import audit_log

    deleted = audit_log.cleanup(keep_days=7)
    print(f"\n🧹 清理完成: 删除 {deleted} 条旧记录")


# ─── 运行所有示例 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Tracing 模块使用示例")
    print("=" * 60)

    demo_basic()
    demo_full_chain()
    demo_reverse_query()
    demo_agent_aggregation()
    demo_audit_stats()
    demo_slow_traces()
    demo_chief_integration()
    demo_trace_propagation()
    demo_root_cause_flow()
    demo_cleanup()
