"""
AuditTrail - 审计日志记录器
支持多存储后端（内存 / JSONL 文件 / 自定义 hook）。
提供：append、query、export、cleanup。
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .trace_context import SpanStatus, SpanType, TraceContext

logger = logging.getLogger("amazon_ops.tracing.audit")

# ─── 默认配置 ─────────────────────────────────────────────────────────────────
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data" / "traces"
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SQLITE_PATH = DEFAULT_DATA_DIR / "audit_trail.db"
DEFAULT_JSONL_PATH = DEFAULT_DATA_DIR / "audit_trail.jsonl.gz"


# ─── 存储后端 ─────────────────────────────────────────────────────────────────
class AuditBackend(ABC):
    """审计日志存储后端接口"""

    @abstractmethod
    def append(self, trace_ctx: TraceContext) -> None:
        """追加一条 trace"""
        raise NotImplementedError

    @abstractmethod
    def query(self, *,
               trace_id: str | None = None,
               span_id: str | None = None,
               agent_id: str | None = None,
               status: str | None = None,
               since: str | None = None,
               until: str | None = None,
               limit: int = 100) -> list[dict[str, Any]]:
        """查询审计记录"""
        raise NotImplementedError

    @abstractmethod
    def reverse_query(self, span_id: str) -> dict[str, Any] | None:
        """从 span_id 逆向追溯完整链路"""
        raise NotImplementedError

    def close(self) -> None:
        pass


# ─── SQLite 后端 ─────────────────────────────────────────────────────────────
class SQLiteBackend(AuditBackend):
    """
    SQLite + WAL 审计后端，支持高效查询。

    表结构：
    - traces: trace 维度的聚合记录
    - spans:  每个 span 一行，支持按 trace_id / agent_id / status 查询
    """

    def __init__(self, db_path: str | Path = DEFAULT_SQLITE_PATH) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id      TEXT PRIMARY KEY,
                root_name     TEXT NOT NULL,
                total_spans   INTEGER NOT NULL DEFAULT 0,
                total_ms      REAL,
                error_count   INTEGER NOT NULL DEFAULT 0,
                started_at    TEXT,
                finished_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS spans (
                span_id        TEXT PRIMARY KEY,
                trace_id       TEXT NOT NULL,
                parent_span_id TEXT,
                name           TEXT NOT NULL,
                type           TEXT NOT NULL,
                status         TEXT NOT NULL,
                input_summary  TEXT,
                output_summary TEXT,
                decision       TEXT,
                start_time     TEXT NOT NULL,
                end_time       TEXT,
                duration_ms    REAL,
                error          TEXT,
                agent_id       TEXT,
                tokens         INTEGER,
                metadata_json  TEXT,
                FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
            );

            CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
            CREATE INDEX IF NOT EXISTS idx_spans_agent ON spans(agent_id);
            CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);
            CREATE INDEX IF NOT EXISTS idx_spans_start ON spans(start_time);
        """)
        conn.commit()
        self._conn = conn
        logger.info(f"[AuditTrail] SQLite backend initialized: {self._db_path}")

    def _conn_get(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_db()
        assert self._conn is not None
        return self._conn

    def append(self, trace_ctx: TraceContext) -> None:
        with self._lock:
            conn = self._conn_get()
            now = _utc_now()
            summary = trace_ctx.summary()

            conn.execute("""
                INSERT OR REPLACE INTO traces
                    (trace_id, root_name, total_spans, total_ms, error_count, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trace_ctx.trace_id,
                trace_ctx.root_name,
                summary["total_spans"],
                summary["total_ms"],
                summary["error_count"],
                summary.get("spans", [{}])[0].get("start_time", now) if summary.get("spans") else now,
                now,
            ))

            for span in trace_ctx.spans:
                conn.execute("""
                    INSERT OR REPLACE INTO spans (
                        span_id, trace_id, parent_span_id, name, type, status,
                        input_summary, output_summary, decision,
                        start_time, end_time, duration_ms, error,
                        agent_id, tokens, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    span.span_id,
                    span.trace_id,
                    span.parent_span_id,
                    span.name,
                    span.type.value,
                    span.status.value,
                    span.input_summary,
                    span.output_summary,
                    span.decision,
                    span.start_time,
                    span.end_time,
                    span.duration_ms,
                    span.error,
                    span.metadata.get("agent_id"),
                    span.metadata.get("tokens"),
                    json.dumps(span.metadata, ensure_ascii=False),
                ))

            conn.commit()
            logger.debug(f"[AuditTrail] persisted trace_id={trace_ctx.trace_id}")

    def query(self, *,
              trace_id: str | None = None,
              span_id: str | None = None,
              agent_id: str | None = None,
              status: str | None = None,
              since: str | None = None,
              until: str | None = None,
              limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._conn_get()
            if span_id:
                cur = conn.execute(
                    "SELECT * FROM spans WHERE span_id = ? LIMIT 1",
                    (span_id,)
                )
                row = cur.fetchone()
                if row:
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, row))]
                return []

            where = []
            params: list[Any] = []
            if trace_id:
                where.append("trace_id = ?")
                params.append(trace_id)
            if agent_id:
                where.append("agent_id = ?")
                params.append(agent_id)
            if status:
                where.append("status = ?")
                params.append(status)
            if since:
                where.append("start_time >= ?")
                params.append(since)
            if until:
                where.append("start_time <= ?")
                params.append(until)

            clause = " AND ".join(where) if where else "1=1"
            cur = conn.execute(
                f"SELECT * FROM spans WHERE {clause} ORDER BY start_time DESC LIMIT ?",
                [*params, limit]
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def reverse_query(self, span_id: str) -> dict[str, Any] | None:
        """从任意 span 逆向追溯：向上找父链，向下找子链"""
        with self._lock:
            conn = self._conn_get()

            # 找到当前 span
            cur = conn.execute("SELECT * FROM spans WHERE span_id = ?", (span_id,))
            row = cur.fetchone()
            if not row:
                return None

            cols = [d[0] for d in cur.description]
            span = dict(zip(cols, row))
            trace_id = span["trace_id"]

            # 加载同 trace 所有 span
            all_cur = conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
                (trace_id,)
            )
            all_cols = [d[0] for d in all_cur.description]
            all_spans = [dict(zip(all_cols, r)) for r in all_cur.fetchall()]

            # 构建父子关系
            span_map: dict[str, dict] = {s["span_id"]: s for s in all_spans}

            # 向上追溯父链
            parent_chain = []
            current = span
            while current.get("parent_span_id"):
                pid = current["parent_span_id"]
                parent = span_map.get(pid)
                if not parent:
                    break
                parent_chain.append(parent)
                current = parent

            # 向下找子 span
            children = [s for s in all_spans if s.get("parent_span_id") == span_id]

            return {
                "target_span": span,
                "parent_chain": list(reversed(parent_chain)),
                "child_spans": children,
                "trace_summary": {
                    "trace_id": trace_id,
                    "total_spans": len(all_spans),
                    "spans": all_spans,
                },
            }

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """按 trace_id 获取完整链路"""
        with self._lock:
            conn = self._conn_get()
            cur = conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            trace = dict(zip(cols, row))

            spans_cur = conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
                (trace_id,)
            )
            span_cols = [d[0] for d in spans_cur.description]
            trace["spans"] = [dict(zip(span_cols, r)) for r in spans_cur.fetchall()]
            return trace

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


