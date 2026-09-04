"""
Amazon Operations Silicon Army
🎩 1个幕僚长 + 20个专业Agent | 企业级SaaS API Server
"""

import asyncio
import contextvars
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

class WorkflowRequest(BaseModel):
    """工作流请求"""
    workflow_id: str = Field(..., min_length=1, description="预置工作流ID")
    input: dict[str, Any] = Field(default_factory=dict, description="工作流输入参数")

class WorkflowResponse(BaseModel):
    """工作流响应（v2.3 含复核沙箱 reviews）"""
    workflow_id: str
    status: str
    error: str | None = None
    step_results: dict[str, Any]
    total_seconds: float
    estimated_vs_actual: dict[str, int] = Field(default_factory=dict)
    run_id: str | None = None
    reviews: dict[str, Any] = Field(default_factory=dict)

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

# ─── Tracing 全局入口（Tracing 集成版） ──────────────────────────────────────
# 支持 Tracing 的 API Server
# 特性：
# 1. 失败时自动创建 TraceContext，记录错误 span
# 2. 所有 500 错误响应携带 trace_id
# 3. 支持从 HTTP Header 传入外部 trace_id（X-Trace-ID）
# 4. 支持用户反馈时附带 trace_id（feedback endpoint）

_trace_ctx_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_trace_ctx", default=None
)  # 存储 {"trace_id": str, "scope": _SpanScope, "ctx": TraceContext}


def _start_request_trace(
    request: Request,
    root_name: str | None = None,
) -> Any | None:
    """
    为每个请求启动 trace 上下文。

    优先使用 X-Trace-ID header（外部传入），否则自动生成。
    返回 TraceContext 实例（未 flush）。
    """
    try:
        from tracing import TraceContext, SpanType
    except ImportError:
        return None

    # 优先从 header 获取外部 trace_id
    incoming_trace = request.headers.get("X-Trace-ID")
    root = root_name or f"{request.method} {request.url.path}"

    ctx = TraceContext.start(name=root, trace_id=incoming_trace)

    # 创建 root span
    scope = ctx.span("HTTP.request", SpanType.ROOT, input_summary=root)
    token = _trace_ctx_var.set({"trace_id": ctx.trace_id, "ctx": ctx, "scope": scope})
    ctx._token = token  # 保留 token，方便 close

    logger.info(f"[Trace] trace_id={ctx.trace_id} start | {root[:50]}")
    return ctx


def _get_request_trace_id() -> str | None:
    """获取当前请求的 trace_id（若有）"""
    info = _trace_ctx_var.get()
    return info["trace_id"] if info else None


def _finish_request_trace(
    error: Exception | None = None,
    extra: str | None = None,
) -> dict[str, Any] | None:
    """
    结束请求 trace，记录错误（如有）并 flush 到审计日志。

    调用时机：
    - 正常响应路径：响应发送前
    - 异常路径：global_exception_handler 中

    Returns:
        {"trace_id": str, "summary": dict} 或 None
    """
    info = _trace_ctx_var.get()
    if info is None:
        return None

    ctx = info["ctx"]
    trace_id = ctx.trace_id

    try:
        if error:
            try:
                from tracing.trace_context import SpanType
                st = SpanType.STEP
            except Exception:
                st = type("SpanTypeStep", (), {"value": "step"})()
            ctx.record_error(
                "HTTP.exception",
                error=str(error)[:500],
                span_type=st,
            )
            logger.warning(f"[Trace] trace_id={trace_id} recorded error: {error}")

        if extra:
            try:
                from tracing.trace_context import SpanType
                st = SpanType.STEP
            except Exception:
                st = type("SpanTypeStep", (), {"value": "step"})()
            scope = ctx.span("HTTP.finish", st)
            scope._span.finish(output_summary=extra[:200])

        summary = ctx.flush()
    finally:
        try:
            _trace_ctx_var.reset(info.get("ctx")._token)
        except Exception:
            pass
        ctx.close()

    return {"trace_id": trace_id, "summary": summary}


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

    # v2.1 经验记忆闭环：记录本次命中的经验 id，供 /memory/rating 评分回写
    _record_experience_hits(req.task_id, result)

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


