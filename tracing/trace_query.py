"""
TraceQuery - 逆向查询工具
提供从结果追溯原因的多种查询路径：

- reverse_from_result : 从 span_id → 完整链路（根因分析）
- trace_full_chain    : 从 trace_id → 全链路时序图
- find_root_cause     : 从 error span → 根本原因
- trace_by_agent      : 按 Agent 聚合所有执行记录
- compare_traces       : 对比两条 trace 的执行差异
"""

from __future__ import annotations

import json
import logging
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .audit_trail import audit_log, AuditTrail
from .trace_context import SpanStatus, SpanType

logger = logging.getLogger("amazon_ops.tracing.query")

# ─── 查询结果包装 ─────────────────────────────────────────────────────────────
@dataclass
class TraceQueryResult:
    """统一查询结果"""
    trace_id: str
    total_spans: int
    total_ms: float
    error_count: int
    root_span: dict[str, Any] | None = None
    spans: list[dict[str, Any]] = field(default_factory=list)
    root_cause: dict[str, Any] | None = None
    summary: str = ""

    def render_timeline(self) -> str:
        """渲染人类可读的时序图"""
        lines = [
            f"{'─' * 60}",
            f"  Trace {self.trace_id}  ({self.total_ms:.1f}ms, "
            f"{self.total_spans} spans, "
            f"{'✅' if self.error_count == 0 else f'❌ {self.error_count} errors'})",
            f"{'─' * 60}",
            f"  {'Time':<12} {'Span':<30} {'Type':<12} {'Status':<8} {'Duration'}",
            f"  {'-' * 12} {'-' * 30} {'-' * 12} {'-' * 8} {'-' * 10}",
        ]
        for s in self.spans:
            status_icon = {
                "ok": "✅", "error": "❌",
                "timeout": "⏱", "skipped": "⏭",
            }.get(s.get("status", ""), "➡")

            name = s.get("name", "?")[:28]
            stype = s.get("type", "?")[:12]
            dur = f"{s.get('duration_ms', 0):.1f}ms"
            indent = "  └─" if s.get("parent_span_id") else "  ●"
            lines.append(
                f"{indent} {name:<30} {stype:<12} {status_icon:<4} {dur:<10}  "
                f"{(s.get('error') or '')[:40]}"
            )
        lines.append(f"{'─' * 60}")
        return "\n".join(lines)

    def render_tree(self) -> str:
        """渲染树形结构（父子关系）"""
        if not self.spans:
            return "No spans"

        # 构建 id → span 映射
        span_map: dict[str, dict] = {s["span_id"]: s for s in self.spans}
        children_map: dict[str, list[dict]] = {}

        for s in self.spans:
            pid = s.get("parent_span_id")
            children_map.setdefault(pid, []).append(s)

        def render_node(span_id: str | None, indent: str = "") -> list[str]:
            lines = []
            for s in children_map.get(span_id, []):
                status_icon = "✅" if s.get("status") == "ok" else "❌"
                dur = f"{s.get('duration_ms', 0):.1f}ms"
                err = f" ⚠ {(s.get('error') or '')[:30]}" if s.get('error') else ""
                lines.append(
                    f"{indent}{status_icon} [{s.get('span_id', ''):<14}] "
                    f"{s.get('name', ''):<30} {dur}{err}"
                )
                lines.extend(render_node(s["span_id"], indent + "    "))
            return lines

        header = [
            f"Trace {self.trace_id} — Tree View",
            "=" * 60,
        ]
        return "\n".join(header + render_node(None) + ["=" * 60])

    def render_report(self) -> str:
        """生成 Markdown 格式报告"""
        parts = [
            f"# Trace Report: `{self.trace_id}`",
            "",
            f"- **Total Spans**: {self.total_spans}",
            f"- **Total Duration**: {self.total_ms:.1f}ms",
            f"- **Errors**: {self.error_count}",
            "",
        ]

        if self.root_cause:
            parts.append("## Root Cause\n")
            rc = self.root_cause
            parts.append(f"- **Error**: `{rc.get('error', 'N/A')}`")
            parts.append(f"- **Source Span**: `{rc.get('span_id', '')}` at `{rc.get('start_time', '')}`")
            parts.append(f"- **Affected Agent**: `{rc.get('metadata', {}).get('agent_id', 'N/A')}`")
            parts.append("")

        parts.append("## Span Timeline\n")
        parts.append("| # | Span ID | Name | Type | Status | Duration |")
        parts.append("|---|----------|------|------|--------|----------|")
        for i, s in enumerate(self.spans):
            parts.append(
                f"| {i} | `{s.get('span_id', '')}` | "
                f"{s.get('name', '')} | {s.get('type', '')} | "
                f"{s.get('status', '')} | "
                f"{s.get('duration_ms', 0):.1f}ms |"
            )

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_spans": self.total_spans,
            "total_ms": self.total_ms,
            "error_count": self.error_count,
            "root_span": self.root_span,
            "spans": self.spans,
            "root_cause": self.root_cause,
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ─── TraceQuery 主类 ──────────────────────────────────────────────────────────
class TraceQuery:
    """
    链路逆向查询工具

    用法：
    ```python
    from tracing.trace_query import TraceQuery

    tq = TraceQuery()

    # 从 span 逆向追溯
    result = tq.reverse_from_result("abc123-0001")
    print(result.render_timeline())

    # 查询完整链路
    result = tq.trace_full_chain("trace-id-abc")
    print(result.render_tree())

    # 查找根本原因
    result = tq.find_root_cause(span_id="error-span-id")

    # 按 Agent 聚合
    agent_traces = tq.trace_by_agent("ppc_manager", limit=10)
    ```
    """

    def __init__(self, backend: AuditTrail | None = None) -> None:
        self._backend = backend or audit_log

    # ─── 核心查询 ────────────────────────────────────────────────────────────
    def reverse_from_result(self, span_id: str) -> TraceQueryResult:
        """
        从任意 span_id 逆向追溯完整链路。

        典型场景：
        - 用户报告："我的 PPC 广告优化结果不对"
          → 用户从 UI 获取错误 span_id → 逆向查询根因

        - 监控告警："某 trace 耗时 5s"
          → 从耗时超标的 span 逆向查看父链路各节点耗时

        Returns:
            TraceQueryResult 含 parent_chain + child_spans + full_trace
        """
        data = self._backend.reverse_query(span_id)
        if not data:
            return TraceQueryResult(
                trace_id=span_id,
                total_spans=0,
                total_ms=0,
                error_count=0,
                summary=f"[ERROR] span_id={span_id} not found in audit log",
            )

        target = data["target_span"]
        parent_chain = data["parent_chain"]
        children = data["child_spans"]
        trace_summary = data["trace_summary"]

        # 构建完整链路（父链 + 目标 + 子链，按时序排列）
        all_spans = trace_summary["spans"]

        # 标记因果方向
        root_span = all_spans[0] if all_spans else None

        result = TraceQueryResult(
            trace_id=trace_summary["trace_id"],
            total_spans=len(all_spans),
            total_ms=sum(s.get("duration_ms", 0) or 0 for s in all_spans),
            error_count=sum(1 for s in all_spans if s.get("status") == "error"),
            root_span=root_span,
            spans=all_spans,
            root_cause=self._find_root_cause_in_chain(
                [target] + parent_chain + children
            ),
        )

        # 生成摘要
        if parent_chain:
            parent_names = " → ".join(s.get("name", "?") for s in reversed(parent_chain))
            result.summary = (
                f"Root cause traced: {target.get('name')} "
                f"(parent: {parent_names}). "
                f"Total {len(children)} downstream spans affected."
            )
        else:
            result.summary = f"Root span: {target.get('name')} (no parents)."

        return result

    def trace_full_chain(self, trace_id: str) -> TraceQueryResult:
        """
        从 trace_id 获取完整链路

        典型场景：
        - 运维排查："帮我看一下 trace abc123 的完整执行"
        - 开发调试："这个请求走过了哪些 Agent？"
        """
        trace = self._backend.get_trace(trace_id)
        if not trace:
            return TraceQueryResult(
                trace_id=trace_id,
                total_spans=0,
                total_ms=0,
                error_count=0,
                summary=f"[ERROR] trace_id={trace_id} not found",
            )

        spans = trace.get("spans", [])
        return TraceQueryResult(
            trace_id=trace_id,
            total_spans=len(spans),
            total_ms=trace.get("total_ms", 0) or 0,
            error_count=trace.get("error_count", 0),
            root_span=spans[0] if spans else None,
            spans=spans,
            root_cause=self._find_root_cause_in_chain(spans),
            summary=self._build_summary(spans),
        )

    def find_root_cause(self, span_id: str) -> TraceQueryResult:
        """
        找到错误的根本原因（第一个 error span 为根因）

        典型场景：
        - 自动化告警处理
        - 根因分析自动化
        """
        data = self._backend.reverse_query(span_id)
        if not data:
            return TraceQueryResult(
                trace_id=span_id,
                total_spans=0,
                total_ms=0,
                error_count=0,
                summary=f"[ERROR] span_id={span_id} not found",
            )

        spans = data["trace_summary"]["spans"]
        # 从根到叶找第一个 error
        root_cause = None
        for s in spans:
            if s.get("status") == "error":
                root_cause = s
                break

        return TraceQueryResult(
            trace_id=data["trace_summary"]["trace_id"],
            total_spans=len(spans),
            total_ms=sum(s.get("duration_ms", 0) or 0 for s in spans),
            error_count=sum(1 for s in spans if s.get("status") == "error"),
            root_span=spans[0] if spans else None,
            spans=spans,
            root_cause=root_cause,
            summary=self._summarize_root_cause(root_cause, spans),
        )

    # ─── 聚合查询 ────────────────────────────────────────────────────────────
    def trace_by_agent(self, agent_id: str, limit: int = 20) -> list[TraceQueryResult]:
        """
        查询某个 Agent 的所有执行记录（按时间倒序）

        典型场景：
        - "ppc_manager 最近执行了多少次？成功率如何？"
        - "GUI Agent 执行过哪些操作？"
        """
        spans = self._backend.query(agent_id=agent_id, limit=limit * 5)
        seen_traces = set()
        results = []

        for s in spans:
            tid = s["trace_id"]
            if tid in seen_traces:
                continue
            seen_traces.add(tid)
            trace = self._backend.get_trace(tid)
            if trace:
                spans_in_trace = trace.get("spans", [])
                results.append(TraceQueryResult(
                    trace_id=tid,
                    total_spans=len(spans_in_trace),
                    total_ms=trace.get("total_ms", 0) or 0,
                    error_count=trace.get("error_count", 0),
                    root_span=spans_in_trace[0] if spans_in_trace else None,
                    spans=spans_in_trace,
                ))
            if len(results) >= limit:
                break

        return results

    def recent_errors(self, limit: int = 10) -> list[TraceQueryResult]:
        """最近的错误 trace"""
        error_traces = self._backend.find_error_traces(limit=limit)
        return [
            TraceQueryResult(
                trace_id=t.get("trace_id"),
                total_spans=len(t.get("spans", [])),
                total_ms=t.get("total_ms", 0) or 0,
                error_count=t.get("error_count", 0),
                root_span=t.get("spans", [{}])[0] if t.get("spans") else None,
                spans=t.get("spans", []),
            )
            for t in error_traces
        ]

    def slow_traces(self, threshold_ms: float = 2000,
                    limit: int = 10) -> list[TraceQueryResult]:
        """最慢的 trace（总耗时超过阈值）"""
        slow_spans = self._backend.find_slow_spans(threshold_ms)
        trace_ids = list(dict.fromkeys(s["trace_id"] for s in slow_spans))
        results = []
        for tid in trace_ids:
            trace = self._backend.get_trace(tid)
            if trace and (trace.get("total_ms") or 0) > threshold_ms:
                spans = trace.get("spans", [])
                results.append(TraceQueryResult(
                    trace_id=tid,
                    total_spans=len(spans),
                    total_ms=trace.get("total_ms", 0) or 0,
                    error_count=trace.get("error_count", 0),
                    root_span=spans[0] if spans else None,
                    spans=spans,
                ))
            if len(results) >= limit:
                break
        return results

    def compare_traces(self, trace_id_a: str, trace_id_b: str) -> str:
        """
        对比两条 trace 的差异

        典型场景：
        - "优化前后的执行路径有什么不同？"
        """
        t_a = self.trace_full_chain(trace_id_a)
        t_b = self.trace_full_chain(trace_id_b)

        lines = [
            "## Trace Comparison",
            "",
            f"| Metric | `{trace_id_a}` | `{trace_id_b}` |",
            f"|--------|------|------|",
            f"| Total Spans | {t_a.total_spans} | {t_b.total_spans} |",
            f"| Total Duration | {t_a.total_ms:.1f}ms | {t_b.total_ms:.1f}ms |",
            f"| Errors | {t_a.error_count} | {t_b.error_count} |",
        ]

        # Span 对比
        names_a = {s.get("name") for s in t_a.spans}
        names_b = {s.get("name") for s in t_b.spans}
        only_a = names_a - names_b
        only_b = names_b - names_a

        if only_a or only_b:
            lines.extend(["", "### Span Differences", ""])
            if only_a:
                lines.append(f"- Only in `{trace_id_a}`: {', '.join(sorted(only_a))}")
            if only_b:
                lines.append(f"- Only in `{trace_id_b}`: {', '.join(sorted(only_b))}")

        return "\n".join(lines)

    # ─── 内部工具 ────────────────────────────────────────────────────────────
    def _find_root_cause_in_chain(
        self, spans: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """在给定链表中找第一个错误 span 作为根因"""
        for s in spans:
            if s.get("status") == "error":
                return s
        return None

    def _build_summary(self, spans: list[dict[str, Any]]) -> str:
        if not spans:
            return "Empty trace"

        # 按类型分组耗时
        by_type: dict[str, list[float]] = {}
        for s in spans:
            t = s.get("type", "?")
            by_type.setdefault(t, []).append(s.get("duration_ms") or 0)

        type_summary = ", ".join(
            f"{t}={sum(v):.0f}ms" for t, v in sorted(by_type.items())
        )
        return (
            f"{len(spans)} spans, "
            f"{sum(s.get('duration_ms',0) or 0 for s in spans):.1f}ms total. "
            f"Breakdown: {type_summary}"
        )

    def _summarize_root_cause(
        self, root_cause: dict[str, Any] | None,
        spans: list[dict[str, Any]]
    ) -> str:
        if not root_cause:
            return "No error found in trace"

        return (
            f"Root cause identified: `{root_cause.get('name')}` "
            f"error='{root_cause.get('error', '')[:80]}'. "
            f"Affected {sum(1 for s in spans if s.get('parent_span_id') == root_cause.get('span_id'))} "
            f"downstream spans."
        )


# ─── 全局便捷实例 ─────────────────────────────────────────────────────────────
query = TraceQuery()
