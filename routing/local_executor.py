"""
集成 Tracing 的 LocalExecutor
在每个本地处理器执行前后自动记录 span。
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger("amazon_ops.local_executor")

# ─── 处理器注册表 ─────────────────────────────────────────────────────────────
_LOCAL_HANDLERS: dict[str, callable] = {}


def register_handler(pattern: str):
    def deco(fn: callable) -> callable:
        _LOCAL_HANDLERS[pattern] = fn
        return fn
    return deco


@dataclass
class LocalResult:
    success: bool
    engine: str = "local"
    tokens: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ─── 处理器（省略内容，同原版）─────────────────────────────────────────────────
@register_handler(r"提取.*数据|导出.*报表")
def handle_data_extract(task: str, context: dict[str, Any]) -> LocalResult:
    data = context.get("data", [])
    output_format = context.get("format", "json").lower()

    if output_format == "csv" and isinstance(data, list) and data:
        output = io.StringIO()
        if isinstance(data[0], dict):
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        else:
            writer = csv.writer(output)
            writer.writerow(data)
        content = output.getvalue()
        return LocalResult(
            success=True,
            data={"format": "csv", "content": content, "rows": len(data)},
            message=f"导出CSV，共{len(data)}行"
        )

    return LocalResult(
        success=True,
        data={"format": "json", "content": data, "count": len(data) if isinstance(data, list) else 1},
        message="数据已提取为JSON格式"
    )


@register_handler(r"格式转换|转\w*格式|json.*csv|csv.*json")
def handle_format_convert(task: str, context: dict[str, Any]) -> LocalResult:
    content = context.get("content", "")
    source_format = context.get("source_format", "json").lower()
    target_format = context.get("target_format", "csv").lower()

    if target_format == "csv" and source_format == "json":
        try:
            records = json.loads(content) if isinstance(content, str) else content
            if not isinstance(records, list):
                records = [records]
            output = io.StringIO()
            if records and isinstance(records[0], dict):
                writer = csv.DictWriter(output, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)
            return LocalResult(
                success=True,
                data={"csv": output.getvalue(), "rows": len(records)},
                message=f"JSON转CSV成功，{len(records)}行"
            )
        except Exception as exc:
            return LocalResult(success=False, error=f"格式转换失败: {exc}")

    if target_format == "json" and source_format == "csv":
        try:
            reader = csv.DictReader(io.StringIO(content))
            records = list(reader)
            return LocalResult(
                success=True,
                data={"json": records, "rows": len(records)},
                message=f"CSV转JSON成功，{len(records)}行"
            )
        except Exception as exc:
            return LocalResult(success=False, error=f"格式转换失败: {exc}")

    return LocalResult(success=False, error=f"不支持的转换: {source_format}→{target_format}")


@register_handler(r"排序|筛选|过滤|去重")
def handle_filter_sort(task: str, context: dict[str, Any]) -> LocalResult:
    data = context.get("data", [])
    if not isinstance(data, list):
        return LocalResult(success=False, error="data必须是列表")

    result = list(data)

    if "去重" in task:
        if isinstance(data[0], dict) if data else False:
            seen = set()
            deduped = []
            key = context.get("dedup_key", "sku")
            for item in data:
                val = item.get(key, "")
                if val not in seen:
                    seen.add(val)
                    deduped.append(item)
            result = deduped
        else:
            result = list(dict.fromkeys(data))

    sort_key = context.get("sort_by")
    if sort_key and result and isinstance(result[0], dict):
        reverse = context.get("reverse", False)
        result.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse)

    return LocalResult(
        success=True,
        data={"result": result, "count": len(result), "original": len(data)},
        message=f"处理完成：{len(data)}→{len(result)}条"
    )


@register_handler(r"统计|求和|平均|占比")
def handle_statistics(task: str, context: dict[str, Any]) -> LocalResult:
    data = context.get("data", [])
    if not isinstance(data, list):
        return LocalResult(success=False, error="data必须是列表")

    field_name = context.get("field", "sales")
    values = [float(item.get(field_name, 0)) for item in data if isinstance(item, dict)]

    if "求和" in task or "sum" in task.lower():
        total = sum(values)
        return LocalResult(
            success=True,
            data={"field": field_name, "sum": total, "count": len(values)},
            message=f"{field_name}总和: {total:.2f}"
        )

    if "平均" in task or "avg" in task.lower():
        avg = sum(values) / len(values) if values else 0
        return LocalResult(
            success=True,
            data={"field": field_name, "average": round(avg, 2), "count": len(values)},
            message=f"{field_name}平均值: {avg:.2f}"
        )

    if "占比" in task:
        total = sum(values)
        pct = {item.get(field_name, 0): round(float(item.get(field_name, 0)) / total * 100, 2)
               for item in data if isinstance(item, dict)}
        return LocalResult(
            success=True,
            data={"field": field_name, "percentage": pct, "total": total},
            message=f"{field_name}占比计算完成"
        )

    return LocalResult(
        success=True,
        data={"count": len(data), "sum": sum(values), "average": sum(values)/len(values) if values else 0},
        message=f"统计：共{len(data)}条"
    )


@register_handler(r"匹配|查找|搜索")
def handle_pattern_match(task: str, context: dict[str, Any]) -> LocalResult:
    data = context.get("data", [])
    pattern = context.get("pattern", "")
    field_name = context.get("field", "title")

    if not pattern and context.get("keywords"):
        pattern = "|".join(context["keywords"])

    if not pattern:
        return LocalResult(success=False, error="未提供匹配pattern")

    regex = re.compile(pattern, re.IGNORECASE)
    matched = [
        item for item in data
        if isinstance(item, dict) and regex.search(str(item.get(field_name, "")))
    ]

    return LocalResult(
        success=True,
        data={"matched": matched, "count": len(matched), "total": len(data)},
        message=f"匹配到{len(matched)}/{len(data)}条"
    )


@register_handler(r"提醒|通知|预警|告警")
def handle_notification(task: str, context: dict[str, Any]) -> LocalResult:
    severity = context.get("severity", "info")
    message = context.get("message", task)
    items = context.get("items", [])

    severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "ℹ️")

    return LocalResult(
        success=True,
        data={
            "severity": severity,
            "title": f"{severity_icon} {severity.upper()} Alert",
            "body": message,
            "affected_count": len(items),
            "items": items[:10],
        },
        message=f"预警已生成 [{severity}]: {message}"
    )


@register_handler(r"表格|列表")
def handle_table_format(task: str, context: dict[str, Any]) -> LocalResult:
    data = context.get("data", [])
    columns = context.get("columns", [])

    if not data:
        return LocalResult(success=False, error="无数据")

    if not columns and isinstance(data[0], dict):
        columns = list(data[0].keys())

    lines = [
        "| " + " | ".join(str(c) for c in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in data[:50]:
        if isinstance(row, dict):
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")

    md_table = "\n".join(lines)

    return LocalResult(
        success=True,
        data={"markdown_table": md_table, "rows": len(data), "columns": columns},
        message=f"生成Markdown表格：{len(data)}行×{len(columns)}列"
    )


# ─── Tracing 工具 ─────────────────────────────────────────────────────────────
_tracing_module: Any = None


def _get_tracing():
    """返回 (TraceContext_cls, SpanType_cls, get_current_trace_fn) 或 None"""
    global _tracing_module
    if _tracing_module is None:
        try:
            from tracing.trace_context import TraceContext, SpanType, get_current_trace
            _tracing_module = (TraceContext, SpanType, get_current_trace)
        except ImportError:
            _tracing_module = None
    return _tracing_module


# ─── LocalExecutor（集成版）────────────────────────────────────────────────────
class LocalExecutor:
    """
    本地执行引擎（Tracing 集成版）

    每个 execute() 调用自动记录一个 span。
    """

    def __init__(self) -> None:
        self.name = "LocalExecutor"
        self.handlers = _LOCAL_HANDLERS

    def can_handle(self, task: str) -> bool:
        return any(re.search(p, task.lower()) for p in self.handlers)

    def execute(self, task: str, context: dict[str, Any]) -> LocalResult:
        """
        执行本地任务（自动记录 span）
        """
        tm = _get_tracing()
        span: Any = None

        if tm is not None:
            TraceContext_cls, SpanType_cls, get_current_trace_fn = tm
            ctx = get_current_trace_fn()
            if ctx is not None:
                scope = ctx.span(
                    "LocalExecutor.execute", SpanType_cls.EXECUTOR,
                    input_summary=task[:200],
                    metadata={"context_keys": list(context.keys())},
                )
                span = scope._span

        logger.info(f"[LocalExecutor] 处理任务: {task[:50]}")

        for pattern, handler in self.handlers.items():
            if re.search(pattern, task.lower()):
                try:
                    result = handler(task, context)
                    msg = f"[LocalExecutor] ✓ {handler.__name__}: {result.message}"

                    if span is not None:
                        span.finish(
                            output_summary=result.message,
                            error=result.error,
                        )

                    logger.info(msg)
                    return result

                except Exception as exc:
                    err_str = str(exc)
                    logger.error(f"[LocalExecutor] ✗ {handler.__name__}: {exc}")

                    if span is not None:
                        span.finish(error=err_str)

                    return LocalResult(success=False, error=err_str)

        # 无匹配处理器
        if context.get("data"):
            result = LocalResult(
                success=True,
                data={"data": context["data"], "count": len(context["data"])},
                message=f"数据已就绪，共{len(context['data'])}条"
            )
            if span is not None:
                span.finish(output_summary=result.message)
            return result

        result = LocalResult(success=False, error="无匹配本地处理器")
        if span is not None:
            span.finish(error=result.error)
        return result


EXECUTOR = LocalExecutor()
