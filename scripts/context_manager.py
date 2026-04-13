"""
Context Manager - 多层上下文管理系统
参考 Multi-Agent Orchestration Patterns 的 Tiered Context Management
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

# ─── 配置 ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(exist_ok=True)
SESSION_DB = DATA_DIR / "sessions.jsonl"
MEMORY_DB = DATA_DIR / "memory.jsonl"


@dataclass
class WorkingContext:
    """Hot Context - 当前任务状态（内存）"""
    session_id: str
    task: str
    routed_agents: list[str]
    results: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionRecord:
    """Warm Context - 会话历史（数据库）"""
    session_id: str
    user_id: str
    tasks: list[dict[str, Any]]
    created_at: str
    updated_at: str
    total_tokens: int = 0
    agent_count: int = 0


@dataclass
class MemoryRecord:
    """Cold Context - 长期记忆（向量DB/JSONL）"""
    event_type: str  # product_research | listing_optimized | ad_optimized
    content: str
    tags: list[str]
    embedding: Optional[list[float]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─── 简单嵌入（无需外部服务）─────────────────────────────────────────────────
def simple_embed(text: str) -> list[float]:
    """简单的词频嵌入（用于记忆检索）"""
    import hashlib
    words = set(text.lower().split())
    # 固定256维向量
    vec = [0.0] * 256
    for i, word in enumerate(words):
        idx = int(hashlib.md5(word.encode()).hexdigest()[:4], 16) % 256
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def cosine_sim(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ─── ContextManager ────────────────────────────────────────────────────────────
class ContextManager:
    """
    三层上下文管理器

    Hot (Working): 当前任务 → 内存字典
    Warm (Session): 会话历史 → DATA_DIR/sessions.jsonl
    Cold (Memory): 长期记忆 → DATA_DIR/memory.jsonl
    """

    def __init__(self) -> None:
        self._working: dict[str, WorkingContext] = {}
        self._session_db = SESSION_DB
        self._memory_db = MEMORY_DB
        self._memory_db.parent.mkdir(exist_ok=True)

    # ─── Hot: 当前任务上下文 ────────────────────────────────────────────────
    def start_task(self, session_id: str, task: str, agents: list[str]) -> WorkingContext:
        ctx = WorkingContext(
            session_id=session_id,
            task=task,
            routed_agents=agents,
            results={},
        )
        self._working[session_id] = ctx
        return ctx

    def update_task(self, session_id: str, results: dict[str, Any]) -> None:
        if session_id in self._working:
            self._working[session_id].results = results
            self._working[session_id].updated_at = datetime.now(timezone.utc).isoformat()

    def get_working(self, session_id: str) -> Optional[WorkingContext]:
        return self._working.get(session_id)

    def close_task(self, session_id: str) -> Optional[WorkingContext]:
        ctx = self._working.pop(session_id, None)
        if ctx:
            self._persist_session(ctx)
            self._update_memory_from_result(ctx)
        return ctx

    # ─── Warm: 会话历史 ────────────────────────────────────────────────────────
    def _persist_session(self, ctx: WorkingContext) -> None:
        record = {
            "session_id": ctx.session_id,
            "task": ctx.task,
            "routed_agents": ctx.routed_agents,
            "results_keys": list(ctx.results.keys()),
            "total_tokens": sum(r.get("tokens", 0) for r in ctx.results.values()),
            "created_at": ctx.created_at,
            "updated_at": ctx.updated_at,
        }
        with open(self._session_db, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_session_history(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self._session_db.exists():
            return []
        records = []
        with open(self._session_db, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records[-limit:]

    # ─── Cold: 长期记忆 ──────────────────────────────────────────────────────
    def _update_memory_from_result(self, ctx: WorkingContext) -> None:
        """从执行结果中提取值得记忆的信息"""
        for agent_id, result in ctx.results.items():
            content = self._extract_insight(agent_id, result)
            if content:
                record = MemoryRecord(
                    event_type=agent_id,
                    content=content,
                    tags=self._infer_tags(agent_id, content),
                    embedding=simple_embed(content),
                )
                self._append_memory(record)

    def _extract_insight(self, agent_id: str, result: dict[str, Any]) -> str | None:
        """从结果中提取洞察"""
        kpis = result.get("kpis", {})
        result_data = result.get("result", {})
        if isinstance(kpis, dict):
            return f"[{agent_id}] " + " | ".join(f"{k}={v}" for k, v in kpis.items())
        if isinstance(result_data, dict) and result_data:
            first_val = list(result_data.values())[0]
            if isinstance(first_val, dict):
                return f"[{agent_id}] {first_val.get('name', str(first_val)[:100])}"
        return None

    def _infer_tags(self, agent_id: str, content: str) -> list[str]:
        tags = [agent_id]
        content_lower = content.lower()
        if "acos" in content_lower: tags.append("acos")
        if "listing" in content_lower: tags.append("listing")
        if "库存" in content_lower or "inventory" in content_lower: tags.append("库存")
        if "review" in content_lower or "评论" in content_lower: tags.append("评论")
        if "利润" in content_lower or "margin" in content_lower: tags.append("利润")
        return tags[:5]

    def _append_memory(self, record: MemoryRecord) -> None:
        with open(self._memory_db, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def recall(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """基于内容的记忆检索"""
        if not self._memory_db.exists():
            return []
        query_vec = simple_embed(query)
        scores: list[tuple[float, dict[str, Any]]] = []
        with open(self._memory_db, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    emb = rec.get("embedding", [])
                    if emb:
                        score = cosine_sim(query_vec, emb)
                        scores.append((score, rec))
                except Exception:
                    continue
        scores.sort(key=lambda x: x[0], reverse=True)
        return [rec for _, rec in scores[:top_k]]

    def get_memory_stats(self) -> dict[str, Any]:
        sessions = self.get_session_history(limit=9999)
        memories = []
        if self._memory_db.exists():
            with open(self._memory_db, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            memories.append(json.loads(line))
                        except Exception:
                            continue
        return {
            "total_sessions": len(sessions),
            "total_memories": len(memories),
            "memory_by_type": self._count_by(memories, "event_type"),
            "recent_insights": [m["content"][:100] for m in memories[-5:]],
        }

    @staticmethod
    def _count_by(items: list[dict], key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            val = item.get(key, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts


# 全局单例
CTX = ContextManager()
