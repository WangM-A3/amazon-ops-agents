"""
trace_monitor.py - 全链路追溯系统自动化监控脚本

功能：
1. 定期检查错误率，超过阈值自动告警
2. 自动分析慢 trace，输出根因摘要
3. 生成健康报告（JSON + Markdown）

使用方式：
    python scripts/trace_monitor.py                    # 默认检查（标准输出）
    python scripts/trace_monitor.py --output report.json   # 输出 JSON 报告
    python scripts/trace_monitor.py --continuous --interval 60  # 每 60 秒持续监控
    python scripts/trace_monitor.py --alert-only         # 仅输出告警
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ─── 路径设置 ─────────────────────────────────────────────────────────────────
_SRC = Path(__file__).parent.parent
sys.path.insert(0, str(_SRC))

# ─── 日志配置 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("trace_monitor")


# ─── 健康等级枚举 ─────────────────────────────────────────────────────────────
class HealthLevel(Enum):
    HEALTHY = "✅ HEALTHY"      # 健康
    WARNING = "⚠️  WARNING"      # 警告
    CRITICAL = "🚨 CRITICAL"    # 严重
    UNKNOWN = "❓ UNKNOWN"       # 未知


# ─── 告警规则 ───────────────────────────────────────────────────────────────
@dataclass
class AlertThresholds:
    error_rate_pct: float = 5.0       # 错误率超过此值告警（%）
    slow_trace_ms: float = 5000.0     # 超过此耗时的 trace 为慢 trace（ms）
    slow_span_ms: float = 2000.0      # 超过此耗时的 span 为慢 span（ms）
    max_recent_errors: int = 20       # 最近错误超过此数量告警
    critical_error_rate: float = 15.0 # 超过此错误率直接标记 CRITICAL（%）


@dataclass
class Alert:
    level: HealthLevel
    category: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None


# ─── 健康报告 ────────────────────────────────────────────────────────────────
@dataclass
class HealthReport:
    generated_at: str
    period_minutes: int
    health: HealthLevel
    alerts: list[dict[str, Any]]
    stats: dict[str, Any]
    slow_traces: list[dict[str, Any]]
    recent_errors: list[dict[str, Any]]
    agent_health: dict[str, dict[str, Any]]
    summary: str


# ─── 核心监控器 ─────────────────────────────────────────────────────────────
class TraceMonitor:
    """
    全链路追溯系统监控器

    功能：
    - 检查审计日志健康状态
    - 分析慢 trace 并输出根因
    - 按 Agent 统计健康度
    - 生成可配置的告警
    """

    def __init__(
        self,
        thresholds: AlertThresholds | None = None,
        since_minutes: int = 60,
    ) -> None:
        self.thresholds = thresholds or AlertThresholds()
        self.since_minutes = since_minutes
        self._tq = None
        self._audit = None
        self._since_iso: str | None = None

    # ─── 懒加载依赖 ──────────────────────────────────────────────────────────
    def _load_dependencies(self) -> None:
        if self._tq is not None:
            return
        try:
            from tracing import audit_log
            from tracing.trace_query import TraceQuery

            self._audit = audit_log
            self._tq = TraceQuery(backend=audit_log)

            # 计算时间窗口
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.since_minutes)
            self._since_iso = cutoff.isoformat().replace("+00:00", "Z")
            logger.info(f"[TraceMonitor] 时间窗口: 最近 {self.since_minutes} 分钟")
        except ImportError as exc:
            logger.error(f"[TraceMonitor] 无法导入 tracing 模块: {exc}")
            raise RuntimeError("Tracing 模块未安装或路径配置错误") from exc

    # ─── 主检查入口 ──────────────────────────────────────────────────────────
    def check(self) -> tuple[HealthLevel, list[Alert], HealthReport]:
        """
        执行完整健康检查

        Returns:
            (health_level, alerts, report)
        """
        self._load_dependencies()

        logger.info("[TraceMonitor] 开始健康检查...")
        alerts: list[Alert] = []

        # 1. 审计日志统计
        stats = self._check_stats()
        logger.info(f"[TraceMonitor] 统计: traces={stats['total_traces']}, "
                    f"spans={stats['total_spans']}, error_rate={stats['error_rate']}%")

        # 2. 错误率告警
        alerts.extend(self._check_error_rate(stats))

        # 3. 慢 trace 分析
        slow_traces = self._check_slow_traces()

        # 4. 慢 span 分析
        alerts.extend(self._check_slow_spans())

        # 5. 最近错误 trace
        recent_errors = self._check_recent_errors()

        # 6. Agent 健康度
        agent_health = self._check_agent_health(recent_errors)

        # 7. 告警汇总
        health = self._compute_health_level(alerts)

        report = HealthReport(
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            period_minutes=self.since_minutes,
            health=health,
            alerts=[self._alert_to_dict(a) for a in alerts],
            stats=stats,
            slow_traces=slow_traces,
            recent_errors=recent_errors,
            agent_health=agent_health,
            summary=self._build_summary(health, alerts, stats),
        )

        return health, alerts, report

    # ─── 统计检查 ────────────────────────────────────────────────────────────
    def _check_stats(self) -> dict[str, Any]:
        stats = self._audit.stats()

        # 按时间窗口过滤（从 spans 表查）
        if self._since_iso:
            spans = self._audit.query(
                since=self._since_iso,
                limit=10000,
            )
            traces = self._audit.recent_traces(limit=5000)
            # 简单过滤：在时间窗口内的
            total_spans = len(spans)
            error_spans = sum(1 for s in spans if s.get("status") == "error")
            stats = {
                **stats,
                "total_spans": total_spans,
                "error_spans": error_spans,
                "error_rate": round(error_spans / total_spans * 100, 2)
                    if total_spans else 0,
            }

        return stats

    # ─── 错误率告警 ──────────────────────────────────────────────────────────
    def _check_error_rate(self, stats: dict[str, Any]) -> list[Alert]:
        alerts: list[Alert] = []
        rate = stats.get("error_rate", 0)

        if rate >= self.thresholds.critical_error_rate:
            alerts.append(Alert(
                level=HealthLevel.CRITICAL,
                category="error_rate",
                message=f"错误率严重超标: {rate:.2f}% (阈值: {self.thresholds.critical_error_rate}%)",
                detail={"error_rate": rate, "threshold": self.thresholds.critical_error_rate},
            ))
        elif rate >= self.thresholds.error_rate_pct:
            alerts.append(Alert(
                level=HealthLevel.WARNING,
                category="error_rate",
                message=f"错误率偏高: {rate:.2f}% (阈值: {self.thresholds.error_rate_pct}%)",
                detail={"error_rate": rate, "threshold": self.thresholds.error_rate_pct},
            ))

        return alerts

    # ─── 慢 trace 检查 ───────────────────────────────────────────────────────
    def _check_slow_traces(self) -> list[dict[str, Any]]:
        slow_traces: list[dict[str, Any]] = []
        threshold = self.thresholds.slow_trace_ms

        # 使用 TraceQuery 的 slow_traces
        if self._tq is None:
            return slow_traces

        results = self._tq.slow_traces(threshold_ms=threshold, limit=20)
        for r in results:
            slow_traces.append({
                "trace_id": r.trace_id,
                "total_ms": r.total_ms,
                "total_spans": r.total_spans,
                "error_count": r.error_count,
                "root_span": r.root_span,
            })

        if slow_traces:
            logger.warning(f"[TraceMonitor] 发现 {len(slow_traces)} 条慢 trace (>{threshold}ms)")

        return slow_traces

    # ─── 慢 span 检查 ────────────────────────────────────────────────────────
    def _check_slow_spans(self) -> list[Alert]:
        alerts: list[Alert] = []
        threshold = self.thresholds.slow_span_ms

        slow_spans = self._audit.find_slow_spans(
            threshold_ms=threshold,
            since=self._since_iso,
        )

        if not slow_spans:
            return alerts

        # 按 trace_id 分组，取最慢的
        by_trace: dict[str, list] = {}
        for s in slow_spans:
            tid = s["trace_id"]
            by_trace.setdefault(tid, []).append(s)

        # 只报告每个 trace 中最慢的 span
        for tid, spans in sorted(by_trace.items(), key=lambda x: -max(
            s.get("duration_ms", 0) for s in x[1]
        ))[:5]:
            slowest = max(spans, key=lambda s: s.get("duration_ms", 0))
            alerts.append(Alert(
                level=HealthLevel.WARNING,
                category="slow_span",
                message=(f"慢 span: {slowest['name']} "
                         f"耗时 {slowest['duration_ms']:.0f}ms "
                         f"(trace={tid[:16]})"),
                detail={
                    "trace_id": tid,
                    "span_id": slowest["span_id"],
                    "name": slowest["name"],
                    "duration_ms": slowest["duration_ms"],
                    "type": slowest.get("type"),
                    "agent_id": slowest.get("agent_id"),
                },
                trace_id=tid,
            ))

        return alerts

    # ─── 最近错误检查 ────────────────────────────────────────────────────────
    def _check_recent_errors(self) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []

        error_traces = self._audit.find_error_traces(
            since=self._since_iso,
            limit=50,
        )

        for t in error_traces:
            error_spans = [s for s in t.get("spans", []) if s.get("status") == "error"]
            errors.append({
                "trace_id": t.get("trace_id"),
                "total_ms": t.get("total_ms"),
                "error_count": t.get("error_count"),
                "first_error": error_spans[0] if error_spans else None,
            })

        if len(errors) >= self.thresholds.max_recent_errors:
            logger.warning(
                f"[TraceMonitor] 最近错误数量过多: {len(errors)} "
                f"(阈值: {self.thresholds.max_recent_errors})"
            )

        return errors

    # ─── Agent 健康度 ────────────────────────────────────────────────────────
    def _check_agent_health(self, error_traces: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        agent_stats: dict[str, dict[str, Any]] = {}

        for t in error_traces:
            for span in t.get("spans", []):
                if span.get("status") != "error":
                    continue
                agent_id = span.get("agent_id") or span.get("name", "").split(".")[-1]
                if agent_id not in agent_stats:
                    agent_stats[agent_id] = {"error_count": 0, "error_traces": [], "spans": []}
                agent_stats[agent_id]["error_count"] += 1
                agent_stats[agent_id]["error_traces"].append(t.get("trace_id"))
                agent_stats[agent_id]["spans"].append({
                    "trace_id": t.get("trace_id"),
                    "span_id": span.get("span_id"),
                    "name": span.get("name"),
                    "error": span.get("error"),
                    "duration_ms": span.get("duration_ms"),
                })

        return agent_stats

    # ─── 汇总健康等级 ───────────────────────────────────────────────────────
    def _compute_health_level(self, alerts: list[Alert]) -> HealthLevel:
        if not alerts:
            return HealthLevel.HEALTHY

        levels = [a.level for a in alerts]
        if HealthLevel.CRITICAL in levels:
            return HealthLevel.CRITICAL
        if HealthLevel.WARNING in levels:
            return HealthLevel.WARNING
        return HealthLevel.UNKNOWN

    # ─── 辅助方法 ───────────────────────────────────────────────────────────
    @staticmethod
    def _alert_to_dict(alert: Alert) -> dict[str, Any]:
        return {
            "level": alert.level.value,
            "category": alert.category,
            "message": alert.message,
            "detail": alert.detail,
            "trace_id": alert.trace_id,
        }

    @staticmethod
    def _build_summary(
        health: HealthLevel,
        alerts: list[Alert],
        stats: dict[str, Any],
    ) -> str:
        parts = [
            f"健康等级: {health.value}",
            f"总 traces: {stats.get('total_traces', 0)}",
            f"总 spans: {stats.get('total_spans', 0)}",
            f"错误率: {stats.get('error_rate', 0):.2f}%",
            f"告警数量: {len(alerts)}",
        ]
        if alerts:
            critical = sum(1 for a in alerts if a.level == HealthLevel.CRITICAL)
            warning = sum(1 for a in alerts if a.level == HealthLevel.WARNING)
            if critical:
                parts.append(f"严重告警: {critical}")
            if warning:
                parts.append(f"警告告警: {warning}")
        return " | ".join(parts)


# ─── 报告渲染 ───────────────────────────────────────────────────────────────
class ReportRenderer:
    """将 HealthReport 渲染为不同格式"""

    @staticmethod
    def render_text(report: HealthReport) -> str:
        lines = [
            "=" * 60,
            f"  全链路追溯健康报告",
            f"  生成时间: {report.generated_at}",
            f"  统计周期: 最近 {report.period_minutes} 分钟",
            "=" * 60,
            "",
            f"  健康等级: {report.health.value}",
            f"  告警数量: {len(report.alerts)}",
            "",
        ]

        if report.alerts:
            lines.append("  ── 告警详情 ──")
            for alert in report.alerts:
                lines.append(f"  [{alert['level']}] {alert['message']}")
                if alert.get("trace_id"):
                    lines.append(f"    trace_id: {alert['trace_id'][:16]}")
            lines.append("")

        lines.extend([
            "  ── 统计摘要 ──",
            f"  总 traces:    {report.stats.get('total_traces', 0)}",
            f"  总 spans:    {report.stats.get('total_spans', 0)}",
            f"  错误 spans:  {report.stats.get('error_spans', 0)}",
            f"  错误率:      {report.stats.get('error_rate', 0):.2f}%",
            f"  总耗时:      {report.stats.get('total_ms', 0):.0f}ms",
            "",
        ])

        if report.agent_health:
            lines.append("  ── Agent 健康度 ──")
            for agent, info in sorted(
                report.agent_health.items(),
                key=lambda x: -x[1]["error_count"]
            )[:10]:
                lines.append(f"  - {agent:<20} 错误: {info['error_count']}")
            lines.append("")

        if report.slow_traces:
            lines.append("  ── 慢 trace TOP 5 ──")
            for t in report.slow_traces[:5]:
                lines.append(
                    f"  trace={t['trace_id'][:16]} | "
                    f"{t['total_ms']:.0f}ms | spans={t['total_spans']} | "
                    f"errors={t['error_count']}"
                )
            lines.append("")

        if report.recent_errors:
            lines.append("  ── 最近错误 trace ──")
            for e in report.recent_errors[:5]:
                err = e.get("first_error") or {}
                lines.append(
                    f"  trace={e['trace_id'][:16]} | "
                    f"{err.get('name', '?')} | "
                    f"error={err.get('error', 'N/A')[:40]}"
                )
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def render_json(report: HealthReport) -> str:
        return json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def render_markdown(report: HealthReport) -> str:
        lines = [
            f"# 全链路追溯健康报告",
            "",
            f"**生成时间**: {report.generated_at}",
            f"**统计周期**: 最近 {report.period_minutes} 分钟",
            f"**健康等级**: {report.health.value}",
            "",
        ]

        if report.alerts:
            lines.append("## 告警详情\n")
            for alert in report.alerts:
                lines.append(f"- **{alert['level']}** [{alert['category']}] {alert['message']}")
                if alert.get("trace_id"):
                    lines.append(f"  - `trace_id`: `{alert['trace_id']}`")
                if alert.get("detail"):
                    for k, v in alert["detail"].items():
                        lines.append(f"  - {k}: `{v}`")
            lines.append("")

        lines.extend([
            "## 统计摘要\n",
            f"| 指标 | 值 |",
            f"|------|----|",
            f"| 总 traces | {report.stats.get('total_traces', 0)} |",
            f"| 总 spans | {report.stats.get('total_spans', 0)} |",
            f"| 错误 spans | {report.stats.get('error_spans', 0)} |",
            f"| 错误率 | {report.stats.get('error_rate', 0):.2f}% |",
            f"| 总耗时 | {report.stats.get('total_ms', 0):.0f}ms |",
            "",
        ])

        if report.agent_health:
            lines.append("## Agent 健康度\n")
            lines.append("| Agent | 错误数 | trace_id |")
            lines.append("|-------|--------|----------|")
            for agent, info in sorted(
                report.agent_health.items(),
                key=lambda x: -x[1]["error_count"]
            )[:10]:
                tids = ", ".join(f"`{t[:16]}`" for t in info["error_traces"][:3])
                lines.append(f"| `{agent}` | {info['error_count']} | {tids} |")
            lines.append("")

        if report.slow_traces:
            lines.append("## 慢 trace\n")
            lines.append("| trace_id | 耗时 | spans | 错误 |")
            lines.append("|----------|------|-------|------|")
            for t in report.slow_traces[:10]:
                lines.append(
                    f"| `{t['trace_id'][:16]}` | {t['total_ms']:.0f}ms | "
                    f"{t['total_spans']} | {t['error_count']} |"
                )
            lines.append("")

        return "\n".join(lines)


# ─── CLI 入口 ───────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="全链路追溯系统监控脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="输出文件路径（JSON 格式）",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="输出格式（默认: text）",
    )
    parser.add_argument(
        "--continuous", "-c",
        action="store_true",
        help="持续监控模式",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="持续监控间隔（秒，默认: 60）",
    )
    parser.add_argument(
        "--alert-only",
        action="store_true",
        help="仅输出告警（忽略健康状态）",
    )
    parser.add_argument(
        "--since", "-s",
        type=int,
        default=60,
        help="统计时间窗口（分钟，默认: 60）",
    )
    parser.add_argument(
        "--error-rate-threshold",
        type=float,
        default=5.0,
        help="错误率告警阈值（%%，默认: 5.0）",
    )
    parser.add_argument(
        "--slow-trace-ms",
        type=float,
        default=5000.0,
        help="慢 trace 阈值（ms，默认: 5000）",
    )
    parser.add_argument(
        "--slow-span-ms",
        type=float,
        default=2000.0,
        help="慢 span 阈值（ms，默认: 2000）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    thresholds = AlertThresholds(
        error_rate_pct=args.error_rate_threshold,
        slow_trace_ms=args.slow_trace_ms,
        slow_span_ms=args.slow_span_ms,
    )

    monitor = TraceMonitor(thresholds=thresholds, since_minutes=args.since)
    renderer = ReportRenderer()

    def run_once() -> HealthReport:
        health, alerts, report = monitor.check()
        return report

    if not args.continuous:
        # 单次检查
        report = run_once()

        if args.alert_only:
            # 仅告警模式
            if not report.alerts:
                print("✅ 未发现告警")
            else:
                for alert in report.alerts:
                    print(f"{alert['level']} [{alert['category']}] {alert['message']}")
                    if alert.get("trace_id"):
                        print(f"  trace_id: {alert['trace_id']}")
        else:
            # 完整报告
            if args.format == "text":
                output = renderer.render_text(report)
            elif args.format == "json":
                output = renderer.render_json(report)
            else:
                output = renderer.render_markdown(report)

            print(output)

        # 写文件
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                if args.format == "json":
                    f.write(renderer.render_json(report))
                else:
                    f.write(renderer.render_markdown(report))
            logger.info(f"[TraceMonitor] 报告已写入: {args.output}")

        # 返回码反映健康状态
        if report.health == HealthLevel.CRITICAL:
            sys.exit(2)
        elif report.health == HealthLevel.WARNING:
            sys.exit(1)
        sys.exit(0)

    else:
        # 持续监控
        print(f"[TraceMonitor] 启动持续监控，间隔 {args.interval} 秒...")
        try:
            while True:
                report = run_once()
                timestamp = datetime.now().strftime("%H:%M:%S")
                marker = "●" if report.health == HealthLevel.HEALTHY else (
                    "⚠" if report.health == HealthLevel.WARNING else "🚨"
                )
                print(f"[{timestamp}] {marker} {report.health.value} | "
                      f"errors={len(report.alerts)} | "
                      f"traces={report.stats.get('total_traces', 0)} | "
                      f"error_rate={report.stats.get('error_rate', 0):.2f}%")

                if not args.alert_only and report.slow_traces:
                    for t in report.slow_traces[:3]:
                        print(f"  └─ slow: trace={t['trace_id'][:16]} "
                              f"{t['total_ms']:.0f}ms")

                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[TraceMonitor] 监控已停止")
            sys.exit(0)


if __name__ == "__main__":
    main()
