"""
memory/experience_store.py — 经验记忆闭环存储与检索
=====================================================
SQLite 落地的「Agent 经验库」：

- 经验（experiences）：一条经验 = {agent_id, title, content(修正策略), keywords(触发词), 命中/正负反馈统计}
- 检索（retrieve_experiences）：按 agent + 任务关键词匹配，烂经验（负反馈占比高）自动过滤
- 打分（apply_rating）：用户给命中经验打 1-5 分，连续低分自动停用（active=0）
- 全部基于标准库 sqlite3，无外部依赖；测试可用 AMAZON_OPS_DATA_DIR 隔离

数据目录默认 data/memory/experience.db（卖家本地运行产物，不入库/不打包）。
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("amazon_ops.memory")

DB_FILE = "experience.db"

# 质量门：负反馈 >= NEG_SAMPLE 且 成功率 < LOW_RATE 时视为烂经验，不再注入
NEG_SAMPLE_BEFORE_GATE = 2
LOW_SUCCESS_RATE = 0.5
# 检索返回上限
RETRIEVE_LIMIT = 3


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _default_data_dir() -> str:
    """实例化时读取，保证测试/多环境可用 env 隔离（同 data/store.py 模式）"""
    return os.getenv("AMAZON_OPS_DATA_DIR", "data")


def _default_db_path() -> Path:
    return Path(_default_data_dir()) / "memory" / DB_FILE


def _parse_keywords(raw: Any) -> list[str]:
    """keywords 存 JSON 数组字符串；兼容直接传 list"""
    if isinstance(raw, list):
        return [str(k).strip() for k in raw if str(k).strip()]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(k).strip() for k in parsed if str(k).strip()]
        except (ValueError, TypeError):
            pass
        return [raw.strip()] if raw.strip() else []
    return []


class ExperienceStore:
    """SQLite 经验记忆存储（线程安全：每次操作独立短连接）"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = _default_db_path()
        self.db_path = Path(db_path)
        if self.db_path.is_dir() or not self.db_path.suffix:
            self.db_path = self.db_path / DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._create_schema()

    # ── schema ──────────────────────────────────────────────────────────────
    def _create_schema(self) -> None:
        with self._lock, sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL DEFAULT 'manual',
                    active INTEGER NOT NULL DEFAULT 1,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    pos_count INTEGER NOT NULL DEFAULT 0,
                    neg_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exp_agent
                    ON experiences(agent_id, active);
                """
            )

    # ── 写：新增 ────────────────────────────────────────────────────────────
    def add(
        self,
        agent_id: str,
        title: str,
        content: str,
        keywords: Optional[list[str]] = None,
        source: str = "manual",
    ) -> int:
        """新增一条经验，返回 id"""
        now = _now()
        kw_json = json.dumps(_parse_keywords(keywords or []), ensure_ascii=False)
        with self._lock, sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO experiences"
                " (agent_id, title, content, keywords, source, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent_id, title, content, kw_json, source, now, now),
            )
            return int(cur.lastrowid)

    # ── 写：停用/启用 ───────────────────────────────────────────────────────
    def set_active(self, exp_id: int, active: bool) -> bool:
        with self._lock, sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "UPDATE experiences SET active = ?, updated_at = ? WHERE id = ?",
                (1 if active else 0, _now(), exp_id),
            )
            return cur.rowcount > 0

    # ── 读：列表 ────────────────────────────────────────────────────────────
    def list(self, agent_id: Optional[str] = None, include_inactive: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM experiences"
        params: list[Any] = []
        conds: list[str] = []
        if agent_id:
            conds.append("agent_id = ?")
            params.append(agent_id)
        if not include_inactive:
            conds.append("active = 1")
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY id DESC"
        with self._lock, sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._to_dict(r) for r in rows]

    # ── 读：按 id ───────────────────────────────────────────────────────────
    def get(self, exp_id: int) -> Optional[dict[str, Any]]:
        with self._lock, sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM experiences WHERE id = ?", (exp_id,)).fetchone()
        return self._to_dict(row) if row else None

    # ── 核心：检索（任务关键词匹配 + 烂经验过滤）─────────────────────────────
    def retrieve(
        self,
        agent_id: str,
        task: str,
        limit: int = RETRIEVE_LIMIT,
    ) -> list[dict[str, Any]]:
        """按 agent + 任务文本匹配经验，按（命中词数, 成功率）排序返回"""
        candidates = self.list(agent_id=agent_id, include_inactive=False)
        if not candidates:
            return []
        task_lower = (task or "").lower()
        scored: list[tuple[int, float, dict[str, Any]]] = []
        for exp in candidates:
            kws = _parse_keywords(exp.get("keywords"))
            hits = sum(1 for kw in kws if kw and kw.lower() in task_lower)
            if hits <= 0:
                continue
            pos, neg = exp.get("pos_count", 0), exp.get("neg_count", 0)
            # 质量门：样本足够时成功率过低 → 烂经验不注入（软过滤，不硬停用）
            if neg >= NEG_SAMPLE_BEFORE_GATE and (pos + neg) > 0:
                rate = pos / (pos + neg)
                if rate < LOW_SUCCESS_RATE:
                    logger.info(
                        f"[Memory] 经验#{exp['id']} 成功率{rate:.0%}过低，跳过注入"
                    )
                    continue
            scored.append((hits, pos - neg, exp))
        if not scored:
            return []
        # 排序：命中词数 > 净好评 > 新近
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        picked = [e for (_, _, e) in scored[:limit]]
        self._bump_hits([e["id"] for e in picked])
        return [
            {"id": e["id"], "title": e["title"], "content": e["content"]}
            for e in picked
        ]

    def _bump_hits(self, ids: list[int]) -> None:
        with self._lock, sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                "UPDATE experiences SET hit_count = hit_count + 1 WHERE id = ?",
                [(i,) for i in ids],
            )

    # ── 核心：打分回写 ───────────────────────────────────────────────────────
    def rate(self, exp_id: int, rating: int) -> Optional[dict[str, Any]]:
        """用户给经验打分（1-5）。rating>=4 记正反馈，<=2 记负反馈。
        负反馈样本足够且成功率 < LOW_SUCCESS_RATE 时自动停用该经验。"""
        exp = self.get(exp_id)
        if not exp:
            return None
        pos, neg = exp.get("pos_count", 0), exp.get("neg_count", 0)
        if rating >= 4:
            pos += 1
        elif rating <= 2:
            neg += 1
        # 其余(3分)只更新不计数
        deactivate = False
        if neg >= NEG_SAMPLE_BEFORE_GATE and (pos + neg) >= NEG_SAMPLE_BEFORE_GATE:
            rate = pos / (pos + neg)
            if rate < LOW_SUCCESS_RATE:
                deactivate = True
        with self._lock, sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "UPDATE experiences SET pos_count = ?, neg_count = ?,"
                " active = ?, updated_at = ? WHERE id = ?",
                (pos, neg, 0 if deactivate else exp.get("active", 1), _now(), exp_id),
            )
        logger.info(
            f"[Memory] 经验#{exp_id} 打分{rating} → pos={pos} neg={neg}"
            + ("，自动停用（成功率过低）" if deactivate else "")
        )
        return self.get(exp_id)

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["keywords"] = _parse_keywords(d.get("keywords"))
        d["success_rate"] = (
            round(d["pos_count"] / (d["pos_count"] + d["neg_count"]), 3)
            if (d["pos_count"] + d["neg_count"]) > 0 else None
        )
        return d


# ─── 模块级便捷函数（供 llm_executor / api_server 调用）──────────────────────

_store: Optional[ExperienceStore] = None


def get_experience_store() -> ExperienceStore:
    global _store
    if _store is None:
        _store = ExperienceStore()
    return _store


def create_experience(
    agent_id: str,
    title: str,
    content: str,
    keywords: Optional[list[str]] = None,
) -> dict[str, Any]:
    exp_id = get_experience_store().add(agent_id, title, content, keywords)
    return get_experience_store().get(exp_id)  # type: ignore[return-value]


def list_experiences(agent_id: Optional[str] = None, include_inactive: bool = False) -> list[dict[str, Any]]:
    return get_experience_store().list(agent_id=agent_id, include_inactive=include_inactive)


def deactivate_experience(exp_id: int) -> bool:
    return get_experience_store().set_active(exp_id, False)


def retrieve_experiences(agent_id: str, task: str, limit: int = RETRIEVE_LIMIT) -> list[dict[str, Any]]:
    """供 LLMExecutor 注入：返回 [{id, title, content}]，无命中返回 []"""
    try:
        return get_experience_store().retrieve(agent_id, task, limit=limit)
    except Exception as exc:  # noqa: BLE001 — 记忆层故障绝不阻断主流程
        logger.warning(f"[Memory] 检索失败: {exc}")
        return []


def apply_rating(exp_id: int, rating: int) -> dict[str, Any]:
    """打分回写；返回更新后的经验（含 active 状态）。"""
    updated = get_experience_store().rate(exp_id, int(rating))
    if updated is None:
        raise KeyError(f"经验 #{exp_id} 不存在")
    return updated
