# 全链路追溯系统使用指南

> 适用版本：amazon-ops-agents ≥ 1.0.0
> 最后更新：2026-04-13

---

## 目录

- [概述](#概述)
- [核心概念](#核心概念)
- [5 大典型场景](#5-大典型场景)
- [常见问题排查流程](#常见问题排查流程)
- [API 参考](#api-参考)
- [最佳实践](#最佳实践)

---

## 概述

全链路追溯系统（Tracing）基于 **OpenTelemetry 思想**，为每个 API 请求分配唯一 `trace_id`，为每个操作单元记录 `span`，最终写入 SQLite + JSONL 双后端审计日志。

**系统架构**

```
用户请求
   │
   ▼
TraceContext.start()         ← 生成 trace_id，建立链路上下文
   │
   ├── span("TaskRouter")    ← 路由决策记录
   │
   ├── span("ChiefOfStaff")  ← 调度中心记录
   │
   ├── span("Agent.xxx")     ← 每个 Agent 调用记录
   │
   └── ctx.flush()           ← 写入 AuditTrail (SQLite + JSONL)
           │
           ▼
      TraceQuery ←── 逆向查询/根因分析/聚合统计
```

---

## 核心概念

### trace_id

全局唯一请求标识，16 位十六进制字符串（如 `a1b2c3d4e5f60718`）。
在 API 响应的 `trace_id` 字段中返回，用户报告问题时提供此 ID 即可快速定位。

### span

链路中的最小操作单元，记录：

| 字段 | 说明 |
|------|------|
| `trace_id` | 所属请求 ID |
| `span_id` | 当前 span 唯一 ID |
| `parent_span_id` | 父 span（构建调用树） |
| `name` | 操作名，如 `TaskRouter.route` |
| `type` | 类型：root / router / chief / agent / executor / http / step |
| `status` | ok / error / timeout / skipped |
| `duration_ms` | 执行耗时（毫秒） |
| `error` | 错误信息（若有） |

### AuditTrail

审计日志管理器，支持：

- **SQLite 后端**：高性能查询，支持按 trace_id / agent_id / status 检索
- **JSONL.gz 后端**：追加归档，用于长期存储和离线分析

---

## 5 大典型场景

### 场景 1：用户报告结果错误 → 逆向追溯根因

**触发条件**：用户报告"某个 Agent 输出不符合预期"

**步骤**：

```python
from tracing.trace_query import TraceQuery

tq = TraceQuery()

# 用户提供 trace_id（如从 API 响应获取）
result = tq.trace_full_chain("a1b2c3d4e5f60718")

# 渲染时序图
print(result.render_timeline())

# 渲染树形结构（父子关系）
print(result.render_tree())

# 输出 Markdown 报告
print(result.render_report())
```

**典型输出**：

```
────────────────────────────────────────────────────────
  Trace a1b2c3d4e5f60718  (4521.3ms, 6 spans, ❌ 1 errors)
────────────────────────────────────────────────────────
  ● TaskRouter.route          router      ✅  12.4ms
  └─ Agent.ppc_manager         agent       ✅  2100.0ms
  └─ Agent.review_monitor     agent       ❌  2340.0ms  HTTP 503: Service Unavailable
────────────────────────────────────────────────────────
```

**关键点**：找到 `status=error` 的 span，沿 `parent_span_id` 向上追溯，找到第一个出错的 span 即为根因。

---

### 场景 2：监控告警 → 自动分析慢 trace

**触发条件**：监控发现某 trace 耗时超过 5 秒

**步骤**：

```python
from tracing.trace_query import TraceQuery

tq = TraceQuery()

# 方式 A：查某条具体 trace
slow = tq.slow_traces(threshold_ms=5000, limit=10)
for s in slow:
    print(f"trace={s.trace_id} | total_ms={s.total_ms:.0f}ms | errors={s.error_count}")

# 方式 B：从 span_id 逆向分析
result = tq.reverse_from_result("error-span-id-0001")
print(result.summary)  # 输出根因摘要
```

**慢 trace 健康阈值建议**：

| 阈值 | 含义 | 建议动作 |
|------|------|----------|
| `< 500ms` | 优秀 | 正常 |
| 500ms - 2000ms | 良好 | 关注 |
| 2000ms - 5000ms | 警告 | 分析具体 Agent |
| `> 5000ms` | 严重 | 必须排查 |

---

### 场景 3：按 Agent 聚合 → 找到高频问题 Agent

**触发条件**：想知道哪个 Agent 最近出错最多

```python
from tracing.trace_query import TraceQuery

tq = TraceQuery()

# 查询某 Agent 最近执行记录
records = tq.trace_by_agent("ppc_manager", limit=20)
for r in records:
    icon = "✅" if r.error_count == 0 else "❌"
    print(f"{icon} {r.trace_id[:16]} | spans={r.total_spans} | "
          f"duration={r.total_ms:.0f}ms | errors={r.error_count}")

# 查询所有最近的错误 trace
errors = tq.recent_errors(limit=10)
for e in errors:
    print(f"❌ trace={e.trace_id[:16]} | errors={e.error_count}")
```

---

### 场景 4：对比优化前后 trace → 验证性能提升

**触发条件**：优化后想验证执行路径是否有改善

```python
from tracing.trace_query import TraceQuery

tq = TraceQuery()

# 优化前 trace vs 优化后 trace
comparison = tq.compare_traces(
    "before-opt-trace-id",
    "after-opt-trace-id"
)
print(comparison)
```

**典型输出**：

```markdown
## Trace Comparison

| Metric | `before-opt` | `after-opt` |
|--------|------|------|
| Total Spans | 8 | 6 |
| Total Duration | 5230.0ms | 3100.0ms |
| Errors | 2 | 0 |

### Span Differences

- Only in `before-opt`: ChiefOfStaff.retry, Agent.repricing
- Only in `after-opt`: Agent.caching
```

---

### 场景 5：跨请求传播 trace_id → 分布式链路追踪

**触发条件**：请求经过多个服务（如 API Server → Worker），需关联完整链路

**HTTP 传播示例**：

```python
# ── API Server 端：生成并传递 trace_id ──────────────────────────────────────
@app.post("/api/v1/execute")
async def execute_task(req: ExecuteRequest, request: Request):
    # 从 header 获取外部传入的 trace_id（若有）
    incoming_trace = request.headers.get("X-Trace-ID")

    response = await CHIEF.execute(
        task=req.task,
        trace_id=incoming_trace,        # ← 传入外部 trace_id
        trace_root_name=f"POST /api/v1/execute",  # ← 自定义根名称
    )

    # 响应中携带 trace_id，方便客户端记录
    return {"trace_id": response["trace_id"], ...}

# ── Worker 端：恢复 trace_id ─────────────────────────────────────────────────
def process_task_from_queue(task_data: dict):
    trace_id = task_data.get("trace_id")
    if trace_id:
        ctx = TraceContext.restore(
            trace_id=trace_id,
            root_name=f"Queue Worker: {task_data['job_id']}",
        )
        try:
            result = do_work(task_data)
            ctx.flush()
        finally:
            ctx.close()
    else:
        # 无 trace_id，照常执行
        result = do_work(task_data)
    return result
```

---

## 常见问题排查流程

### 问题 1：API 返回 500 错误，但无 trace_id

**排查步骤**：

1. 检查 `api_server.py` 的 `global_exception_handler` 是否正常记录日志
2. 查看 `data/traces/audit_trail.db` 是否有对应的 trace 记录
3. 由于异常在 TraceContext 创建前发生，该请求不会有 trace_id

**修复方案**：参见 [错误处理集成](#错误处理集成)

### 问题 2：trace_id 存在但查不到数据

**可能原因**：

- trace_ctx.flush() 未被调用（代码路径异常跳过 finally）
- SQLite WAL 锁冲突（高并发写入）

**排查步骤**：

```python
from tracing import audit_log

# 确认 trace 是否存在于审计日志
trace = audit_log.get_trace("your-trace-id")
if not trace:
    print("Trace not found - 可能未被 flush")

# 检查审计日志统计
stats = audit_log.stats()
print(f"Total traces: {stats['total_traces']}")
print(f"Error rate: {stats['error_rate']}%")
```

### 问题 3：慢 trace 排查

```python
from tracing.trace_query import TraceQuery

tq = TraceQuery()

# Step 1: 找到所有慢 span
slow_spans = audit_log.find_slow_spans(threshold_ms=2000)
print(f"发现 {len(slow_spans)} 个慢 span")

# Step 2: 逐一分析
for span in slow_spans[:5]:
    tid = span["trace_id"]
    sid = span["span_id"]
    print(f"\n慢 span: {sid} in trace {tid[:16]}, duration={span['duration_ms']:.0f}ms")

    # Step 3: 逆向追溯完整链路
    result = tq.reverse_from_result(sid)
    print(result.render_timeline())
```

### 问题 4：错误率高居不下

```python
from tracing import audit_log

# 查看最近 24 小时的错误率趋势
stats = audit_log.stats()
print(f"当前错误率: {stats['error_rate']}%")
print(f"各类型分布: {stats['type_breakdown']}")

# 找出最容易出错的 Agent
error_traces = audit_log.find_error_traces(limit=100)
agent_errors = {}
for t in error_traces:
    for span in t.get("spans", []):
        if span.get("status") == "error" and span.get("agent_id"):
            agent = span["agent_id"]
            agent_errors[agent] = agent_errors.get(agent, 0) + 1

print("出错的 Agent TOP 5:")
for agent, count in sorted(agent_errors.items(), key=lambda x: -x[1])[:5]:
    print(f"  {agent}: {count} 次")
```

---

## API 参考

### TraceContext

```python
from tracing import start_trace, TraceContext, SpanType, SpanStatus

# 创建新 trace
ctx = start_trace("任务描述")
ctx = TraceContext.start(name="根操作名", trace_id=None)  # 可指定外部 trace_id

# 记录 span（with 语法，自动记录结束时间）
with ctx.span("TaskRouter.route", SpanType.ROUTER) as span:
    span.input_summary = "任务内容摘要"
    # 执行业务逻辑
    span.finish(output_summary="路由结果", decision="引擎=small_model")

# 快捷方法
ctx.record_router(task, routing_decision)     # 记录路由决策
ctx.record_executor(task, result, success)     # 记录执行结果
ctx.record_agent(agent_id, task, output, tokens, success)  # 记录 Agent
ctx.record_error("step.name", error_exception) # 记录错误

# 强制 flush 到审计日志
summary = ctx.flush()

# 获取 trace_id
print(ctx.trace_id)  # "a1b2c3d4e5f60718"

# 关闭上下文
ctx.close()
```

### TraceQuery

```python
from tracing.trace_query import TraceQuery, query

tq = TraceQuery()

# 从 trace_id 获取完整链路
result = tq.trace_full_chain("a1b2c3d4e5f60718")

# 从任意 span 逆向追溯
result = tq.reverse_from_result("abc123-0001")

# 查找根本原因
result = tq.find_root_cause(span_id="error-span-id")

# 按 Agent 聚合查询
results = tq.trace_by_agent("ppc_manager", limit=20)

# 最近的错误 trace
errors = tq.recent_errors(limit=10)

# 慢 trace
slow = tq.slow_traces(threshold_ms=2000, limit=10)

# 对比两条 trace
comparison = tq.compare_traces("trace-a", "trace-b")

# 渲染输出
result.render_timeline()   # 时序图
result.render_tree()      # 树形结构
result.render_report()    # Markdown 报告
result.to_json()          # JSON 格式
```

### AuditTrail

```python
from tracing import audit_log

# 统计信息
stats = audit_log.stats()

# 按 trace_id 查询
trace = audit_log.get_trace("a1b2c3d4e5f60718")

# 原始查询
spans = audit_log.query(
    trace_id="xxx",
    agent_id="ppc_manager",
    status="error",
    limit=100,
)

# 查询慢 span
slow = audit_log.find_slow_spans(threshold_ms=2000)

# 查询错误 trace
errors = audit_log.find_error_traces(limit=50)

# 清理旧数据（保留最近 N 天）
deleted = audit_log.cleanup(keep_days=7)
```

### SpanType 枚举值

| 值 | 说明 | 典型使用场景 |
|----|------|-------------|
| `root` | 请求入口 | `TraceContext.start()` |
| `router` | TaskRouter 决策 | 路由引擎选择 |
| `chief` | ChiefOfStaff 调度 | 幕僚长调度 |
| `executor` | LocalExecutor 本地执行 | 零 Token 处理 |
| `agent` | 单一 Agent 执行 | Agent 调用 |
| `step` | 工作流步骤 | WorkflowEngine 节点 |
| `http` | 外部 API 调用 | 第三方接口 |

### SpanStatus 枚举值

| 值 | 说明 |
|----|------|
| `ok` | 成功完成 |
| `error` | 执行失败 |
| `timeout` | 执行超时 |
| `skipped` | 被跳过（如条件不满足） |

---

## 错误处理集成

### 自动集成（推荐）

在 `api_server.py` 中，错误处理已集成 Tracing：

```python
# 见 api_server.py 的 global_exception_handler
# 失败时自动记录 trace，响应中返回 trace_id
```

响应格式（出错时）：

```json
{
  "code": "INTERNAL_ERROR",
  "message": "服务器内部错误，请联系技术支持",
  "trace_id": "a1b2c3d4e5f60718"
}
```

用户报告问题时，提供 `trace_id` 即可快速回溯。

### 手动集成

在业务代码中手动添加 Tracing：

```python
from tracing import start_trace, SpanType, SpanStatus

def risky_operation(task_id: str, params: dict):
    ctx = start_trace(f"operation[{task_id}]")
    try:
        result = do_work(params)
        ctx.span("work.execute", SpanType.STEP)._span.finish(
            output_summary=f"成功: {result}"
        )
        return result
    except Exception as exc:
        ctx.record_error("work.execute", exc, SpanType.STEP)
        raise
    finally:
        summary = ctx.flush()
        ctx.close()
        # 将 trace_id 附加到异常
        exc.trace_id = ctx.trace_id
        raise exc
```

### 用户反馈时附带 trace

当用户报告问题时，引导用户提供：

```
请提供以下信息以帮助排查：
1. API 响应中的 trace_id（如果有）
2. 请求时间
3. 具体的任务描述
```

---

## 最佳实践

### 1. 始终使用 with 语法

```python
# ✅ 推荐：with 语法确保 span 正确结束
with ctx.span("TaskRouter.route", SpanType.ROUTER) as span:
    decision = router.route(task)
    span.finish(decision=str(decision))

# ❌ 不推荐：手动管理 start/end，容易遗漏
span = ctx.span(...)
# ... 如果中间抛出异常，span 不会被 finish
```

### 2. trace_id 跨请求传播

在 HTTP header 或消息队列中携带 `X-Trace-ID`，确保分布式链路完整：

```python
# 发送方
headers = {"X-Trace-ID": response["trace_id"]}

# 接收方
trace_id = request.headers.get("X-Trace-ID")
ctx = TraceContext.restore(trace_id, root_name="worker[...]")
```

### 3. 错误时附加 trace_id

```python
except Exception as exc:
    ctx.record_error("step.name", exc)
    # 将 trace_id 加入异常信息，便于日志关联
    exc.trace_id = ctx.trace_id
    raise
```

### 4. 定期清理旧数据

```python
# 建议配合定时任务（如 cron）执行
from tracing import audit_log
deleted = audit_log.cleanup(keep_days=7)
print(f"清理完成: {deleted} 条")
```

### 5. 慢 trace 监控阈值建议

| 操作类型 | 正常 | 警告 | 严重 |
|---------|------|------|------|
| TaskRouter | < 50ms | 50-200ms | > 200ms |
| ChiefOfStaff | < 500ms | 500-2000ms | > 2000ms |
| Agent.small | < 2000ms | 2-5s | > 5s |
| Agent.large | < 5000ms | 5-15s | > 15s |

---

## 文件位置

| 文件 | 说明 |
|------|------|
| `tracing/trace_context.py` | 链路上下文管理器 |
| `tracing/audit_trail.py` | 审计日志（双后端） |
| `tracing/trace_query.py` | 逆向查询工具 |
| `data/traces/audit_trail.db` | SQLite 审计数据库 |
| `data/traces/audit_trail.jsonl.gz` | JSONL 归档文件 |
| `scripts/trace_monitor.py` | 自动化监控脚本 |
