"""
Amazon Operations Silicon Army - ChiefOfStaff (Tracing 集成版)
在每个任务执行周期自动创建 TraceContext 并记录所有 Agent 调用。
支持手动传入 trace_id 实现跨请求链路追踪。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from .base import AGENTS, TASK_ROUTING

logger = logging.getLogger("amazon_ops")

# ─── Tracing 懒加载 ───────────────────────────────────────────────────────────
_tracing_module: Any = None


def _get_tracing_module():
    global _tracing_module
    if _tracing_module is None:
        try:
            from tracing import TraceContext, SpanStatus, SpanType, audit_log
            _tracing_module = (TraceContext, SpanStatus, SpanType, audit_log)
        except ImportError:
            _tracing_module = ()
    return _tracing_module


class ChiefOfStaff:
    """
    幕僚长 - 智能任务调度中心（Tracing 集成版）

    新增能力：
    - 每个 execute() 自动创建 TraceContext
    - 每个 Agent 调用记录独立 span
    - 执行完成后自动 flush 到 AuditTrail
    - 支持 trace_id 跨请求传播（HTTP header / 消息队列）
    """

    def __init__(self) -> None:
        self.name = "ChiefOfStaff"
        self.emoji = "🎩"
        self._router = None
        self._executor = None

    @property
    def router(self):
        if self._router is None:
            from routing import ROUTER
            self._router = ROUTER
        return self._router

    @property
    def executor(self):
        if self._executor is None:
            from routing import EXECUTOR
            self._executor = EXECUTOR
        return self._executor

    def route(self, task: str) -> list[str]:
        task_lower = task.lower()
        scores: dict[str, int] = {}

        for agent_id, keywords in TASK_ROUTING.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[agent_id] = scores.get(agent_id, 0) + score

        for agent_id, agent in AGENTS.items():
            if agent_id in scores:
                continue
            capabilities = getattr(agent, "capabilities", []) or []
            score = sum(1 for kw in capabilities if kw in task_lower)
            if score > 0:
                scores[agent_id] = score

        if not scores:
            logger.info(f"[ChiefOfStaff] 未匹配到Agent，使用默认：sales_analytics")
            return ["sales_analytics"]

        routed = sorted(scores, key=scores.get, reverse=True)
        logger.info(f"[ChiefOfStaff] 路由 {routed} | 任务: {task[:50]}")
        return routed

    async def execute(
        self,
        task: str,
        context: Optional[dict[str, Any]] = None,
        trace_id: str | None = None,
        trace_root_name: str | None = None,
    ) -> dict[str, Any]:
        """
        智能执行（Tracing 全链路记录版）

        新增参数：
        - trace_id       : 外部传入的 trace_id（支持跨请求传播）
        - trace_root_name: trace 根名称（用于日志可见性）

        Returns: 同原版，末尾追加 trace_id
        """
        tm = _get_tracing_module()
        trace_ctx: Any = None  # 初始化为 None，finally 中保证已定义

        # ── 创建 / 恢复 TraceContext ──────────────────────────────────────────
        if tm:
            TraceContext_cls, SpanStatus_cls, SpanType_cls, _ = tm
            trace_ctx = TraceContext_cls.start(
                name=trace_root_name or f"chief[{task[:30]}]",
                trace_id=trace_id,
            )
            scope = trace_ctx.span(
                "ChiefOfStaff.execute", SpanType_cls.CHIEF,
                input_summary=task[:200],
            )
            root_span = scope._span
        else:
            root_span = None

        try:
            # ── 核心执行逻辑（保持不变）────────────────────────────────────────
            routed = self.route(task)
            context = context or {}

            # TaskRouter 决策
            routing_decision = self.router.route(task, routed)
            engine = routing_decision.engine
            context["_routing"] = {
                "engine": engine.value,
                "complexity_score": routing_decision.complexity_score,
                "estimated_tokens": routing_decision.estimated_tokens,
                "reasoning": routing_decision.reasoning,
                "fallback": routing_decision.fallback.value
                    if routing_decision.fallback else None,
            }

            # ── LOCAL 引擎 ────────────────────────────────────────────────────
            if engine.value == "local":
                logger.info("[ChiefOfStaff] → 本地执行引擎（零Token消耗）")
                local_result = self.executor.execute(task, context)

                if tm and trace_ctx:
                    trace_ctx.record_executor(task, local_result, local_result.success)

                response: dict[str, Any] = {
                    "chief": f"{self.emoji} {self.name}",
                    "input": task,
                    "routing": context["_routing"],
                    "routed_agents": [],
                    "agent_count": 0,
                    "strategy": "local",
                    "results": {
                        "local": {
                            "success": local_result.success,
                            "data": local_result.data,
                            "message": local_result.message,
                            "error": local_result.error,
                        }
                    },
                    "total_tokens": 0,
                    "timestamp": datetime.now().isoformat(),
                    "trace_id": trace_ctx.trace_id if trace_ctx else None,
                }

                if root_span is not None:
                    root_span.finish(output_summary="local, tokens=0")

                return response

            # ── SMALL/LARGE 引擎 ─────────────────────────────────────────────
            async def run_one(aid: str) -> tuple[str, dict[str, Any]]:
                if aid not in AGENTS:
                    logger.warning(f"[ChiefOfStaff] Agent不存在: {aid}")
                    return aid, {"error": f"Agent '{aid}' not found in registry"}

                agent_span: Any = None
                if tm and trace_ctx:
                    agent_scope = trace_ctx.span(
                        f"Agent.{aid}", SpanType_cls.AGENT,
                        input_summary=task[:200],
                        metadata={"agent_id": aid},
                    )
                    agent_span = agent_scope._span

                try:
                    result = await AGENTS[aid].execute(task, context)
                    tokens = result.get("tokens", 0) if isinstance(result, dict) else 0

                    if agent_span is not None:
                        agent_span.finish(
                            output_summary=str(result)[:200],
                            metadata={"tokens": tokens},
                        )
                        trace_ctx.record_agent(
                            aid, task, result, tokens=tokens, success=True,
                        )

                    return aid, result

                except Exception as exc:
                    err_str = str(exc)
                    logger.error(f"[ChiefOfStaff] Agent执行失败 {aid}: {exc}")

                    if agent_span is not None:
                        status_cls = SpanStatus_cls
                        agent_span.finish(status=status_cls.ERROR, error=err_str)
                        trace_ctx.record_agent(
                            aid, task, None, tokens=0, success=False, error=err_str,
                        )

                    return aid, {"error": err_str}

            results_list = await asyncio.gather(
                *[run_one(a) for a in routed], return_exceptions=True
            )

            results: dict[str, Any] = {}
            for item in results_list:
                if isinstance(item, Exception):
                    continue
                aid, res = item
                results[aid] = res if isinstance(res, dict) and "error" not in res \
                    else {"error": str(res)}

            total_tokens = sum(r.get("tokens", 0) for r in results.values())

            response = {
                "chief": f"{self.emoji} {self.name}",
                "input": task,
                "routing": context["_routing"],
                "routed_agents": routed,
                "agent_count": len(routed),
                "strategy": "parallel" if len(routed) > 1 else "single",
                "results": results,
                "total_tokens": total_tokens,
                "timestamp": datetime.now().isoformat(),
                "trace_id": trace_ctx.trace_id if trace_ctx else None,
            }

            if root_span is not None:
                root_span.finish(output_summary=f"agents={routed} tokens={total_tokens}")

            return response

        finally:
            # ── 强制 flush（trace_ctx 可能为 None，但 try-except 安全处理）───
            if trace_ctx is not None:
                summary = trace_ctx.flush()
                if summary.get("error_count", 0) > 0:
                    logger.warning(
                        f"[ChiefOfStaff] trace_id={trace_ctx.trace_id} "
                        f"finished with {summary['error_count']} errors"
                    )
                trace_ctx.close()

    def plan(self, task: str) -> dict[str, Any]:
        """仅做路由规划，不执行"""
        routed = self.route(task)
        decision = self.router.route(task, routed)

        workflow_candidates = []
        from workflows import PRESET_WORKFLOWS
        for wf_id, wf in PRESET_WORKFLOWS.items():
            if any(step.agent_id in routed for step in wf.steps):
                workflow_candidates.append({
                    "id": wf_id,
                    "name": wf.name,
                    "emoji": wf.emoji,
                    "steps_count": len(wf.steps),
                    "estimated_seconds": wf.estimated_total_seconds,
                })

        return {
            "routing": {
                "engine": decision.engine.value,
                "complexity_score": decision.complexity_score,
                "estimated_tokens": decision.estimated_tokens,
                "reasoning": decision.reasoning,
                "fallback": decision.fallback.value
                    if decision.fallback else None,
            },
            "candidate_agents": routed,
            "workflow_candidates": workflow_candidates,
        }


CHIEF = ChiefOfStaff()
