"""
Tracing 模块 - 全链路追溯能力

核心组件：
- TraceContext : 链路上下文（trace_id / span_id 管理）
- AuditTrail   : 审计日志（SQLite + JSONL 多后端）
- TraceQuery   : 逆向查询工具（根因分析 / 链路回放）

集成点：
- TaskRouter   : 路由决策记录
- ChiefOfStaff : 任务执行记录
- LocalExecutor: 本地处理记录
"""

from __future__ import annotations

from .audit_trail import AuditTrail, audit_log
from .trace_context import (
    Span,
    SpanStatus,
    SpanType,
    TraceContext,
    current_span,
    get_current_trace,
    start_trace,
)
from .trace_query import TraceQuery, TraceQueryResult, query

__all__ = [
    # 核心上下文
    "TraceContext",
    "Span",
    "SpanType",
    "SpanStatus",
    "start_trace",
    "get_current_trace",
    "current_span",
    # 审计日志
    "AuditTrail",
    "audit_log",
    # 查询工具
    "TraceQuery",
    "TraceQueryResult",
    "query",
]
