"""
TraceContext - 链路上下文管理器
为每个请求生成唯一 trace_id，为每个 Agent 调用生成 span_id。
支持上下文传递（thread-local 或显式propagate）。
"""

from __future__ import annotations

import contextvars
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("amazon_ops.tracing")

# ─── 全局上下文变量 ────────────────────────────────────────────────────────────
_current_trace: contextvars.ContextVar[Optional["TraceContext"]] = (
    contextvars.ContextVar("current_trace", default=None)
)
_span_counter_lock = threading.Lock()
_span_counters: dict[str, int] = {}  # trace_id → counter


# ─── 状态枚举 ─────────────────────────────────────────────────────────────────
class SpanStatus(Enum):
    OK = "ok"          # 成功
    ERROR = "error"    # 失败
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


# ─── Span 类型 ────────────────────────────────────────────────────────────────
class SpanType(Enum):
    ROOT = "root"           # 请求入口（trace root）
    ROUTER = "router"       # TaskRouter 决策
    CHIEF = "chief"         # ChiefOfStaff 调度
    EXECUTOR = "executor"   # LocalExecutor 本地执行
    AGENT = "agent"         # 单一 Agent 执行
    STEP = "step"           # 工作流步骤
    HTTP = "http"           # 外部 API 调用


# ─── Span 数据模型 ────────────────────────────────────────────────────────────
@dataclass
class Span:
    """单个操作单元"""
    trace_id: str
    span_id: str              # 当前 span 的唯一 ID
    parent_span_id: str | None  # 父 span（None 表示 root span）
    name: str                 # 操作名，如 "TaskRouter.route"
    type: SpanType            # span 类型
    status: SpanStatus = SpanStatus.OK
    # ── 记录内容 ──
    input_summary: str = ""          # 输入摘要（截断到200字符）
    output_summary: str = ""         # 输出摘要
    decision: str = ""               # 决策内容（路由决策、Agent选择等）
    # ── 性能 ──
    start_time: str = field(default_factory=lambda: _utc_now())
    end_time: str | None = None
    duration_ms: float | None = None
    # ── 额外 ──
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    # ── 内部 ──
    _started_at: float = field(default_factory=time.time, repr=False)

    def finish(self, status: SpanStatus = SpanStatus.OK,
               output_summary: str = "", error: str | None = None) -> None:
        """标记 span 结束"""
        self.end_time = _utc_now()
        self.duration_ms = round((time.time() - self._started_at) * 1000, 2)
        self.status = status
        if output_summary:
            self.output_summary = output_summary[:200]
        if error:
            self.error = error[:500]
            self.status = SpanStatus.ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "decision": self.decision,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "error": self.error,
        }


