"""
workflows/review_gate.py — 步骤复核闸门（v2.3）
==================================================
映射 WeKnora v0.8「工具级人工审批 require_approval + pending」到工作流语境：
- 工作流中 review=True 的步骤产物 → 进入待复核队列（pending）
- 卖家逐条 approve / reject + 备注 → 记录审计轨迹
- 全部产物默认只读建议；reject 即"不采纳"，不会自动触发任何外部动作

设计取舍：amazon-ops 是单机引擎（卖家一键包无 Docker），
不引入容器沙箱；"沙箱"语义 = 产物隔离校验（presets._sandbox_step）
+ 本复核门 + 全链路审计。复核状态存进程内存 + 审计落 audit_log。
"""
from __future__ import annotations

import logging
import secrets
import threading
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("amazon_ops.review_gate")

# 内存运行上限，防膨胀
_MAX_RUNS = 200


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _audit(event: str, data: dict[str, Any]) -> None:
    """写入审计（tracing.audit_log 可用则落盘，否则仅日志）"""
    try:
        from tracing import audit_log
        audit_log(event, "review_gate", data)
    except Exception:  # noqa: BLE001
        logger.info(f"[ReviewGate] {event} {data}")


class ReviewGate:
    """工作流步骤复核闸门（run_id → {step_key: review item}）"""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    # ── 登记 ────────────────────────────────────────────────────────────────
    def register(
        self,
        run_id: str,
        workflow_id: str,
        reviews: dict[str, dict[str, Any]],
    ) -> None:
        """登记一次工作流运行中所有待复核步骤"""
        pending = {
            step_key: {
                "run_id": run_id,
                "workflow_id": workflow_id,
                "step_key": step_key,
                "step": info.get("step", step_key),
                "agent_id": info.get("agent_id", ""),
                "risk": info.get("risk", "low"),
                "reason": info.get("reason", ""),
                "preview": info.get("preview", ""),
                "validated": info.get("validated", True),
                "missing": info.get("missing", []),
                "decision": "pending",
                "decided_at": None,
                "comment": "",
                "reviewer": "",
            }
            for step_key, info in reviews.items()
            if info.get("review_required")
        }
        with self._lock:
            self._runs[run_id] = pending
            if len(self._runs) > _MAX_RUNS:
                for stale in list(self._runs)[:_MAX_RUNS // 4]:
                    self._runs.pop(stale, None)
        if pending:
            logger.info(
                f"[ReviewGate] run_id={run_id} 登记 {len(pending)} 项待复核"
            )
            _audit("review_register", {"run_id": run_id, "workflow_id": workflow_id,
                                       "count": len(pending)})

    # ── 查询 ────────────────────────────────────────────────────────────────
    def pending(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id, {})
            return [v for v in run.values() if v["decision"] == "pending"]

    def status(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._runs.get(run_id, {})
        items = list(run.values())
        return {
            "run_id": run_id,
            "total": len(items),
            "pending": sum(1 for i in items if i["decision"] == "pending"),
            "approved": sum(1 for i in items if i["decision"] == "approved"),
            "rejected": sum(1 for i in items if i["decision"] == "rejected"),
            "items": items,
        }

    # ── 决策 ────────────────────────────────────────────────────────────────
    def decide(
        self,
        run_id: str,
        step_key: str,
        decision: str,
        comment: str = "",
        reviewer: str = "seller",
    ) -> Optional[dict[str, Any]]:
        """approve=复核通过（可采纳）；reject=不采纳（仅记录，不触发动作）。
        存储统一为 approved / rejected。"""
        if decision not in ("approve", "reject"):
            raise ValueError(f"decision 必须是 approve|reject，收到: {decision}")
        stored = "approved" if decision == "approve" else "rejected"
        with self._lock:
            run = self._runs.get(run_id)
            if not run or step_key not in run:
                return None
            item = run[step_key]
            if item["decision"] != "pending":
                return item  # 幂等：已决策的返回现状
            item["decision"] = stored
            item["decided_at"] = _now()
            item["comment"] = comment
            item["reviewer"] = reviewer
        _audit("review_decision", {
            "run_id": run_id, "step_key": step_key, "decision": stored,
            "comment": comment[:200], "reviewer": reviewer,
        })
        logger.info(
            f"[ReviewGate] run_id={run_id} {step_key} → {stored}"
            + (f" ({comment[:60]})" if comment else "")
        )
        return item


# 全局单例
REVIEW_GATE = ReviewGate()


def new_run_id() -> str:
    return f"wf_{secrets.token_hex(6)}"