@app.get("/api/v1/workflows", tags=["工作流"])
async def list_workflows(auth: dict = Depends(require_auth)) -> dict[str, Any]:
    """列出全部预置工作流"""
    from workflows.presets import WORKFLOW_ENGINE
    return {"total": len(WORKFLOW_ENGINE.list_workflows()), "workflows": WORKFLOW_ENGINE.list_workflows()}


@app.post("/api/v1/workflow", response_model=WorkflowResponse, tags=["工作流"])
async def run_workflow(
    req: WorkflowRequest,
    request: Request,
    auth: dict = Depends(require_auth),
) -> WorkflowResponse:
    """一键启动预置工作流（v2.3：响应含 run_id + 待复核 reviews 清单）"""
    logger.info(f"[Workflow] {req.workflow_id} | input={str(req.input)[:80]}")
    audit("workflow_run", request.headers.get("X-API-Key", ""), {"workflow_id": req.workflow_id})
    from workflows.presets import WORKFLOW_ENGINE
    from workflows.review_gate import REVIEW_GATE, new_run_id

    result = await WORKFLOW_ENGINE.launch(req.workflow_id, req.input)
    # v2.3：登记待复核步骤（review_required=True 的产物）
    run_id = new_run_id()
    if result.reviews:
        REVIEW_GATE.register(run_id, req.workflow_id, result.reviews)
    return WorkflowResponse(
        workflow_id=result.workflow_id,
        status=result.status.value,
        error=result.error,
        step_results=result.step_results,
        total_seconds=result.total_seconds,
        estimated_vs_actual=result.estimated_vs_actual,
        run_id=run_id,
        reviews=result.reviews,
    )


class WorkflowReviewRequest(BaseModel):
    """工作流步骤复核决策（v2.3）"""
    run_id: str = Field(..., min_length=1, description="工作流运行的 run_id")
    step_key: str = Field(..., min_length=1, description="待复核步骤的 output_key")
    decision: str = Field(..., pattern="^(approve|reject)$", description="approve=采纳 / reject=不采纳")
    comment: str = Field(default="", max_length=500, description="复核备注")


