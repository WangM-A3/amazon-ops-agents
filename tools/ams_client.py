"""
tools/ams_client.py
====================
AMS API 客户端 — Sponsored Products / Brands / Display + Marketing Stream

支持:
  - OAuth 2.0 自动刷新令牌
  - 自动重试 + 指数退避
  - 速率限制尊重
  - 多账户 / 多Profile并发
  - 历史报告 + 实时流双通道

Author: 硅基军团 · AMS数据接入 Agent
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

# ─── 日志 ────────────────────────────────────────────────────────────────────
logger = logging.getLogger("amazon_ops.ams_client")

# ─── 数据模型 ─────────────────────────────────────────────────────────────────

class AdType(Enum):
    SPONSORED_PRODUCTS = "sp"
    SPONSORED_BRANDS = "sb"
    SPONSORED_DISPLAY = "sd"


@dataclass
class TokenInfo:
    """OAuth Token 信息"""
    access_token: str
    token_type: str
    expires_in: int        # 秒
    refresh_token: str
    obtained_at: float      # time.time()


@dataclass
class CampaignMetrics:
    """广告活动指标"""
    campaign_id: str
    campaign_name: str
    campaign_type: AdType
    profile_id: str
    date: str              # YYYY-MM-DD
    # 核心指标
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    sales: float = 0.0
    orders: int = 0
    # 计算字段
    ctr: float = 0.0
    cvr: float = 0.0
    cpc: float = 0.0
    acos: float = 0.0
    roas: float = 0.0
    # 状态
    status: str = "enabled"
    bidding_strategy: str = ""
    budget: float = 0.0
    budget_type: str = "daily"
    # 时间戳
    fetched_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.impressions > 0:
            self.ctr = self.clicks / self.impressions
        if self.clicks > 0:
            self.cvr = self.orders / self.clicks
            self.cpc = self.spend / self.clicks
        if self.sales > 0:
            self.acos = self.spend / self.sales
            self.roas = self.sales / self.spend


@dataclass
class KeywordMetrics:
    """关键词指标"""
    keyword_id: str
    campaign_id: str
    ad_group_id: str
    keyword_text: str
    match_type: str         # exact | phrase | broad
    profile_id: str
    date: str
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    sales: float = 0.0
    orders: int = 0
    # 竞价
    current_bid: float = 0.0
    bid_strategy: str = "manual"
    # 计算
    ctr: float = 0.0
    cvr: float = 0.0
    cpc: float = 0.0
    acos: float = 0.0
    roas: float = 0.0
    # 状态
    state: str = "enabled"
    fetched_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.impressions > 0:
            self.ctr = self.clicks / self.impressions
        if self.clicks > 0:
            self.cvr = self.orders / self.clicks
            self.cpc = self.spend / self.clicks
        if self.sales > 0:
            self.acos = self.spend / self.sales
            self.roas = self.sales / self.spend


@dataclass
class StreamEvent:
    """Marketing Stream 事件"""
    event_type: str              # IMPRESSION | CLICK | CONVERSION
    campaign_id: str
    ad_group_id: Optional[str] = None
    keyword_id: Optional[str] = None
    asin: Optional[str] = None
    sku: Optional[str] = None
    profile_id: str = ""
    timestamp: str = ""          # ISO 8601
    value: float = 0.0           # 销售额（CONVERSION时）
    cost: float = 0.0            # 花费（CLICK时）
    event_id: str = ""           # 去重ID
    fetched_at: float = field(default_factory=time.time)


# ─── AMS API 端点 ─────────────────────────────────────────────────────────────

AMS_ENDPOINTS = {
    "us-east-1": {
        "auth":    "https://api.amazon.com/auth/o2/token",
        "sp":      "https://advertising-api.amazon.com",
        "sb":      "https://advertising-api.amazon.com",
        "sd":      "https://advertising-api.amazon.com",
        "stream":  "https://advertising-api-eu.amazon.com",   # Stream统一走EU端点
        "reports": "https://advertising-api.amazon.com",
    },
    "eu-west-1": {
        "auth":    "https://api.amazon.com/auth/o2/token",
        "sp":      "https://advertising-api.amazon.co.uk",
        "sb":      "https://advertising-api.amazon.co.uk",
        "sd":      "https://advertising-api.amazon.co.uk",
        "stream":  "https://advertising-api-eu.amazon.com",
        "reports": "https://advertising-api.amazon.co.uk",
    },
    "fe-west-1": {
        "auth":    "https://api.amazon.co.jp/auth/o2/token",
        "sp":      "https://advertising-api.amazon.co.jp",
        "sb":      "https://advertising-api.amazon.co.jp",
        "sd":      "https://advertising-api.amazon.co.jp",
        "stream":  "https://advertising-api-eu.amazon.com",
        "reports": "https://advertising-api.amazon.co.jp",
    },
}

PROFILE_ID_HEADER = "Amazon-Advertising-API-Scope"
CLIENT_ID_HEADER  = "Amazon-Advertising-API-ClientId"


# ─── 核心客户端 ──────────────────────────────────────────────────────────────

class AMSClient:
    """
    AMS API 统一客户端

    Usage:
        cfg = load_ams_config()
        async with AMSClient(cfg.accounts[0], cfg.rate_limit) as client:
            campaigns = await client.get_sp_campaigns()
    """

    def __init__(
        self,
        account,          # AMSAccountConfig
        rate_limit,       # RateLimitConfig
        cache=None,       # 可选AMSCache
        log_requests: bool = False,
    ):
        self.account = account
        self.rl = rate_limit
        self.cache = cache
        self.log_requests = log_requests

        self._token: Optional[TokenInfo] = None
        self._token_lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0.0
        self._request_lock = asyncio.Lock()

        # 请求计数（滑动窗口）
        self._request_timestamps: list[float] = []
        self._rate_window_seconds: int = 60

        # 指标
        self.total_requests = 0
        self.total_errors = 0
        self.last_error: Optional[str] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.account.timeout_seconds),
            headers={"User-Agent": "AmazonOpsAgents/1.0 (Python/async)"},
        )
        await self._ensure_token()
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Token管理 ──────────────────────────────────────────────────────────────

    async def _ensure_token(self) -> str:
        """确保有效access_token（自动刷新）"""
        async with self._token_lock:
            now = time.time()
            if self._token and (now - self._token.obtained_at) < (self._token.expires_in - 60):
                return self._token.access_token

            token = await self._refresh_token()
            self._token = token
            logger.info(f"[{self.account.account_id}] Token已刷新，有效期{token.expires_in}s")
            return token.access_token

    async def _refresh_token(self) -> TokenInfo:
        """执行OAuth刷新令牌"""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30))

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.account.refresh_token,
            "client_id": self.account.client_id,
            "client_secret": self.account.client_secret,
        }

        resp = await self._client.post(AMS_ENDPOINTS["us-east-1"]["auth"], data=data)
        resp.raise_for_status()
        body = resp.json()

        return TokenInfo(
            access_token=body["access_token"],
            token_type=body.get("token_type", "Bearer"),
            expires_in=int(body.get("expires_in", 3600)),
            refresh_token=body.get("refresh_token", self.account.refresh_token),
            obtained_at=time.time(),
        )

    def _get_headers(self, access_token: str, scope: Optional[str] = None) -> dict[str, str]:
        """构建API请求头"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            CLIENT_ID_HEADER: self.account.client_id,
            "Content-Type": "application/vnd.createasyncreportrequest.v3+json",
            "Accept": "application/vnd.createasyncreportrequest.v3+json",
        }
        if scope or self.account.profile_id:
            headers[PROFILE_ID_HEADER] = scope or self.account.profile_id
        return headers

    # ── 速率限制 ───────────────────────────────────────────────────────────────

    async def _throttle(self, rpm: int):
        """尊重速率限制（滑动窗口）"""
        async with self._request_lock:
            now = time.time()
            # 清理过期窗口
            self._request_timestamps = [
                t for t in self._request_timestamps
                if now - t < self._rate_window_seconds
            ]

            if len(self._request_timestamps) >= rpm:
                oldest = self._request_timestamps[0]
                wait = self._rate_window_seconds - (now - oldest) + 0.05
                if wait > 0:
                    logger.debug(f"[{self.account.account_id}] 速率限制触发，等待{wait:.2f}s")
                    await asyncio.sleep(wait)
                    now = time.time()
                    self._request_timestamps = [
                        t for t in self._request_timestamps
                        if now - t < self._rate_window_seconds
                    ]

            self._request_timestamps.append(now)

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        rpm: int = 10,
    ) -> httpx.Response:
        """
        带重试的HTTP请求

        Retry策略：
        - 指数退避 × 抖动
        - 最多重试3次（或account.retry_attempts次）
        - 重试条件：429/500/502/503/504
        """
        await self._throttle(rpm)

        attempts = 0
        max_attempts = self.account.retry_attempts
        delay = self.rl.base_delay_seconds

        while attempts <= max_attempts:
            attempts += 1
            try:
                if not self._client:
                    self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.account.timeout_seconds))

                access_token = await self._ensure_token()
                req_headers = headers or self._get_headers(access_token)

                resp = await self._client.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    json=data,
                    params=params,
                )

                self.total_requests += 1

                if resp.status_code == 429:
                    # Rate limit — 按 Retry-After 延迟
                    retry_after = float(resp.headers.get("Retry-After", delay))
                    logger.warning(f"[{self.account.account_id}] 429 Rate Limited，等待{retry_after}s")
                    await asyncio.sleep(retry_after)
                    delay = min(delay * 2, self.rl.max_delay_seconds)
                    continue

                if resp.status_code >= 500 and attempts <= max_attempts:
                    logger.warning(f"[{self.account.account_id}] {resp.status_code}，重试({attempts}/{max_attempts})")
                    await asyncio.sleep(delay)
                    delay = min(delay * self.rl.exponential_base, self.rl.max_delay_seconds)
                    continue

                resp.raise_for_status()
                return resp

            except httpx.TimeoutException:
                logger.warning(f"[{self.account.account_id}] 超时，重试({attempts}/{max_attempts})")
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.rl.max_delay_seconds)
                continue

            except Exception as e:
                self.total_errors += 1
                self.last_error = str(e)
                logger.error(f"[{self.account.account_id}] 请求失败: {e}")
                raise

        # 最终尝试
        access_token = await self._ensure_token()
        req_headers = headers or self._get_headers(access_token)
        resp = await self._client.request(
            method=method, url=url, headers=req_headers,
            json=data, params=params,
        )
        resp.raise_for_status()
        return resp

    # ── Sponsored Products API ─────────────────────────────────────────────────

    def _sp_base(self) -> str:
        ep = AMS_ENDPOINTS.get(self.account.region, AMS_ENDPOINTS["us-east-1"])
        return ep["sp"]

    async def get_sp_campaigns(self, state_filter: Optional[str] = None) -> list[CampaignMetrics]:
        """
        获取Sponsored Products广告活动列表
        POST /campaigns/list
        """
        url = f"{self._sp_base()}/sp/campaigns/list"
        payload = {
            "stateFilter": state_filter or "enabled,paused",
            "pagination": {"additionalProperties": {}},
        }

        all_campaigns = []
        next_token = None

        while True:
            if next_token:
                payload["pagination"] = {"nextToken": next_token}

            resp = await self._request_with_retry(
                "POST", url,
                data=payload,
                rpm=self.rl.sp_campaigns_rpm,
            )
            body = resp.json()

            for c in body.get("campaigns", []):
                all_campaigns.append(CampaignMetrics(
                    campaign_id=c.get("campaignId", ""),
                    campaign_name=c.get("name", ""),
                    campaign_type=AdType.SPONSORED_PRODUCTS,
                    profile_id=self.account.profile_id,
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    status=c.get("state", "unknown"),
                    budget=float(c.get("dailyBudget", 0) or 0),
                    budget_type=c.get("budgetType", "daily"),
                    bidding_strategy=c.get("biddingStrategy", {}).get("strategy", "legacy_for_tacos"),
                ))

            next_token = body.get("pagination", {}).get("nextToken")
            if not next_token:
                break

        logger.info(f"[{self.account.account_id}] 获取SP广告活动: {len(all_campaigns)}条")
        return all_campaigns

    async def get_sp_keywords(
        self,
        campaign_id: Optional[str] = None,
        state_filter: Optional[str] = None,
    ) -> list[KeywordMetrics]:
        """
        获取关键词列表（含出价）
        POST /keywords/list
        """
        url = f"{self._sp_base()}/sp/keywords/list"
        payload = {
            "stateFilter": state_filter or "enabled,paused",
        }
        if campaign_id:
            payload["campaignIdFilter"] = {"include": [campaign_id]}

        all_keywords = []
        next_token = None

        while True:
            if next_token:
                payload["pagination"] = {"nextToken": next_token}

            resp = await self._request_with_retry(
                "POST", url,
                data=payload,
                rpm=self.rl.sp_keywords_rpm,
            )
            body = resp.json()

            for kw in body.get("keywords", []):
                bid_info = kw.get("bid", {}) or {}
                current_bid = float(bid_info.get("default", 0) or 0)

                all_keywords.append(KeywordMetrics(
                    keyword_id=kw.get("keywordId", ""),
                    campaign_id=kw.get("campaignId", ""),
                    ad_group_id=kw.get("adGroupId", ""),
                    keyword_text=kw.get("keywordText", ""),
                    match_type=kw.get("matchType", "exact"),
                    profile_id=self.account.profile_id,
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    current_bid=current_bid,
                    bid_strategy=kw.get("biddingStrategy", {}).get("strategy", "manual"),
                    state=kw.get("state", "unknown"),
                ))

            next_token = body.get("pagination", {}).get("nextToken")
            if not next_token:
                break

        logger.info(f"[{self.account.account_id}] 获取SP关键词: {len(all_keywords)}条")
        return all_keywords

    async def get_sp_performance(
        self,
        campaign_ids: Optional[list[str]] = None,
        metric_types: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[CampaignMetrics]:
        """
        获取实时性能指标（通过报告API轮询）
        POST /reporting/reports

        注意：AMS报告是异步的，这里演示同步方式（实际生产应使用async report）
        """
        url = f"{self._sp_base()}/reporting/reports"

        # 构建报告
        report_payload = {
            "name": f"perf_{int(time.time())}",
            "startDate": start_date or (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"),
            "endDate": end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["campaign"],
                "columns": [
                    "campaignId", "campaignName", "campaignStatus",
                    "impressions", "clicks", "cost", "purchases1d",
                    "purchases7d", "purchases30d", "sales1d", "sales7d", "sales30d",
                ],
                "reportTypeId": "spCampaigns",
                "timeUnit": "SUMMARY",
            },
        }

        # ── Step 1: 创建报告 ─────────────────────────────────────────────────
        resp = await self._request_with_retry(
            "POST", url,
            data=report_payload,
            rpm=self.rl.sp_reports_rpm,
        )
        report_id = resp.json().get("reportId")

        # ── Step 2: 轮询报告状态 ─────────────────────────────────────────────
        status_url = f"{self._sp_base()}/reporting/reports/{report_id}"
        for _ in range(30):   # 最多等待5分钟
            await asyncio.sleep(10)
            status_resp = await self._request_with_retry(
                "GET", status_url,
                rpm=self.rl.sp_reports_rpm,
            )
            status_body = status_resp.json()
            if status_body.get("status") == "COMPLETED":
                break
            elif status_body.get("status") == "FAILED":
                raise RuntimeError(f"报告生成失败: {status_body.get('details')}")

        # ── Step 3: 下载报告 ─────────────────────────────────────────────────
        download_url = status_body.get("url")
        if download_url:
            dl_resp = await self._client.get(download_url)  # 第三方URL，无auth
            records = self._parse_tsv(dl_resp.text)
            return self._records_to_metrics(records, AdType.SPONSORED_PRODUCTS)

        return []

    # ── Marketing Stream ──────────────────────────────────────────────────────

    async def stream_events(
        self,
        stream_type: str = "MARKETING",   # MARKETING | CREATIVE | CAMPAIGN
        event_types: Optional[list[str]] = None,
    ) -> list[StreamEvent]:
        """
        连接Amazon Marketing Stream（AWS EventBridge / Kinesis兼容）
        返回过去时间窗口内的事件

        实际实现依赖：Marketing Stream的EventBridge sink或Kinesis pull
        这里展示SDK兼容的事件拉取逻辑
        """
        ep = AMS_ENDPOINTS.get(self.account.region, AMS_ENDPOINTS["us-east-1"])
        url = f"{ep['stream']}/reporting/stream"

        payload = {
            "eventTypes": event_types or ["IMPRESSION", "CLICK", "CONVERSION"],
            "streamType": stream_type,
            "profileId": self.account.profile_id,
        }

        try:
            resp = await self._request_with_retry(
                "POST", url,
                data=payload,
                rpm=self.rl.stream_rpm,
            )
            body = resp.json()
            events = []
            for raw in body.get("events", []):
                events.append(StreamEvent(
                    event_type=raw.get("eventType", "UNKNOWN"),
                    campaign_id=raw.get("campaignId", ""),
                    ad_group_id=raw.get("adGroupId"),
                    keyword_id=raw.get("keywordId"),
                    asin=raw.get("asin"),
                    sku=raw.get("sku"),
                    profile_id=raw.get("profileId", self.account.profile_id),
                    timestamp=raw.get("timestamp", ""),
                    value=float(raw.get("value", 0)),
                    cost=float(raw.get("cost", 0)),
                    event_id=raw.get("eventId", str(uuid.uuid4())),
                ))
            logger.debug(f"[{self.account.account_id}] Stream事件: {len(events)}条")
            return events
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"[{self.account.account_id}] Marketing Stream未启用，跳过")
                return []
            raise

    # ── 批量聚合 ──────────────────────────────────────────────────────────────

    async def get_all_performance(self) -> dict[str, Any]:
        """
        获取全维度性能数据（供数据管道使用）

        Returns:
            {
                "campaigns": [CampaignMetrics],
                "keywords": [KeywordMetrics],
                "stream_events": [StreamEvent],
                "fetched_at": timestamp
            }
        """
        fetched_at = time.time()

        # 并发拉取（各API独立）
        campaigns_task = self.get_sp_campaigns()
        keywords_task  = self.get_sp_keywords()
        stream_task    = self.stream_events()

        campaigns, keywords, events = await asyncio.gather(
            campaigns_task, keywords_task, stream_task,
            return_exceptions=True,
        )

        # 处理异常（降级而非崩溃）
        if isinstance(campaigns, Exception):
            logger.error(f"Campaigns拉取失败: {campaigns}")
            campaigns = []
        if isinstance(keywords, Exception):
            logger.error(f"Keywords拉取失败: {keywords}")
            keywords = []
        if isinstance(events, Exception):
            logger.error(f"Stream事件拉取失败: {events}")
            events = []

        return {
            "campaigns": campaigns,
            "keywords": keywords,
            "stream_events": events,
            "fetched_at": fetched_at,
            "account_id": self.account.account_id,
            "profile_id": self.account.profile_id,
        }

    # ── 工具方法 ──────────────────────────────────────────────────────────────

    def _parse_tsv(self, text: str) -> list[dict[str, str]]:
        """解析TSV格式报告"""
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return []
        headers = lines[0].split("\t")
        records = []
        for line in lines[1:]:
            cols = line.split("\t")
            if len(cols) == len(headers):
                records.append(dict(zip(headers, cols)))
        return records

    def _records_to_metrics(
        self,
        records: list[dict[str, str]],
        ad_type: AdType,
    ) -> list[CampaignMetrics]:
        """将报告记录转换为CampaignMetrics"""
        metrics = []
        for r in records:
            m = CampaignMetrics(
                campaign_id=r.get("campaignId", ""),
                campaign_name=r.get("campaignName", ""),
                campaign_type=ad_type,
                profile_id=self.account.profile_id,
                date=r.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                impressions=int(r.get("impressions", 0) or 0),
                clicks=int(r.get("clicks", 0) or 0),
                spend=float(r.get("cost", 0) or 0),
                sales=float(r.get("sales1d", 0) or r.get("sales7d", 0) or 0),
                orders=int(r.get("purchases1d", 0) or r.get("purchases7d", 0) or 0),
                status=r.get("campaignStatus", "unknown"),
            )
            metrics.append(m)
        return metrics

    # ── 便捷方法 ──────────────────────────────────────────────────────────────

    @property
    def api_health(self) -> dict[str, Any]:
        """API健康状态（用于监控）"""
        return {
            "account_id": self.account.account_id,
            "profile_id": self.account.profile_id,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": self.total_errors / max(self.total_requests, 1),
            "last_error": self.last_error,
            "token_valid": (
                self._token is not None
                and (time.time() - self._token.obtained_at) < self._token.expires_in
            ),
        }