# ─── JSONL 备份后端（追加写入）─────────────────────────────────────────────────
class JSONLBackend(AuditBackend):
    """JSONL.gz 追加写入后端，用于归档备份"""

    def __init__(self, path: str | Path = DEFAULT_JSONL_PATH) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, trace_ctx: TraceContext) -> None:
        with self._lock:
            record = trace_ctx.summary()
            record["_written_at"] = _utc_now()
            line = json.dumps(record, ensure_ascii=False)
            with gzip.open(str(self._path), "at", encoding="utf-8") as f:
                f.write(line + "\n")

    def query(self, **kwargs: Any) -> list[dict[str, Any]]:
        # JSONL 后端只写不读（读由 SQLite 负责）
        return []

    def reverse_query(self, span_id: str) -> dict[str, Any] | None:
        return None


# ─── 聚合审计日志管理器 ───────────────────────────────────────────────────────
class AuditTrail:
    """
    统一审计日志管理器

    支持多后端同时写入（SQLite 查询 + JSONL 归档）。
    默认使用 SQLite（高性能查询）。

    用法：
    ```python
    from tracing import audit_log, start_trace

    # 启动 trace
    ctx = start_trace("优化PPC广告")

    # 执行操作（自动记录 span）
    ...

    # 自动 flush 到审计日志
    ctx.flush()
    ```
    """

    def __init__(
        self,
        sqlite_path: str | Path | None = None,
        jsonl_path: str | Path | None = None,
    ) -> None:
        self._sqlite = SQLiteBackend(sqlite_path or DEFAULT_SQLITE_PATH)
        self._jsonl = JSONLBackend(jsonl_path or DEFAULT_JSONL_PATH) if jsonl_path else None
        self._query_backend: AuditBackend = self._sqlite  # 默认查询后端

    def append_trace(self, trace_ctx: TraceContext) -> None:
        """追加一条 trace 到所有后端"""
        self._sqlite.append(trace_ctx)
        if self._jsonl:
            self._jsonl.append(trace_ctx)

    # ─── 查询 API ────────────────────────────────────────────────────────────
    def query(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._query_backend.query(**kwargs)

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        return self._sqlite.get_trace(trace_id)

    def reverse_query(self, span_id: str) -> dict[str, Any] | None:
        """
        从结果 → 原因：逆向追溯

        场景示例：
        - 用户看到某个 Agent 输出错误，从 span_id 反查父链（TaskRouter → ChiefOfStaff → 请求入口）
        - 运维发现某 trace 耗时异常高，逆向查看每层的耗时分解

        Returns:
            {
                "target_span": {...},    # 用户查询的 span
                "parent_chain": [...],   # 父链（根 → 父 → ... → 目标）
                "child_spans": [...],    # 目标 span 的子 span
                "trace_summary": {...},  # 全链路摘要
            }
        """
        return self._query_backend.reverse_query(span_id)

    def find_error_traces(self, since: str | None = None,
                          until: str | None = None,
                          limit: int = 50) -> list[dict[str, Any]]:
        """查询所有包含错误的 trace"""
        spans = self._sqlite.query(status="error", since=since, until=until, limit=limit)
        trace_ids = list(dict.fromkeys(s["trace_id"] for s in spans))
        return [self._sqlite.get_trace(tid) for tid in trace_ids if tid]

    def find_slow_spans(self, threshold_ms: float = 1000,
                        since: str | None = None) -> list[dict[str, Any]]:
        """查找耗时超过 threshold_ms 的 span"""
        with self._sqlite._lock:
            conn = self._sqlite._conn_get()
            cur = conn.execute(
                "SELECT * FROM spans WHERE duration_ms >= ? AND start_time >= ? "
                "ORDER BY duration_ms DESC LIMIT 200",
                (threshold_ms, since or "1970-01-01")
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def recent_traces(self, limit: int = 20) -> list[dict[str, Any]]:
        """最近 N 条 trace 摘要"""
        traces = self._sqlite.query(limit=limit * 3)
        seen = set()
        result = []
        for s in traces:
            if s["trace_id"] not in seen:
                seen.add(s["trace_id"])
                t = self._sqlite.get_trace(s["trace_id"])
                if t:
                    result.append(t)
            if len(result) >= limit:
                break
        return result

    def stats(self) -> dict[str, Any]:
        """审计日志统计"""
        with self._sqlite._lock:
            conn = self._sqlite._conn_get()
            trace_count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
            span_count = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
            error_count = conn.execute(
                "SELECT COUNT(*) FROM spans WHERE status = 'error'"
            ).fetchone()[0]
            total_ms = conn.execute(
                "SELECT SUM(total_ms) FROM traces"
            ).fetchone()[0] or 0

            # 各类型 span 统计
            type_cur = conn.execute(
                "SELECT type, COUNT(*), AVG(duration_ms) FROM spans GROUP BY type"
            )
            type_stats = {row[0]: {"count": row[1], "avg_ms": round(row[2] or 0, 2)}
                          for row in type_cur.fetchall()}

            return {
                "total_traces": trace_count,
                "total_spans": span_count,
                "error_spans": error_count,
                "error_rate": round(error_count / span_count * 100, 2) if span_count else 0,
                "total_ms": round(total_ms, 2),
                "type_breakdown": type_stats,
                "sqlite_path": str(self._sqlite._db_path),
                "jsonl_path": str(self._jsonl._path) if self._jsonl else None,
            }

    def cleanup(self, keep_days: int = 7) -> int:
        """清理 N 天前的记录，返回删除行数"""
        cutoff = _days_ago(keep_days)
        with self._sqlite._lock:
            conn = self._sqlite._conn_get()
            # 先删 spans
            cur = conn.execute(
                "DELETE FROM spans WHERE start_time < ?", (cutoff,)
            )
            deleted_spans = cur.rowcount
            # 再删孤立的 traces
            cur2 = conn.execute(
                "DELETE FROM traces WHERE finished_at < ? AND trace_id NOT IN "
                "(SELECT DISTINCT trace_id FROM spans)",
                (cutoff,)
            )
            deleted_traces = cur2.rowcount
            conn.commit()
            logger.info(
                f"[AuditTrail] cleanup: deleted {deleted_spans} spans, "
                f"{deleted_traces} traces (before {cutoff})"
            )
            return deleted_spans + deleted_traces

    def close(self) -> None:
        self._sqlite.close()


# ─── 全局单例 ─────────────────────────────────────────────────────────────────
audit_log = AuditTrail()


# ─── 工具函数 ─────────────────────────────────────────────────────────────────
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _days_ago(n: int) -> str:
    from datetime import timedelta
    dt = datetime.now(timezone.utc) - timedelta(days=n)
    return dt.isoformat().replace("+00:00", "Z")