# ─── TraceContext ──────────────────────────────────────────────────────────────
class TraceContext:
    """
    全链路追溯上下文

    用法：
    ```python
    # 请求入口
    ctx = TraceContext.start("用户查询: PPC广告优化")
    try:
        # TaskRouter
        with ctx.span("TaskRouter.route", SpanType.ROUTER) as span:
            decision = router.route(task, agents)
            span.finish(decision=f"引擎={decision.engine.value}")

        # ChiefOfStaff
        with ctx.span("ChiefOfStaff.execute", SpanType.CHIEF):
            result = await chief.execute(task)

        # Agent
        with ctx.span(f"Agent.{agent_id}", SpanType.AGENT) as span:
            output = await agent.execute(task)
            span.finish(output_summary=str(output)[:100])

    finally:
        ctx.flush()  # 写入审计日志
    ```
    """

    def __init__(self, trace_id: str | None = None,
                 root_name: str = "request",
                 parent_span_id: str | None = None) -> None:
        self.trace_id = trace_id or _gen_trace_id()
        self.root_name = root_name
        self.spans: list[Span] = []
        self._started_at = time.time()
        self._token = _current_trace.set(self)

    def deflate(self) -> str:
        """压缩格式（用于跨进程传递）"""
        return self.trace_id

    @staticmethod
    def restore(trace_id: str, root_name: str = "continuation") -> "TraceContext":
        """从 trace_id 恢复上下文"""
        return TraceContext(trace_id=trace_id, root_name=root_name)

    # ─── 上下文管理器入口 ────────────────────────────────────────────────────
    def span(self, name: str, span_type: SpanType,
             parent_span_id: str | None = None,
             input_summary: str = "",
             metadata: dict[str, Any] | None = None) -> "_SpanScope":
        """
        创建一个子 span

        Args:
            name:         span 名称，如 "TaskRouter.route"
            span_type:    span 类型
            parent_span_id: 父 span ID（默认用上一个 span）
            input_summary: 输入摘要
            metadata:     额外元数据
        """
        parent = self._last_span_id() if parent_span_id is None else parent_span_id
        span = Span(
            trace_id=self.trace_id,
            span_id=_gen_span_id(self.trace_id),
            parent_span_id=parent,
            name=name,
            type=span_type,
            input_summary=input_summary[:200] if input_summary else "",
            metadata=metadata or {},
        )
        self.spans.append(span)
        return _SpanScope(self, span)

    def _last_span_id(self) -> str | None:
        return self.spans[-1].span_id if self.spans else None

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    # ─── 快捷方法 ────────────────────────────────────────────────────────────
    def record_router(self, task: str, decision: Any) -> Span:
        """快捷记录 TaskRouter 决策"""
        # 安全提取属性（避免 mock 对象序列化失败）
        engine_val = getattr(decision, "engine", None)
        engine_str = getattr(engine_val, "value", str(engine_val)) if engine_val else None
        span = Span(
            trace_id=self.trace_id,
            span_id=_gen_span_id(self.trace_id),
            parent_span_id=self._last_span_id(),
            name="TaskRouter.route",
            type=SpanType.ROUTER,
            input_summary=task[:200],
            decision=str(decision),
            metadata={
                "engine": engine_str,
                "complexity_score": getattr(decision, "complexity_score", None),
                "estimated_tokens": getattr(decision, "estimated_tokens", None),
                "agent_ids": getattr(decision, "agent_ids", []),
            },
        )
        self.spans.append(span)
        return span

    def record_executor(self, task: str, result: Any, success: bool) -> Span:
        """快捷记录 LocalExecutor 执行"""
        err = getattr(result, "error", None) if not success else None
        span = Span(
            trace_id=self.trace_id,
            span_id=_gen_span_id(self.trace_id),
            parent_span_id=self._last_span_id(),
            name="LocalExecutor.execute",
            type=SpanType.EXECUTOR,
            input_summary=task[:200],
            status=SpanStatus.OK if success else SpanStatus.ERROR,
            output_summary=getattr(result, "message", str(result))[:200] if result else "",
            error=err,
            metadata={"engine": "local", "tokens": 0},
        )
        self.spans.append(span)
        return span

    def record_agent(self, agent_id: str, task: str,
                     output: Any, tokens: int,
                     success: bool = True,
                     error: str | None = None) -> Span:
        """快捷记录单个 Agent 执行"""
        output_str = str(output)[:200] if output else ""
        err_str = error or (str(output)[:500] if (not success and isinstance(output, Exception)) else None)
        span = Span(
            trace_id=self.trace_id,
            span_id=_gen_span_id(self.trace_id),
            parent_span_id=self._last_span_id(),
            name=f"Agent.{agent_id}",
            type=SpanType.AGENT,
            input_summary=task[:200],
            status=SpanStatus.OK if success else SpanStatus.ERROR,
            output_summary=output_str,
            error=err_str,
            metadata={"agent_id": agent_id, "tokens": tokens},
        )
        self.spans.append(span)
        return span

    def record_error(self, name: str, error: str | Exception,
                     span_type: SpanType = SpanType.STEP) -> Span:
        """快捷记录错误"""
        err_str = str(error)[:500]
        span = Span(
            trace_id=self.trace_id,
            span_id=_gen_span_id(self.trace_id),
            parent_span_id=self._last_span_id(),
            name=name,
            type=span_type,
            status=SpanStatus.ERROR,
            error=err_str,
            end_time=_utc_now(),
            duration_ms=None,
        )
        self.spans.append(span)
        return span

    # ─── 完成 & 导出 ─────────────────────────────────────────────────────────
    def flush(self) -> dict[str, Any]:
        """将所有 span 写入审计日志并返回 trace 报告"""
        from .audit_trail import audit_log

        if not self.spans:
            logger.warning(f"[TraceContext] trace_id={self.trace_id} 没有记录任何 span")
            return self.summary()

        total_ms = round((time.time() - self._started_at) * 1000, 2)
        for s in self.spans:
            if s.end_time is None:
                s.end_time = _utc_now()
                s.duration_ms = round((time.time() - s._started_at) * 1000, 2)

        audit_log.append_trace(self)
        logger.info(
            f"[TraceContext] flush trace_id={self.trace_id} | "
            f"spans={len(self.spans)} | total_ms={total_ms}"
        )
        return self.summary()

    def summary(self) -> dict[str, Any]:
        """获取 trace 摘要"""
        total_ms = round((time.time() - self._started_at) * 1000, 2)
        error_count = sum(1 for s in self.spans if s.status == SpanStatus.ERROR)
        return {
            "trace_id": self.trace_id,
            "root_name": self.root_name,
            "total_spans": len(self.spans),
            "total_ms": total_ms,
            "error_count": error_count,
            "spans": [s.to_dict() for s in self.spans],
        }

    def close(self) -> None:
        """清理上下文变量"""
        try:
            _current_trace.reset(self._token)
        except Exception:
            pass

    def __enter__(self) -> "TraceContext":
        return self

    def __exit__(self, *_: Any) -> None:
        self.flush()
        self.close()