# ─── 多账户并发客户端 ─────────────────────────────────────────────────────────

class MultiAccountAMSClient:
    """
    多账户AMS客户端 — 并发管理多个账户

    Usage:
        multi = MultiAccountAMSClient(cfg)
        results = await multi.fetch_all()
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self._clients: dict[str, AMSClient] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        for client in self._clients.values():
            await client.__aexit__(*args)
        self._clients.clear()

    async def get_client(self, account_id: str) -> Optional[AMSClient]:
        """获取或创建指定账户的客户端"""
        if account_id in self._clients:
            return self._clients[account_id]

        account = self.cfg.get_account(account_id)
        if not account or not account.enabled:
            return None

        client = AMSClient(
            account=account,
            rate_limit=self.cfg.rate_limit,
            log_requests=self.cfg.log_requests,
        )
        await client.__aenter__()
        self._clients[account_id] = client
        return client

    async def fetch_all(self) -> dict[str, dict]:
        """
        并发拉取所有启用账户的数据

        Returns:
            {account_id: {campaigns, keywords, stream_events, fetched_at}}
        """
        tasks = {}
        for acc in self.cfg.enabled_accounts():
            async def _fetch(a):
                client = await self.get_client(a.account_id)
                if client:
                    return await client.get_all_performance()
                return {}

            tasks[acc.account_id] = asyncio.create_task(_fetch(acc))

        results = {}
        for acc_id, task in tasks.items():
            try:
                results[acc_id] = await task
            except Exception as e:
                logger.error(f"账户 {acc_id} 拉取失败: {e}")
                results[acc_id] = {"error": str(e)}

        return results

    def all_health(self) -> list[dict]:
        return [c.api_health for c in self._clients.values()]
