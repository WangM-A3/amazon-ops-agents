"""
data/sp_api_client.py — Amazon Selling Partner API (SP-API) 客户端
====================================================================
真实数据层的外部通道。生产形态：
- LWA (Login With Amazon) OAuth2: client_id/client_secret/refresh_token -> access_token
- 请求带 x-amz-access-token + x-amz-date；端点按 region 路由
- 指数退避重试 + 限速保护；凭据缺失时 available=False，由 DataProvider 降级到 demo

环境变量：
- SPAPI_CLIENT_ID / SPAPI_CLIENT_SECRET / SPAPI_REFRESH_TOKEN / SPAPI_REGION / SPAPI_MARKETPLACE_ID
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger("amazon_ops.sp_api")

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

_REGION_ENDPOINTS = {
    "na": "sellingpartnerapi-na.amazon.com",
    "eu": "sellingpartnerapi-eu.amazon.com",
    "fe": "sellingpartnerapi-fe.amazon.com",
}

MARKETPLACE_IDS = {
    "US": "ATVPDKIKX0DER",
    "CA": "A2EUQ1WTGCTBG2",
    "MX": "A1AM78C64UM0Y8",
    "DE": "A1PA6795UKMFR9",
    "FR": "A13V1IB3VIYZZH",
    "IT": "APJ6JRA9NG5V4",
    "ES": "A1RKKUPIHCS9HS",
    "UK": "A1F83G8C2ARO7P",
    "JP": "A1VC38T7YXB528",
}


class SPAPICredentialsMissing(Exception):
    """缺少 SP-API 凭据"""


@dataclass
class SPAPIConfig:
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    region: str = "na"
    marketplace_id: str = "ATVPDKIKX0DER"

    @classmethod
    def from_env(cls) -> "SPAPIConfig":
        return cls(
            client_id=os.getenv("SPAPI_CLIENT_ID", ""),
            client_secret=os.getenv("SPAPI_CLIENT_SECRET", ""),
            refresh_token=os.getenv("SPAPI_REFRESH_TOKEN", ""),
            region=os.getenv("SPAPI_REGION", "na"),
            marketplace_id=os.getenv("SPAPI_MARKETPLACE_ID", MARKETPLACE_IDS.get(
                os.getenv("SPAPI_MARKETPLACE", "US"), "ATVPDKIKX0DER")),
        )

    @property
    def available(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)


class SPAPIClient:
    """SP-API 客户端（LWA OAuth + 带 token 的 REST 调用）"""

    def __init__(self, config: Optional[SPAPIConfig] = None) -> None:
        self.cfg = config or SPAPIConfig.from_env()
        self._access_token: str = ""
        self._token_expires_at: float = 0.0
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def available(self) -> bool:
        return self.cfg.available

    async def close(self) -> None:
        await self._client.aclose()

    # ── OAuth ─────────────────────────────────────────────────────────────────
    async def _refresh_token(self) -> str:
        resp = await self._client.post(
            LWA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self.cfg.client_id,
                "client_secret": self.cfg.client_secret,
                "refresh_token": self.cfg.refresh_token,
            },
        )
        resp.raise_for_status()
        j = resp.json()
        self._access_token = j["access_token"]
        self._token_expires_at = time.time() + int(j.get("expires_in", 3600)) - 60
        return self._access_token

    async def _get_token(self) -> str:
        if not self._access_token or time.time() >= self._token_expires_at:
            return await self._refresh_token()
        return self._access_token

    # ── 通用请求 ───────────────────────────────────────────────────────────────
    async def _request(self, method: str, path: str, params: dict | None = None,
                       body: dict | None = None, retries: int = 3) -> dict:
        if not self.available:
            raise SPAPICredentialsMissing("SP-API 凭据未配置 (SPAPI_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN)")
        token = await self._get_token()
        host = _REGION_ENDPOINTS.get(self.cfg.region, _REGION_ENDPOINTS["na"])
        url = f"https://{host}{path}"
        headers = {
            "x-amz-access-token": token,
            "x-amz-date": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
            "content-type": "application/json",
        }
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                resp = await self._client.request(method, url, params=params, json=body, headers=headers)
                if resp.status_code in (429, 500, 502, 503):
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else (2 ** attempt)
                    await asyncio.sleep(min(wait, 30))
                    continue
                resp.raise_for_status()
                return resp.json() if resp.content else {}
            except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                    break
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"SP-API 请求失败 {method} {path}: {last_exc}")

    # ── 业务端点 ───────────────────────────────────────────────────────────────
    async def get_inventory_summaries(self) -> dict[str, Any]:
        """FBA 库存汇总（/fba/inventory/v1/summaries）"""
        return await self._request(
            "GET", "/fba/inventory/v1/summaries",
            params={"marketplaceIds": self.cfg.marketplace_id, "granularityType": "Marketplace"},
        )

    async def get_order_metrics(self, interval_days: int = 30) -> dict[str, Any]:
        """订单量指标（/sales/v1/orderMetrics）"""
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=interval_days)
        return await self._request(
            "GET", "/sales/v1/orderMetrics",
            params={
                "marketplaceIds": self.cfg.marketplace_id,
                "interval": f"{start.isoformat()}T00:00:00Z--{end.isoformat()}T00:00:00Z",
                "granularity": "Day",
            },
        )

    async def get_orders(self, days: int = 7, max_results: int = 100) -> dict[str, Any]:
        """近期订单（/orders/v0/orders）"""
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days)
        return await self._request(
            "GET", "/orders/v0/orders",
            params={
                "MarketplaceIds": self.cfg.marketplace_id,
                "CreatedAfter": f"{start.isoformat()}T00:00:00Z",
                "MaxResultsPerPage": max_results,
            },
        )
