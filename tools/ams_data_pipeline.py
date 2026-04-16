"""
tools/ams_data_pipeline.py
==========================
AMS 数据管道 — 数据清洗 → 存储缓存 → ProfitOptimizer消费

架构:
    AMS API
        ↓
    AMSClient（认证/速率限制）
        ↓
    DataPipeline（清洗/聚合/去重）
        ↓
    AMSCache（SQLite存储 + TTL缓存）
        ↓
    RealTimeMetricsEngine（实时指标计算）
        ↓
    ProfitOptimizer（竞价优化）/ AlertSystem（告警）

Author: 硅基军团 · AMS数据接入 Agent
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import sqlite3
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Generator

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("amazon_ops.ams_pipeline")

# ─── 依赖可选导入 ─────────────────────────────────────────────────────────────
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

# ─── 数据管道状态 ─────────────────────────────────────────────────────────────

class PipelineState(Enum):
    STOPPED   = "stopped"
    STARTING  = "starting"
    RUNNING   = "running"
    PAUSED    = "paused"
    STOPPING  = "stopping"
    ERROR     = "error"


# ─── 事件类型 ─────────────────────────────────────────────────────────────────

@dataclass
class PipelineEvent:
    """管道事件（用于Webhook/日志/追踪）"""
    event_type: str          # UPDATE | FLUSH | ALERT | ERROR | HEARTBEAT
    profile_id: str
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    pipeline_id: str = "main"

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "profile_id": self.profile_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "pipeline_id": self.pipeline_id,
            "iso_time": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
        }


# ─── 数据清洗器 ──────────────────────────────────────────────────────────────

@dataclass
class DataCleaner:
    """
    数据清洗器 — 确保数据质量

    清洗规则:
    1. 去重（event_id去重）
    2. 异常值过滤（impressions<0, spend<0, bid>上限）
    3. 类型强制转换
    4. 缺失值填充
    """

    max_bid: float = 99.99
    max_daily_spend: float = 10000.0
    min_ctr: float = 0.0
    max_ctr: float = 1.0

    def clean_campaigns(self, raw: list[dict]) -> list[dict]:
        """清洗广告活动数据"""
        seen = set()
        cleaned = []

        for r in raw:
            cid = r.get("campaignId") or r.get("campaign_id")
            if not cid or cid in seen:
                continue

            # 类型转换
            try:
                item = {
                    "campaign_id": str(cid),
                    "campaign_name": str(r.get("campaignName", r.get("campaign_name", "Unknown"))),
                    "impressions": max(0, int(r.get("impressions", 0))),
                    "clicks": max(0, int(r.get("clicks", 0))),
                    "spend": max(0.0, float(r.get("spend", r.get("cost", 0)))),
                    "sales": max(0.0, float(r.get("sales", 0))),
                    "orders": max(0, int(r.get("orders", r.get("purchases1d", 0)))),
                    "budget": max(0.0, float(r.get("budget", r.get("dailyBudget", 0)) or 0)),
                    "status": str(r.get("status", r.get("state", "enabled"))),
                    "acos": 0.0,  # 计算属性
                    "roas": 0.0,  # 计算属性
                }

                # 过滤异常值
                if item["spend"] > self.max_daily_spend:
                    logger.warning(f"异常spend值过滤: {item['campaign_id']} spend={item['spend']}")
                    continue

                if item["impressions"] > 0:
                    item["ctr"] = item["clicks"] / item["impressions"]
                if item["sales"] > 0:
                    item["acos"] = item["spend"] / item["sales"]
                    item["roas"] = item["sales"] / item["spend"]

                seen.add(cid)
                cleaned.append(item)

            except (ValueError, TypeError) as e:
                logger.debug(f"数据清洗跳过: {e}")

        return cleaned

    def clean_keywords(self, raw: list[dict]) -> list[dict]:
        """清洗关键词数据"""
        seen = set()
        cleaned = []

        for r in raw:
            kid = r.get("keywordId") or r.get("keyword_id")
            if not kid or kid in seen:
                continue

            try:
                bid = float(r.get("current_bid", r.get("bid", 0) or 0))
                bid = min(bid, self.max_bid)   # 出价上限

                item = {
                    "keyword_id": str(kid),
                    "campaign_id": str(r.get("campaignId", r.get("campaign_id", ""))),
                    "ad_group_id": str(r.get("adGroupId", r.get("ad_group_id", ""))),
                    "keyword_text": str(r.get("keywordText", r.get("keyword_text", ""))),
                    "match_type": str(r.get("matchType", r.get("match_type", "exact"))),
                    "impressions": max(0, int(r.get("impressions", 0))),
                    "clicks": max(0, int(r.get("clicks", 0))),
                    "spend": max(0.0, float(r.get("spend", r.get("cost", 0)))),
                    "sales": max(0.0, float(r.get("sales", 0))),
                    "orders": max(0, int(r.get("orders", r.get("purchases1d", 0)))),
                    "current_bid": bid,
                    "state": str(r.get("state", "enabled")),
                }

                if item["impressions"] > 0:
                    item["ctr"] = item["clicks"] / item["impressions"]
                if item["clicks"] > 0:
                    item["cvr"] = item["orders"] / item["clicks"]
                    item["cpc"] = item["spend"] / item["clicks"]
                if item["sales"] > 0:
                    item["acos"] = item["spend"] / item["sales"]
                    item["roas"] = item["sales"] / item["spend"]

                seen.add(kid)
                cleaned.append(item)

            except (ValueError, TypeError):
                continue

        return cleaned

    def deduplicate_events(self, events: list[dict]) -> list[dict]:
        """事件流去重（event_id）"""
        seen = set()
        unique = []
        for e in events:
            eid = e.get("event_id", "")
            if not eid:
                eid = f"{e.get('campaign_id', '')}_{e.get('timestamp', '')}_{e.get('event_type', '')}"
            if eid not in seen:
                seen.add(eid)
                unique.append(e)
        return unique


# ─── SQLite缓存 ──────────────────────────────────────────────────────────────

class AMSCache:
    """
    SQLite后端缓存

    表结构:
    - campaign_metrics: 广告活动指标（TTL可配置）
    - keyword_metrics: 关键词指标
    - stream_events: Stream事件（当日）
    - raw_reports: 原始报告（归档）
    """

    def __init__(self, db_path: str = "data/ams_cache.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        with self._conn_ctx() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS campaign_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    impressions INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    spend REAL DEFAULT 0.0,
                    sales REAL DEFAULT 0.0,
                    orders INTEGER DEFAULT 0,
                    ctr REAL DEFAULT 0.0,
                    acos REAL DEFAULT 0.0,
                    roas REAL DEFAULT 0.0,
                    fetched_at REAL NOT NULL,
                    UNIQUE(campaign_id, profile_id, date)
                );

                CREATE TABLE IF NOT EXISTS keyword_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    match_type TEXT DEFAULT 'exact',
                    impressions INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    spend REAL DEFAULT 0.0,
                    sales REAL DEFAULT 0.0,
                    orders INTEGER DEFAULT 0,
                    current_bid REAL DEFAULT 0.0,
                    acos REAL DEFAULT 0.0,
                    fetched_at REAL NOT NULL,
                    UNIQUE(keyword_id, profile_id, date)
                );

                CREATE TABLE IF NOT EXISTS stream_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE,
                    campaign_id TEXT NOT NULL,
                    keyword_id TEXT,
                    event_type TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    event_timestamp TEXT,
                    value REAL DEFAULT 0.0,
                    cost REAL DEFAULT 0.0,
                    asin TEXT,
                    sku TEXT,
                    fetched_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pipeline_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT,
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_campaign_lookup
                    ON campaign_metrics(campaign_id, profile_id, date);
                CREATE INDEX IF NOT EXISTS idx_keyword_lookup
                    ON keyword_metrics(keyword_id, profile_id, date);
                CREATE INDEX IF NOT EXISTS idx_stream_events
                    ON stream_events(profile_id, event_type, fetched_at);
            """)

    @contextmanager
    def _conn_ctx(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_campaign(self, m: dict, fetched_at: float):
        with self._conn_ctx() as conn:
            conn.execute("""
                INSERT INTO campaign_metrics
                    (campaign_id, profile_id, date, impressions, clicks, spend, sales,
                     orders, ctr, acos, roas, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, profile_id, date) DO UPDATE SET
                    impressions=excluded.impressions,
                    clicks=excluded.clicks,
                    spend=excluded.spend,
                    sales=excluded.sales,
                    orders=excluded.orders,
                    ctr=excluded.ctr,
                    acos=excluded.acos,
                    roas=excluded.roas,
                    fetched_at=excluded.fetched_at
            """, (
                m["campaign_id"], m["profile_id"], m.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                m["impressions"], m["clicks"], m["spend"], m["sales"],
                m["orders"], m.get("ctr", 0), m.get("acos", 0), m.get("roas", 0),
                fetched_at,
            ))

    def upsert_keyword(self, m: dict, fetched_at: float):
        with self._conn_ctx() as conn:
            conn.execute("""
                INSERT INTO keyword_metrics
                    (keyword_id, campaign_id, profile_id, date, match_type,
                     impressions, clicks, spend, sales, orders, current_bid, acos, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(keyword_id, profile_id, date) DO UPDATE SET
                    impressions=excluded.impressions,
                    clicks=excluded.clicks,
                    spend=excluded.spend,
                    sales=excluded.sales,
                    orders=excluded.orders,
                    current_bid=excluded.current_bid,
                    acos=excluded.acos,
                    fetched_at=excluded.fetched_at
            """, (
                m["keyword_id"], m["campaign_id"], m["profile_id"],
                m.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                m.get("match_type", "exact"),
                m["impressions"], m["clicks"], m["spend"], m["sales"],
                m["orders"], m["current_bid"], m.get("acos", 0),
                fetched_at,
            ))

    def insert_stream_events(self, events: list[dict], fetched_at: float):
        if not events:
            return
        with self._conn_ctx() as conn:
            conn.executemany("""
                INSERT OR IGNORE INTO stream_events
                    (event_id, campaign_id, keyword_id, event_type, profile_id,
                     event_timestamp, value, cost, asin, sku, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (e.get("event_id", ""), e.get("campaign_id", ""),
                 e.get("keyword_id"), e.get("event_type", ""),
                 e.get("profile_id", ""), e.get("timestamp", ""),
                 e.get("value", 0), e.get("cost", 0),
                 e.get("asin"), e.get("sku"), fetched_at)
                for e in events
            ])

    def log_event(self, profile_id: str, event_type: str, payload: dict):
        with self._conn_ctx() as conn:
            conn.execute("""
                INSERT INTO pipeline_log (profile_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
            """, (profile_id, event_type, json.dumps(payload), time.time()))

    def get_latest_campaigns(self, profile_id: str, limit: int = 100) -> list[dict]:
        with self._conn_ctx() as conn:
            rows = conn.execute("""
                SELECT campaign_id, impressions, clicks, spend, sales, orders, acos, roas, fetched_at
                FROM campaign_metrics
                WHERE profile_id = ?
                ORDER BY fetched_at DESC
                LIMIT ?
            """, (profile_id, limit)).fetchall()
        cols = ["campaign_id", "impressions", "clicks", "spend", "sales", "orders", "acos", "roas", "fetched_at"]
        return [dict(zip(cols, r)) for r in rows]

    def purge_old_data(self, retention_days: int = 90):
        """清理过期数据"""
        cutoff = time.time() - retention_days * 86400
        with self._conn_ctx() as conn:
            deleted = conn.execute(
                "DELETE FROM campaign_metrics WHERE fetched_at < ?", (cutoff,)
            ).rowcount
            kw_deleted = conn.execute(
                "DELETE FROM keyword_metrics WHERE fetched_at < ?", (cutoff,)
            ).rowcount
            # Stream事件保留7天
            stream_cutoff = time.time() - 7 * 86400
            stream_deleted = conn.execute(
                "DELETE FROM stream_events WHERE fetched_at < ?", (stream_cutoff,)
            ).rowcount
        logger.info(f"数据清理: campaigns={deleted} keywords={kw_deleted} stream={stream_deleted}")


# ─── 数据管道 ───────────────────────────────────────────────────────────────

class DataPipeline:
    """
    AMS 数据管道 — 协调AMSClient → 清洗 → 缓存 → 实时指标引擎

    Usage:
        cfg = load_ams_config()
        cache = AMSCache()
        metrics_engine = RealTimeMetricsEngine(cfg, profit_optimizer)

        pipeline = DataPipeline(cfg, cache, metrics_engine)
        await pipeline.start()

        # 手动触发一次拉取
        await pipeline.fetch_once()

        # 停止
        await pipeline.stop()
    """

    def __init__(
        self,
        config,               # AMSConfig
        cache: AMSCache,
        metrics_engine,        # RealTimeMetricsEngine
        on_event: Optional[callable] = None,  # PipelineEvent回调
    ):
        self.config = config
        self.cache = cache
        self.metrics = metrics_engine
        self.on_event = on_event

        self.cleaner = DataCleaner()
        self.state = PipelineState.STOPPED

        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()
        self._paused  = asyncio.Event()

        # 统计
        self.cycle_count = 0
        self.last_cycle_at: float = 0.0
        self.last_cycle_duration: float = 0.0
        self.errors_this_session = 0
        self.bytes_processed = 0

    # ── 生命周期 ─────────────────────────────────────────────────────────────

    async def start(self):
        """启动数据管道（后台运行）"""
        if self.state == PipelineState.RUNNING:
            logger.warning("管道已在运行中")
            return

        self.state = PipelineState.STARTING
        self._running.set()
        self._paused.set()

        self._task = asyncio.create_task(self._run_loop())
        self.state = PipelineState.RUNNING
        logger.info("AMS数据管道已启动")

    async def stop(self, timeout: float = 30):
        """优雅停止"""
        self.state = PipelineState.STOPPING
        self._running.clear()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("管道停止超时，强制取消")

        self.state = PipelineState.STOPPED
        logger.info(f"AMS数据管道已停止 | cycle={self.cycle_count} errors={self.errors_this_session}")

    async def pause(self):
        self._paused.clear()
        self.state = PipelineState.PAUSED
        logger.info("管道已暂停")

    async def resume(self):
        self._paused.set()
        self.state = PipelineState.RUNNING
        logger.info("管道已恢复")

    # ── 主循环 ────────────────────────────────────────────────────────────────

    async def _run_loop(self):
        """后台轮询循环"""
        interval = self.config.pipeline.polling_interval_seconds

        while self._running.is_set():
            await self._paused.wait()   # 暂停时阻塞

            if not self._running.is_set():
                break

            try:
                await self._fetch_and_process()
                self.cycle_count += 1
            except Exception as e:
                self.errors_this_session += 1
                logger.error(f"拉取循环异常: {e}", exc_info=True)
                if self.errors_this_session >= 5:
                    self.state = PipelineState.ERROR
                    logger.critical("连续错误过多，管道进入ERROR状态")

            # 等待下一次轮询
            try:
                await asyncio.wait_for(
                    self._running.wait(),
                    timeout=interval,
                )
            except asyncio.TimeoutError:
                pass  # 正常超时，继续下一次循环

    async def _fetch_and_process(self):
        """单次拉取-处理循环"""
        t0 = time.time()

        async with MultiAccountAMSClient(self.config) as multi_client:
            all_results = await multi_client.fetch_all()

        for account_id, result in all_results.items():
            if "error" in result:
                logger.error(f"账户 {account_id} 拉取出错: {result['error']}")
                continue

            profile_id = result.get("profile_id", account_id)
            fetched_at  = result.get("fetched_at", time.time())

            # ── Step 1: 数据清洗 ───────────────────────────────────────────
            raw_campaigns = [c.__dict__ for c in result.get("campaigns", [])]
            raw_keywords  = [k.__dict__ for k in result.get("keywords", [])]
            raw_events    = [e.__dict__ for e in result.get("stream_events", [])]

            clean_campaigns = self.cleaner.clean_campaigns(raw_campaigns)
            clean_keywords  = self.cleaner.clean_keywords(raw_keywords)
            clean_events    = self.cleaner.deduplicate_events(raw_events)

            # ── Step 2: 存储缓存 ──────────────────────────────────────────
            for c in clean_campaigns:
                self.cache.upsert_campaign(c, fetched_at)
            for k in clean_keywords:
                self.cache.upsert_keyword(k, fetched_at)
            if clean_events:
                self.cache.insert_stream_events(clean_events, fetched_at)

            # ── Step 3: 更新实时指标引擎 ──────────────────────────────────
            from tools.ams_client import CampaignMetrics, KeywordMetrics, StreamEvent

            camp_objs = [CampaignMetrics(
                campaign_id=c["campaign_id"],
                campaign_name=c["campaign_name"],
                campaign_type=AdType.SPONSORED_PRODUCTS,
                profile_id=profile_id,
                date=c.get("date", ""),
                impressions=c["impressions"],
                clicks=c["clicks"],
                spend=c["spend"],
                sales=c["sales"],
                orders=c["orders"],
                budget=c["budget"],
                fetched_at=fetched_at,
            ) for c in clean_campaigns]

            kw_objs = [KeywordMetrics(
                keyword_id=k["keyword_id"],
                campaign_id=k["campaign_id"],
                ad_group_id=k.get("ad_group_id", ""),
                keyword_text=k["keyword_text"],
                match_type=k["match_type"],
                profile_id=profile_id,
                date=k.get("date", ""),
                impressions=k["impressions"],
                clicks=k["clicks"],
                spend=k["spend"],
                sales=k["sales"],
                orders=k["orders"],
                current_bid=k["current_bid"],
                state=k["state"],
                fetched_at=fetched_at,
            ) for k in clean_keywords]

            event_objs = [StreamEvent(
                event_type=e.get("event_type", "UNKNOWN"),
                campaign_id=e.get("campaign_id", ""),
                keyword_id=e.get("keyword_id"),
                asin=e.get("asin"),
                sku=e.get("sku"),
                profile_id=profile_id,
                timestamp=e.get("timestamp", ""),
                value=float(e.get("value", 0)),
                cost=float(e.get("cost", 0)),
                event_id=e.get("event_id", str(uuid.uuid4())),
                fetched_at=fetched_at,
            ) for e in clean_events]

            self.metrics.update_campaign_metrics(profile_id, camp_objs)
            self.metrics.update_keyword_metrics(profile_id, kw_objs)
            self.metrics.update_stream_events(profile_id, event_objs)

            # ── Step 4: ProfitOptimizer推送 ──────────────────────────────
            if self.config.pipeline.push_to_optimizer:
                await self.metrics.push_to_optimizer()

            # ── Step 5: 事件回调 ───────────────────────────────────────────
            if self.on_event:
                self.on_event(PipelineEvent(
                    event_type="UPDATE",
                    profile_id=profile_id,
                    payload={
                        "campaigns": len(clean_campaigns),
                        "keywords": len(clean_keywords),
                        "events": len(clean_events),
                        "fetched_at": fetched_at,
                    }
                ))

        duration = time.time() - t0
        self.last_cycle_at = time.time()
        self.last_cycle_duration = round(duration, 3)
        self.bytes_processed += sum(len(json.dumps(c)) for c in clean_campaigns)

        logger.info(
            f"拉取完成 | 耗时={duration:.2f}s | "
            f"账户={len(all_results)} | 总campaigns={sum(len(r.get('campaigns', [])) for r in all_results.values())}"
        )

    # ── 手动触发 ─────────────────────────────────────────────────────────────

    async def fetch_once(self) -> dict[str, Any]:
        """手动触发一次完整拉取（不启动后台循环）"""
        t0 = time.time()
        try:
            await self._fetch_and_process()
            return {"status": "success", "duration": round(time.time() - t0, 3)}
        except Exception as e:
            logger.error(f"手动拉取失败: {e}")
            return {"status": "error", "error": str(e)}

    # ── 报告 ─────────────────────────────────────────────────────────────────

    async def get_health_report(self) -> dict[str, Any]:
        """健康报告"""
        alerts = await self.metrics.get_alerts()
        return {
            "pipeline_state": self.state.value,
            "cycle_count": self.cycle_count,
            "errors_this_session": self.errors_this_session,
            "last_cycle_at": datetime.fromtimestamp(self.last_cycle_at, tz=timezone.utc).isoformat() if self.last_cycle_at else None,
            "last_cycle_duration_s": self.last_cycle_duration,
            "metrics_health": self.metrics.health,
            "recent_alerts": [a for a in alerts if time.time() - a["timestamp"] < 3600],
        }


# ─── 导入兼容 ────────────────────────────────────────────────────────────────
import uuid
from tools.ams_client import MultiAccountAMSClient, AdType
