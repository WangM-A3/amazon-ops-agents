"""
Amazon Operations Silicon Army
🎩 1个幕僚长 + 20个专业Agent | 企业级SaaS API Server
"""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ─── 日志 ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("amazon_ops")

# ─── 全局Agent注册（延迟导入避免循环） ───────────────────────────────────────
from agents.base import AGENT_REGISTRY, TASK_ROUTING, AGENTS  # noqa: E402
from agents.chief import CHIEF  # noqa: E402

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    """单任务执行请求"""
    task: str = Field(..., min_length=1, max_length=2000, description="自然语言任务描述")
    context: dict[str, Any] = Field(default_factory=dict, description="任务上下文")
    callback_url: str | None = Field(default=None, description="Webhook回调URL（异步完成后通知）")
    task_id: str = Field(default_factory=lambda: secrets.token_hex(8), description="任务ID")

class BatchRequest(BaseModel):
    """批量执行请求"""
    tasks: list[str] = Field(..., min_length=1, max_length=50, description="任务列表")
    parallel: bool = Field(default=True, description="是否并行执行")

class AgentListResponse(BaseModel):
    """Agent列表响应"""
    total: int
    agents: list[dict[str, Any]]

class ExecuteResponse(BaseModel):
    """执行响应"""
    task_id: str
    chief: str
    routed_agents: list[str]
    agent_count: int
    strategy: str
    results: dict[str, Any]
    total_tokens: int
    timestamp: str
    callback_url: str | None = None

class BatchResponse(BaseModel):
    """批量执行响应"""
    total: int
    task_id: str = Field(default_factory=lambda: secrets.token_hex(8))
    results: list[dict[str, Any]]

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    agents_registered: int
    uptime_seconds: float
    timestamp: str

# ─── 速率限制存储（内存，生产环境建议Redis） ───────────────────────────────────
class RateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}
        self._window = 60  # 1分钟窗口
        self._limit = 100  # 每窗口上限

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        if key not in self._requests:
            self._requests[key] = []
        # 清理过期记录
        self._requests[key] = [t for t in self._requests[key] if now - t < self._window]
        if len(self._requests[key]) >= self._limit:
            return False
        self._requests[key].append(now)
        return True


rate_limiter = RateLimiter()

# ─── 审计日志 ────────────────────────────────────────────────────────────────
audit_log: list[dict[str, Any]] = []


def audit(event: str, api_key: str, data: dict[str, Any]) -> None:
    """记录审计日志"""
    audit_log.append({
        "event": event,
        "api_key": api_key[:8] + "***",
        "time": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })
    # 只保留最近1000条
    if len(audit_log) > 1000:
        audit_log.pop(0)


# ─── OAuth 2.0 + API Key 认证 ────────────────────────────────────────────────
class AuthManager:
    """认证管理器：支持API Key和HMAC签名"""

    def __init__(self) -> None:
        # 存储已注册凭证 {api_key: {"secret": str, "tier": str, "name": str}}
        self._keys: dict[str, dict[str, str]] = {}
        self._webhook_secrets: dict[str, str] = {}  # callback_url -> secret
        self._load_env_keys()

    def _load_env_keys(self) -> None:
        # 从环境变量加载预置凭证（演示用，生产从数据库读取）
        if api_key := os.getenv("AMAZON_OPS_API_KEY"):
            secret = os.getenv("AMAZON_OPS_API_SECRET", "dev_secret_change_me")
            tier = os.getenv("AMAZON_OPS_TIER", "professional")
            name = os.getenv("AMAZON_OPS_CLIENT_NAME", "default_client")
            self._keys[api_key] = {"secret": secret, "tier": tier, "name": name}
            logger.info(f"[Auth] Loaded API key for: {name}")

    def verify_api_key(self, api_key: str) -> dict[str, str] | None:
        return self._keys.get(api_key)

    def verify_signature(
        self, api_key: str, signature: str, timestamp: str, body: bytes
    ) -> bool:
        key_info = self._keys.get(api_key)
        if not key_info:
            return False
        # HMAC-SHA256签名验证
        payload = f"{timestamp}.{body.decode('utf-8', errors='replace')}"
        expected = hmac.new(
            key_info["secret"].encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return secrets.compare_digest(expected, signature)

    def register_webhook(self, callback_url: str) -> str:
        secret = secrets.token_urlsafe(32)
        self._webhook_secrets[callback_url] = secret
        return secret

    def verify_webhook(self, callback_url: str, signature: str) -> bool:
        secret = self._webhook_secrets.get(callback_url, "")
        expected = hmac.new(secret.encode(), callback_url.encode(), hashlib.sha256).hexdigest()
        return secrets.compare_digest(expected, signature)

    def get_tier_limit(self, tier: str) -> int:
        return {"basic": 500, "professional": 5000, "enterprise": 99999999}.get(tier, 100)

    def register_key(self, api_key: str, secret: str, tier: str, name: str) -> None:
        self._keys[api_key] = {"secret": secret, "tier": tier, "name": name}


auth_manager = AuthManager()


async def require_auth(request: Request) -> dict[str, str]:
    """
    依赖注入：验证API Key
    - Header: X-API-Key: <key>
    - 可选签名: X-Signature: <hmac-sha256>  X-Timestamp: <unix>
    """
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MISSING_API_KEY", "message": "请提供 X-API-Key header"},
        )

    key_info = auth_manager.verify_api_key(api_key)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_API_KEY", "message": "API Key无效或已过期"},
        )

    # HMAC签名可选验证（提高安全性）
    signature = request.headers.get("X-Signature", "")
    timestamp = request.headers.get("X-Timestamp", "")
    if signature and timestamp:
        body = await request.body()
        if not auth_manager.verify_signature(api_key, signature, timestamp, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_SIGNATURE", "message": "签名验证失败"},
            )

    # 速率限制
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{api_key}"
    if not rate_limiter.is_allowed(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后再试"},
        )

    audit("api_call", api_key, {"path": request.url.path})
    return key_info


