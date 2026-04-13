"""
Amazon Operations Silicon Army - Python SDK Client
企业级Python客户端，支持同步/异步API调用、Webhook、OAuth
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
from typing import Any, Optional

import httpx

__version__ = "1.0.0"


class AmazonOpsClient:
    """
    亚马逊运营硅基军团 Python SDK

    用法:
        client = AmazonOpsClient(api_key="xxx", secret="xxx")

        # 同步
        result = client.execute("帮我分析这款无线蓝牙耳机的市场机会")

        # 异步
        result = await client.execute_async("帮我分析选品")
    """

    def __init__(
        self,
        api_key: str | None = None,
        secret: str | None = None,
        base_url: str = "http://localhost:8080",
        timeout: float = 30.0,
        auto_sign: bool = True,
    ) -> None:
        self.api_key = api_key or os.getenv("AMAZON_OPS_API_KEY", "")
        self.secret = secret or os.getenv("AMAZON_OPS_API_SECRET", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auto_sign = auto_sign
        self._client: httpx.AsyncClient | None = None

    def _sign(self, timestamp: str, body: str) -> str:
        """HMAC-SHA256签名"""
        payload = f"{timestamp}.{body}"
        return hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self, body: str = "") -> dict[str, str]:
        """构建认证Header"""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.auto_sign and self.secret and body:
            timestamp = str(int(time.time()))
            headers["X-Timestamp"] = timestamp
            headers["X-Signature"] = self._sign(timestamp, body)
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._headers(),
            )
        return self._client

    # ─── 核心API ────────────────────────────────────────────────────────────

    async def execute_async(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        callback_url: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """
        异步执行单个任务
        """
        body = {
            "task": task,
            "context": context or {},
            **( {"callback_url": callback_url} if callback_url else {}),
            **( {"task_id": task_id} if task_id else {}),
        }
        import json
        body_str = json.dumps(body, ensure_ascii=False)
        client = await self._get_client()
        resp = await client.post(
            "/api/v1/execute",
            content=body_str,
            headers=self._headers(body_str),
        )
        resp.raise_for_status()
        return resp.json()

    def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        """
        同步执行单个任务（内部异步包装）
        """
        return asyncio.run(self.execute_async(task, context, callback_url))

    async def batch_execute_async(
        self,
        tasks: list[str],
        parallel: bool = True,
    ) -> dict[str, Any]:
        """异步批量执行"""
        import json
        body = json.dumps({"tasks": tasks, "parallel": parallel}, ensure_ascii=False)
        client = await self._get_client()
        resp = await client.post(
            "/api/v1/batch",
            content=body,
            headers=self._headers(body),
        )
        resp.raise_for_status()
        return resp.json()

    def batch_execute(
        self,
        tasks: list[str],
        parallel: bool = True,
    ) -> dict[str, Any]:
        """同步批量执行"""
        return asyncio.run(self.batch_execute_async(tasks, parallel))

    # ─── 查询类API ────────────────────────────────────────────────────────────

    async def list_agents_async(self) -> dict[str, Any]:
        """异步获取Agent列表"""
        client = await self._get_client()
        resp = await client.get("/api/v1/agents", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def list_agents(self) -> dict[str, Any]:
        """同步获取Agent列表"""
        return asyncio.run(self.list_agents_async())

    async def health_check_async(self) -> dict[str, Any]:
        """异步健康检查"""
        client = await self._get_client()
        resp = await client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> dict[str, Any]:
        """同步健康检查"""
        return asyncio.run(self.health_check_async())

    async def get_stats_async(self) -> dict[str, Any]:
        """异步获取系统统计"""
        client = await self._get_client()
        resp = await client.get("/api/v1/stats", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_stats(self) -> dict[str, Any]:
        """同步获取系统统计"""
        return asyncio.run(self.get_stats_async())

    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def __aenter__(self) -> "AmazonOpsClient":
        return self

    def __aexit__(self, *args: Any) -> None:
        asyncio.run(self.close())

    # ─── 便捷方法 ─────────────────────────────────────────────────────────────

    async def product_research_async(self, product: str, marketplace: str = "US") -> dict[str, Any]:
        """选品分析快捷方法"""
        return await self.execute_async(
            f"帮我分析这个产品能不能做：{product}，目标市场：{marketplace}"
        )

    async def optimize_listing_async(self, asin: str, current_listing: str = "") -> dict[str, Any]:
        """Listing优化快捷方法"""
        return await self.execute_async(
            f"优化以下Amazon Listing：ASIN={asin}\n当前内容：{current_listing}"
        )

    async def optimize_ppc_async(self, sku: str, target_acos: float = 25.0) -> dict[str, Any]:
        """广告优化快捷方法"""
        return await self.execute_async(
            f"分析广告数据并优化：SKU={sku}，目标ACOS={target_acos}%"
        )

    async def reply_review_async(self, asin: str, review_text: str, rating: int) -> dict[str, Any]:
        """差评回复快捷方法"""
        return await self.execute_async(
            f"收到{rating}星评论，内容：{review_text}\nASIN={asin}，如何回复？"
        )

    async def check_profit_async(self, sku: str, selling_price: float) -> dict[str, Any]:
        """利润计算快捷方法"""
        return await self.execute_async(
            f"计算SKU={sku}，售价${selling_price}的利润和ROI"
        )


# ─── CLI入口 ──────────────────────────────────────────────────────────────────
def main() -> None:
    import argparse, json, sys

    parser = argparse.ArgumentParser(description="Amazon Ops Silicon Army CLI")
    parser.add_argument("--api-key", default=os.getenv("AMAZON_OPS_API_KEY"))
    parser.add_argument("--secret", default=os.getenv("AMAZON_OPS_API_SECRET"))
    parser.add_argument("--base-url", default=os.getenv("AMAZON_OPS_BASE_URL", "http://localhost:8080"))
    parser.add_argument("task", nargs="+", help="要执行的任务")
    args = parser.parse_args()

    client = AmazonOpsClient(
        api_key=args.api_key,
        secret=args.secret,
        base_url=args.base_url,
        auto_sign=False,
    )

    task_text = " ".join(args.task)
    print(f"📤 执行: {task_text}")

    try:
        result = client.execute(task_text)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"❌ 错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
