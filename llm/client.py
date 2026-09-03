"""
llm/client.py — OpenAI 兼容 LLM 客户端（真实调用）
=====================================================
SMALL/LARGE 引擎的落地实现。支持任何 OpenAI 兼容端点（DeepSeek / OpenAI / 本地代理）：

环境变量（优先级 DEEPSEEK_* > OPENAI_* > 内置默认）：
- DEEPSEEK_BASE_URL / DEEPSEEK_API_KEY / DEEPSEEK_MODEL
- OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL
- 默认 base_url: https://api.deepseek.com/v1, model: deepseek-chat

未配置 base_url 时 available=False，调用方回退到模板引擎。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger("amazon_ops.llm")

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class LLMClient:
    """OpenAI 兼容 chat completions 客户端（httpx 直连，无 SDK 依赖）"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 90.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL")
                         or os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.base_url)

    async def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> tuple[str, dict[str, int]]:
        """返回 (文本内容, usage)"""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
            j = resp.json()
        content = j["choices"][0]["message"]["content"]
        usage = j.get("usage", {})
        logger.debug(f"[LLM] model={self.model} tokens={usage.get('total_tokens')}")
        return content, {"prompt_tokens": usage.get("prompt_tokens", 0),
                         "completion_tokens": usage.get("completion_tokens", 0),
                         "total_tokens": usage.get("total_tokens", 0)}

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """要求模型返回 JSON 对象，解析失败抛 ValueError"""
        content, usage = await self.chat(messages, json_mode=True, max_tokens=max_tokens)
        # 容错：去掉 ```json ``` 包裹
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(cleaned), usage


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def reset_llm_client() -> None:
    global _client
    _client = None