# ─── Webhook 回调 ─────────────────────────────────────────────────────────────
async def notify_callback(callback_url: str, task_id: str, result: dict[str, Any]) -> None:
    """异步通知Webhook"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                callback_url,
                json={
                    "event": "task_completed",
                    "task_id": task_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "result": result,
                },
                headers={"Content-Type": "application/json"},
            )
            logger.info(f"[Webhook] 回调 {callback_url} → {resp.status_code}")
    except Exception as exc:  # pragma: no cover
        logger.warning(f"[Webhook] 回调失败: {exc}")


# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="亚马逊运营硅基军团 API",
    description="1个幕僚长 + 20个专业Agent，企业级亚马逊运营AI平台",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动时间
START_TIME = time.time()

# ─── 路由 ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        agents_registered=len(AGENTS),
        uptime_seconds=round(time.time() - START_TIME, 1),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/v1/agents", response_model=AgentListResponse, tags=["Agent"])
async def list_agents(auth: dict = Depends(require_auth)) -> AgentListResponse:
    """列出所有已注册的Agent"""
    return AgentListResponse(
        total=len(AGENT_REGISTRY),
        agents=[
            {
                "id": info["id"],
                "name": info["name"],
                "emoji": info["emoji"],
                "description": info["description"],
                "capabilities": info["capabilities"],
            }
            for info in AGENT_REGISTRY.values()
        ],
    )


@app.get("/api/v1/routing", tags=["Agent"])
async def get_routing_table(auth: dict = Depends(require_auth)) -> dict[str, Any]:
    """获取关键词路由表"""
    return {
        "total_routes": len(TASK_ROUTING),
        "routing_table": TASK_ROUTING,
    }


@app.post("/api/v1/execute", response_model=ExecuteResponse, tags=["执行"])
async def execute_task(
    req: ExecuteRequest,
    request: Request,
    auth: dict = Depends(require_auth),
) -> ExecuteResponse:
    """
    主执行入口
    - 自然语言任务 → ChiefOfStaff调度 → Agent并行执行 → 聚合结果
    - 支持Webhook异步回调
    """
    logger.info(f"[Execute] task_id={req.task_id} | {req.task[:60]}")
    audit("task_execute", request.headers.get("X-API-Key", ""), {"task_id": req.task_id, "task": req.task})

    # 并行执行
    result = await CHIEF.execute(req.task, req.context)

    # 异步Webhook回调
    if req.callback_url:
        asyncio.create_task(notify_callback(req.callback_url, req.task_id, result))

    return ExecuteResponse(
        task_id=req.task_id,
        chief=result["chief"],
        routed_agents=result["routed_agents"],
        agent_count=result["agent_count"],
        strategy=result["strategy"],
        results=result["results"],
        total_tokens=result["total_tokens"],
        timestamp=result["timestamp"],
        callback_url=req.callback_url,
    )


@app.post("/api/v1/batch", response_model=BatchResponse, tags=["执行"])
async def batch_execute(
    req: BatchRequest,
    request: Request,
    auth: dict = Depends(require_auth),
) -> BatchResponse:
    """
    批量执行多个任务
    - parallel=True: 所有任务并行执行
    - parallel=False: 顺序执行
    """
    logger.info(f"[Batch] 执行 {len(req.tasks)} 个任务，parallel={req.parallel}")
    task_id = secrets.token_hex(8)

    if req.parallel:
        tasks = [CHIEF.execute(t, {}) for t in req.tasks]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        results_list = []
        for t in req.tasks:
            results_list.append(await CHIEF.execute(t, {}))

    # 清理异常
    cleaned = []
    for r in results_list:
        if isinstance(r, Exception):
            cleaned.append({"error": str(r)})
        else:
            cleaned.append({
                "input": r["input"],
                "routed_agents": r["routed_agents"],
                "results": r["results"],
                "tokens": r["total_tokens"],
            })

    return BatchResponse(total=len(req.tasks), task_id=task_id, results=cleaned)


@app.get("/api/v1/stats", tags=["系统"])
async def get_stats(auth: dict = Depends(require_auth)) -> dict[str, Any]:
    """系统统计"""
    total_invocations = sum(
        info["invoked_count"] for info in AGENT_REGISTRY.values()
    )
    return {
        "total_agents": len(AGENTS),
        "total_invocations": total_invocations,
        "total_tokens_consumed": sum(
            info["total_tokens"] for info in AGENT_REGISTRY.values()
        ),
        "top_agents": sorted(
            AGENT_REGISTRY.values(), key=lambda x: x["invoked_count"], reverse=True
        )[:5],
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "audit_log_entries": len(audit_log),
    }


@app.get("/api/v1/audit", tags=["系统"])
async def get_audit_log(
    limit: int = 100,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """审计日志（最近N条）"""
    return {"total": len(audit_log), "entries": audit_log[-limit:]}


# ─── 错误处理 ────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"[Unhandled] {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请联系技术支持",
            "detail": str(exc) if os.getenv("DEBUG") else None,
        },
    )


# ─── 启动入口 ────────────────────────────────────────────────────────────────
def main() -> None:
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true",
        workers=1,  # 开发模式单进程
        log_level="info",
    )


if __name__ == "__main__":
    main()
