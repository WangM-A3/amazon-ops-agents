"""
本地执行引擎 - LocalExecutor
处理所有 LOCAL 级别任务，零Token消耗
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("amazon_ops.local_executor")


# ─── 本地任务处理器注册表 ──────────────────────────────────────────────────────
_LOCAL_HANDLERS: dict[str, callable] = {}


def register_handler(pattern: str):
    """装饰器：注册本地任务处理器"""
    def deco(fn: callable) -> callable:
        _LOCAL_HANDLERS[pattern] = fn
        return fn
    return deco


# ─── 结果类型 ─────────────────────────────────────────────────────────────────
@dataclass
class LocalResult:
    """本地执行结果"""
    success: bool
    engine: str = "local"
    tokens: int = 0            # 恒为0
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ─── 格式化工具 ────────────────────────────────────────────────────────────────
@register_handler(r"提取.*数据|导出.*报表")
def handle_data_extract(task: str, context: dict[str, Any]) -> LocalResult:
    """数据提取：支持JSON/CSV格式转换"""
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
    """格式转换：JSON ↔ CSV"""
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
    """排序筛选：支持多字段排序、条件过滤、去重"""
    data = context.get("data", [])
    if not isinstance(data, list):
        return LocalResult(success=False, error="data必须是列表")

    result = list(data)

    # 去重
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

    # 排序
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
    """统计计算：求和、平均、占比、计数"""
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

    # 默认计数
    return LocalResult(
        success=True,
        data={"count": len(data), "sum": sum(values), "average": sum(values)/len(values) if values else 0},
        message=f"统计：共{len(data)}条"
    )


@register_handler(r"匹配|查找|搜索")
def handle_pattern_match(task: str, context: dict[str, Any]) -> LocalResult:
    """规则匹配：关键词匹配、正则过滤"""
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
    """通知预警：生成告警消息"""
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
            "items": items[:10],  # 最多10条详情
        },
        message=f"预警已生成 [{severity}]: {message}"
    )


@register_handler(r"表格|列表")
def handle_table_format(task: str, context: dict[str, Any]) -> LocalResult:
    """表格格式化：Markdown表格输出"""
    data = context.get("data", [])
    columns = context.get("columns", [])

    if not data:
        return LocalResult(success=False, error="无数据")

    if not columns and isinstance(data[0], dict):
        columns = list(data[0].keys())

    # 构建Markdown表格
    lines = [
        "| " + " | ".join(str(c) for c in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in data[:50]:  # 最多50行
        if isinstance(row, dict):
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")

    md_table = "\n".join(lines)

    return LocalResult(
        success=True,
        data={"markdown_table": md_table, "rows": len(data), "columns": columns},
        message=f"生成Markdown表格：{len(data)}行×{len(columns)}列"
    )


# ─── LocalExecutor 主类 ────────────────────────────────────────────────────────
class LocalExecutor:
    """
    本地执行引擎

    特点：
    - 零Token消耗
    - 毫秒级响应
    - 支持数据处理全链路（提取/转换/统计/格式）
    """

    def __init__(self) -> None:
        self.name = "LocalExecutor"
        self.handlers = _LOCAL_HANDLERS

    def can_handle(self, task: str) -> bool:
        """判断任务是否可本地执行"""
        return any(
            re.search(p, task.lower())
            for p in self.handlers
        )

    def execute(self, task: str, context: dict[str, Any]) -> LocalResult:
        """
        执行本地任务

        Args:
            task: 任务描述
            context: 上下文数据（含data、format等）

        Returns:
            LocalResult：标准化结果
        """
        logger.info(f"[LocalExecutor] 处理任务: {task[:50]}")

        for pattern, handler in self.handlers.items():
            if re.search(pattern, task.lower()):
                try:
                    result = handler(task, context)
                    logger.info(f"[LocalExecutor] ✓ {handler.__name__}: {result.message}")
                    return result
                except Exception as exc:
                    logger.error(f"[LocalExecutor] ✗ {handler.__name__}: {exc}")
                    return LocalResult(success=False, error=str(exc))

        # 无匹配处理器：尝试通用数据提取
        if context.get("data"):
            return LocalResult(
                success=True,
                data={"data": context["data"], "count": len(context["data"])},
                message=f"数据已就绪，共{len(context['data'])}条"
            )

        return LocalResult(success=False, error="无匹配本地处理器")


# 全局单例
EXECUTOR = LocalExecutor()