@app.post("/api/v1/workflow/review", tags=["工作流"])
async def review_workflow_step(
    req: WorkflowReviewRequest,
    request: Request,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """人工复核工作流步骤产物（approve 后该建议才视为可采纳）"""
    from workflows.review_gate import REVIEW_GATE
    item = REVIEW_GATE.decide(
        req.run_id, req.step_key, req.decision,
        comment=req.comment, reviewer=auth.get("name", "seller"),
    )
    if item is None:
        raise HTTPException(status_code=404, detail={
            "code": "NOT_FOUND",
            "message": f"run_id={req.run_id} 的步骤 {req.step_key} 不存在或已过期",
        })
    audit("workflow_review", request.headers.get("X-API-Key", ""),
          {"run_id": req.run_id, "step_key": req.step_key, "decision": req.decision})
    return {"status": "reviewed", "item": item}


@app.get("/api/v1/workflow/review/{run_id}", tags=["工作流"])
async def review_status(
    run_id: str,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """查询一次工作流运行的复核状态（全部步骤的 decision）"""
    from workflows.review_gate import REVIEW_GATE
    return REVIEW_GATE.status(run_id)


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


# ─── 错误处理（Tracing 集成版） ───────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理（Tracing 集成版）

    特性：
    1. 尝试复用当前请求的 TraceContext，记录 error span
    2. 如果没有 TraceContext（异常发生在中间件层之前），自动创建
    3. 响应 JSON 中附加 trace_id，方便用户反馈
    """
    trace_id: str | None = None

    # 尝试从当前 trace 上下文获取 trace_id
    try:
        trace_result = _finish_request_trace(error=exc)
        if trace_result:
            trace_id = trace_result["trace_id"]
            summary = trace_result.get("summary", {})
            error_count = summary.get("error_count", 0)
            logger.warning(
                f"[Trace] global_exception_handler recorded error "
                f"trace_id={trace_id} errors={error_count}"
            )
    except Exception as trace_err:
        logger.error(f"[Trace] _finish_request_trace failed: {trace_err}")

    # 如果没有获取到 trace_id（异常发生在 tracing 初始化前），创建一个最小 trace
    if not trace_id:
        try:
            ctx = _start_request_trace(request)
            if ctx:
                trace_id = ctx.trace_id
                ctx.record_error("HTTP.exception_early", exc)
                ctx.flush()
                ctx.close()
        except Exception:
            pass

    logger.error(f"[Unhandled] {exc}", exc_info=True)

    content = {
        "code": "INTERNAL_ERROR",
        "message": "服务器内部错误，请联系技术支持",
        "trace_id": trace_id,  # ← 关键：告知用户此 ID 用于反馈
    }
    if os.getenv("DEBUG"):
        content["detail"] = str(exc)

    return JSONResponse(status_code=500, content=content)


# ─── 经验记忆闭环 API（v2.1）────────────────────────────────────────────────
# 最近的执行结果 → 命中经验映射（task_id -> exp ids），供评分回写；环形上限 500
_RECENT_HITS: dict[str, list[int]] = {}
_RECENT_HITS_MAX = 500


def _record_experience_hits(task_id: str, chief_result: dict[str, Any]) -> None:
    """从 ChiefOfStaff 结果中收集各 Agent 命中的经验 id"""
    hits: list[int] = []
    for r in chief_result.get("results", {}).values():
        if not isinstance(r, dict):
            continue
        for e in r.get("experience_used") or []:
            if isinstance(e, dict) and e.get("id"):
                hits.append(int(e["id"]))
    if not hits:
        return
    _RECENT_HITS[task_id] = sorted(set(hits))
    if len(_RECENT_HITS) > _RECENT_HITS_MAX:
        for stale in list(_RECENT_HITS)[:_RECENT_HITS_MAX // 5]:
            _RECENT_HITS.pop(stale, None)


class ExperienceCreate(BaseModel):
    """新增一条运营经验"""
    agent_id: str = Field(..., min_length=1, description="目标 Agent id，如 ppc_manager")
    title: str = Field(..., min_length=1, max_length=200, description="经验标题")
    content: str = Field(..., min_length=1, max_length=4000, description="经验/修正策略正文")
    keywords: list[str] = Field(default_factory=list, max_length=50, description="触发关键词（命中任务文本才注入）")


class RatingRequest(BaseModel):
    """给命中经验打分（1-5）"""
    task_id: str | None = Field(None, description="执行响应的 task_id（自动定位该任务命中的经验）")
    experience_ids: list[int] | None = Field(None, description="或直接指定经验 id 列表")
    rating: int = Field(..., ge=1, le=5, description="1=没用 2=较差 3=一般 4=有用 5=非常好")


@app.post("/api/v1/memory/experience", tags=["经验记忆"])
async def create_experience_api(
    req: ExperienceCreate,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """沉淀一条经验：告诉系统「以后这类任务要这样做」"""
    from memory.experience_store import create_experience
    exp = create_experience(req.agent_id, req.title, req.content, req.keywords)
    audit("memory_create", auth.get("name", "unknown"),
          {"agent_id": req.agent_id, "exp_id": exp["id"], "title": req.title})
    return {"status": "created", "experience": exp}


@app.get("/api/v1/memory/experience", tags=["经验记忆"])
async def list_experience_api(
    agent_id: str | None = None,
    include_inactive: bool = False,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """列出经验库（可按 Agent 过滤）"""
    from memory.experience_store import list_experiences
    items = list_experiences(agent_id=agent_id, include_inactive=include_inactive)
    return {"total": len(items), "experiences": items}


@app.post("/api/v1/memory/experience/{exp_id}/deactivate", tags=["经验记忆"])
async def deactivate_experience_api(
    exp_id: int,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """手动停用一条经验（不再注入）"""
    from memory.experience_store import deactivate_experience
    ok = deactivate_experience(exp_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"经验 #{exp_id} 不存在"})
    return {"status": "deactivated", "exp_id": exp_id}


@app.post("/api/v1/memory/rating", tags=["经验记忆"])
async def rate_experience_api(
    req: RatingRequest,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """给命中经验打分 → 正/负反馈统计 → 低成功率经验自动停用（闭环收口）"""
    from memory.experience_store import apply_rating
    exp_ids: list[int] = []
    if req.task_id and req.task_id in _RECENT_HITS:
        exp_ids = _RECENT_HITS[req.task_id]
    if req.experience_ids:
        exp_ids = [int(i) for i in req.experience_ids]
    if not exp_ids:
        raise HTTPException(status_code=404, detail={
            "code": "NO_EXPERIENCE",
            "message": "该任务未命中任何经验，或 task_id 已过期；请用 experience_ids 指定",
        })
    updated = []
    for eid in exp_ids:
        try:
            updated.append(apply_rating(eid, req.rating))
        except KeyError:
            continue
    if not updated:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "经验不存在"})
    return {"status": "rated", "rating": req.rating, "updated": updated}


# ─── 用户反馈接口 ────────────────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    """用户反馈模型"""
    trace_id: str | None = Field(None, description="发生问题的 trace_id（可选）")
    description: str = Field(..., min_length=10, max_length=2000, description="问题描述")
    contact: str | None = Field(None, description="联系方式（可选）")
    tags: list[str] = Field(default_factory=list, description="标签")


class FeedbackResponse(BaseModel):
    feedback_id: str
    trace_id: str | None
    status: str
    message: str


@app.post("/api/v1/feedback", response_model=FeedbackResponse, tags=["系统"])
async def submit_feedback(
    req: FeedbackRequest,
    auth: dict = Depends(require_auth),
) -> FeedbackResponse:
    """
    用户反馈接口

    功能：
    - 接收用户反馈，自动关联 trace_id 进行根因分析
    - 如果提供了 trace_id，自动查询并附加 trace 摘要到反馈记录
    - 存储反馈（内存 + 可扩展到数据库）

    用户操作流程：
    1. 遇到问题时，复制响应中的 trace_id
    2. 访问反馈接口，粘贴 trace_id 并描述问题
    3. 运维团队使用 trace_id 快速定位根因
    """
    feedback_id = secrets.token_hex(8)

    # 附加 trace 信息（如果有 trace_id）
    trace_info: dict[str, Any] | None = None
    if req.trace_id:
        try:
            trace_info = audit_log.get_trace(req.trace_id) if hasattr(audit_log, "get_trace") else None
            if trace_info is None:
                # fallback: 直接查询
                try:
                    from tracing.trace_query import query as trace_query
                    trace_info = trace_query.trace_full_chain(req.trace_id)
                except Exception:
                    trace_info = None
        except Exception:
            trace_info = None

    # 记录反馈到审计日志
    audit(
        event="user_feedback",
        api_key=auth.get("name", "unknown"),
        data={
            "feedback_id": feedback_id,
            "trace_id": req.trace_id,
            "description": req.description,
            "contact": req.contact,
            "tags": req.tags,
            "trace_summary": trace_info.get("summary") if trace_info else None,
        },
    )

    # 如果提供了 trace_id，输出 trace 摘要到日志
    if req.trace_id and trace_info:
        try:
            from tracing.trace_query import TraceQuery
            tq = TraceQuery()
            result = tq.trace_full_chain(req.trace_id)
            logger.info(
                f"[Feedback] trace_id={req.trace_id} | "
                f"spans={result.total_spans} | "
                f"errors={result.error_count} | "
                f"duration={result.total_ms:.0f}ms"
            )
        except Exception:
            pass

    return FeedbackResponse(
        feedback_id=feedback_id,
        trace_id=req.trace_id,
        status="received",
        message="反馈已收到，我们会尽快处理。如有 trace_id，我们会根据链路记录进行根因分析。",
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