# ─── _SpanScope ────────────────────────────────────────────────────────────────
class _SpanScope:
    """with 语句作用域，自动记录结束时间"""
    __slots__ = ("_ctx", "_span")

    def __init__(self, ctx: TraceContext, span: Span) -> None:
        self._ctx = ctx
        self._span = span

    def __enter__(self) -> Span:
        return self._span

    def __exit__(self, exc_type: Any, exc_val: Any, _: Any) -> bool:
        if exc_val:
            self._span.finish(
                status=SpanStatus.ERROR,
                error=str(exc_val)[:500],
            )
        return False  # 不吞掉异常

    def finish(self, **kwargs: Any) -> None:
        self._span.finish(**kwargs)


# ─── 全局入口 ─────────────────────────────────────────────────────────────────
def start_trace(name: str = "request",
                trace_id: str | None = None) -> TraceContext:
    """
    开始一个新的 trace

    用法：
    ```python
    ctx = start_trace("用户: 优化PPC广告")
    ```
    """
    return TraceContext(trace_id=trace_id, root_name=name)


def get_current_trace() -> TraceContext | None:
    """获取当前上下文的 trace（thread-safe）"""
    return _current_trace.get()


def current_span() -> Span | None:
    """获取当前活跃的 span"""
    ctx = get_current_trace()
    return ctx.spans[-1] if ctx and ctx.spans else None


# ─── ID 生成 ──────────────────────────────────────────────────────────────────
def _gen_trace_id() -> str:
    return uuid.uuid4().hex[:16]  # 16位可读ID


def _gen_span_id(trace_id: str) -> str:
    """线程安全的 span_id 自增"""
    with _span_counter_lock:
        count = _span_counters.get(trace_id, 0) + 1
        _span_counters[trace_id] = count
        return f"{trace_id[:8]}-{count:04d}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
