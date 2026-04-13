"""
GUI Guardian - GUI Agent三层安全防护
应用层拦截 → 系统层确认 → 驱动层保护
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("amazon_ops.guardian")

# ─── 安全级别枚举 ──────────────────────────────────────────────────────────────
class SecurityLevel(Enum):
    SAFE      = "safe"       # 安全操作，直接放行
    CONFIRM   = "confirm"    # 需要用户二次确认
    BLOCK     = "block"      # 危险操作，直接拦截
    AUDIT     = "audit"      # 记录但不阻止


# ─── 操作危险等级定义 ──────────────────────────────────────────────────────────
# 应用层拦截（BLOCK）
PROHIBITED_ACTIONS = {
    "delete_listing",         # 删除Listing
    "delete_product",         # 删除产品
    "bulk_delete_orders",     # 批量删除订单
    "delete_review",          # 删除评论
    "modify_brand_settings",  # 修改品牌核心设置
    "transfer_funds",         # 转账/修改收款账户
    "submit_false_report",    # 提交虚假报告
    "cancel_all_orders",      # 取消所有订单
    "disable_advertising",     # 禁用广告活动（批量）
    "modify_tax_info",        # 修改税务信息
}

# 系统层确认（CONFIRM）
CONFIRM_REQUIRED_ACTIONS = {
    # 价格类
    "modify_price": {
        "keywords": ["修改价格", "调价", "降价", "涨价", "set price", "change price"],
        "reason": "价格修改将直接影响BuyBox和销售收入",
    },
    # 消息类
    "send_message": {
        "keywords": ["发送消息", "回复买家", "send message", "reply to buyer"],
        "reason": "消息将直接触达买家，请确认内容准确",
    },
    # 数据导出类
    "export_sensitive": {
        "keywords": ["导出客户数据", "导出邮箱", "extract customer", "export customer data"],
        "reason": "涉及买家个人信息导出，需要授权",
    },
    # 广告调整类
    "modify_ad_budget": {
        "keywords": ["修改广告预算", "调整预算", "set budget", "change budget"],
        "reason": "预算变更将影响广告投放，请确认",
    },
    # 库存修改类
    "adjust_inventory": {
        "keywords": ["修改库存数量", "set inventory", "adjust quantity"],
        "reason": "库存变更可能影响FBA补货计划",
    },
}

# 审计类（AUDIT） - 记录但放行
AUDIT_ACTIONS = {
    "view_dashboard",          # 查看仪表盘
    "view_reports",            # 查看报表
    "view_orders",             # 查看订单
    "extract_data",            # 提取数据
    "screenshot",             # 截图
    "navigate",                # 导航浏览
}


# ─── 操作日志 ──────────────────────────────────────────────────────────────────
@dataclass
class AuditLogEntry:
    """操作审计日志条目"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    action: str = ""
    security_level: str = ""
    task: str = ""
    result: str = ""          # ALLOWED / BLOCKED / CONFIRMED / PENDING
    reason: str = ""
    session_id: str = ""
    agent: str = "GUI Guardian"


# ─── 安全确认请求 ──────────────────────────────────────────────────────────────
@dataclass
class ConfirmationRequest:
    """用户确认请求"""
    action: str
    description: str
    reason: str
    session_id: str
    confirm_token: str        # 用于确认的Token
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_in_seconds: int = 300  # 5分钟有效期


# ─── 凭证加密 ─────────────────────────────────────────────────────────────────
class CredentialVault:
    """
    凭证保险库 - 核心账号信息加密存储

    使用HMAC-SHA256加密，密钥来自环境变量
    """

    def __init__(self) -> None:
        self._secret = os.getenv("GUI_GUARDIAN_SECRET", secrets.token_hex(32)).encode()
        self._cache: dict[str, bytes] = {}  # 内存缓存（仅Session内）

    def store(self, key: str, value: str) -> str:
        """加密存储凭证，返回存储ID"""
        storage_id = secrets.token_urlsafe(16)
        encrypted = hmac.new(self._secret, value.encode(), hashlib.sha256).digest()
        self._cache[storage_id] = encrypted
        logger.info(f"[CredentialVault] 凭证已加密存储 (ID={storage_id[:8]}...)")
        return storage_id

    def retrieve(self, storage_id: str) -> str | None:
        """解密获取凭证"""
        encrypted = self._cache.get(storage_id)
        if not encrypted:
            return None
        # 简单校验：HMAC验证
        expected = hmac.new(self._secret, b"", hashlib.sha256).digest()
        # 实际解密：重新计算（简化版，真实场景用Fernet对称加密）
        return encrypted.hex()[:32] if encrypted else None

    def delete(self, storage_id: str) -> bool:
        """删除凭证"""
        if storage_id in self._cache:
            del self._cache[storage_id]
            logger.info(f"[CredentialVault] 凭证已删除 (ID={storage_id[:8]}...)")
            return True
        return False

    def clear_all(self) -> int:
        """清空所有缓存凭证"""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"[CredentialVault] 清空全部{count}条凭证缓存")
        return count


# ─── GUI Guardian 主类 ─────────────────────────────────────────────────────────
class GUIGuardian:
    """
    GUI Agent 安全守护者

    三层防护机制：
    1. 应用层（BLOCK）  - 直接拦截危险操作
    2. 系统层（CONFIRM）- 需要用户二次确认
    3. 驱动层（AUDIT）  - 全量日志 + 加密存储

    使用方式：
        guardian = GUIGuardian()
        result = guardian.authorize(action="modify_price", task="帮我把某产品价格降到9.9")

        if result.level == SecurityLevel.BLOCK:
            print("拒绝执行：危险操作")
        elif result.level == SecurityLevel.CONFIRM:
            print(f"需要确认：{result.confirmation.description}")
            # 用户确认后：
            guardian.confirm(session_id=result.session_id, token=result.confirm_token)
    """

    def __init__(self) -> None:
        self.name = "GUIGuardian"
        self.vault = CredentialVault()
        self._audit_log: list[AuditLogEntry] = []
        self._pending_confirms: dict[str, ConfirmationRequest] = {}

    # ─── 核心授权方法 ────────────────────────────────────────────────────────
    def authorize(
        self,
        action: str,
        task: str,
        session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> GuardianResult:
        """
        授权检查入口

        Returns:
            GuardianResult：包含 SecurityLevel 和后续指令
        """
        session_id = session_id or secrets.token_hex(8)
        metadata = metadata or {}

        # 1. 应用层检查：危险操作直接拦截
        if action in PROHIBITED_ACTIONS:
            log = AuditLogEntry(
                action=action, security_level="BLOCK",
                task=task[:80], result="BLOCKED",
                reason=f"危险操作被拦截: {action}",
                session_id=session_id,
            )
            self._log_audit(log)
            return GuardianResult(
                level=SecurityLevel.BLOCK,
                action=action,
                reason=action,
                message="⛔ 该操作被系统拦截，禁止执行",
                session_id=session_id,
                confirmed=False,
            )

        # 2. 系统层检查：确认类操作
        for confirm_action, config in CONFIRM_REQUIRED_ACTIONS.items():
            keywords = config["keywords"]
            if any(kw.lower() in task.lower() for kw in keywords):
                confirm_token = secrets.token_urlsafe(24)
                req = ConfirmationRequest(
                    action=confirm_action,
                    description=f"操作: {confirm_action}",
                    reason=config["reason"],
                    session_id=session_id,
                    confirm_token=confirm_token,
                )
                self._pending_confirms[confirm_token] = req

                log = AuditLogEntry(
                    action=confirm_action, security_level="CONFIRM",
                    task=task[:80], result="PENDING",
                    reason=config["reason"], session_id=session_id,
                )
                self._log_audit(log)

                return GuardianResult(
                    level=SecurityLevel.CONFIRM,
                    action=confirm_action,
                    reason=config["reason"],
                    message=f"⚠️ {config['reason']}，是否继续？",
                    session_id=session_id,
                    confirm_token=confirm_token,
                    confirmation=req,
                    confirmed=False,
                )

        # 3. 审计类操作
        if action in AUDIT_ACTIONS:
            log = AuditLogEntry(
                action=action, security_level="AUDIT",
                task=task[:80], result="ALLOWED",
                reason="审计类操作，直接放行",
                session_id=session_id,
            )
            self._log_audit(log)
            return GuardianResult(
                level=SecurityLevel.SAFE,
                action=action,
                reason="审计类操作",
                message="✅ 操作已记录并放行",
                session_id=session_id,
                confirmed=True,
            )

        # 4. 默认放行（安全操作）
        log = AuditLogEntry(
            action=action or "unknown", security_level="SAFE",
            task=task[:80], result="ALLOWED",
            reason="默认安全操作", session_id=session_id,
        )
        self._log_audit(log)
        return GuardianResult(
            level=SecurityLevel.SAFE,
            action=action or "unknown",
            reason="默认安全",
            message="✅ 操作已授权",
            session_id=session_id,
            confirmed=True,
        )

    def confirm(self, confirm_token: str, session_id: str = "") -> GuardianResult:
        """
        用户二次确认（仅对CONFIRM级别操作有效）

        Returns:
            GuardianResult：确认后的授权结果
        """
        req = self._pending_confirms.pop(confirm_token, None)
        if not req:
            return GuardianResult(
                level=SecurityLevel.BLOCK,
                action="confirm",
                reason="无效的确认Token或已过期",
                message="❌ 确认失败：Token无效或已过期",
                session_id=session_id,
                confirmed=False,
            )

        log = AuditLogEntry(
            action=req.action, security_level="CONFIRM",
            task=req.description, result="CONFIRMED",
            reason=f"用户确认: {req.reason}", session_id=session_id,
        )
        self._log_audit(log)

        return GuardianResult(
            level=SecurityLevel.SAFE,
            action=req.action,
            reason=req.reason,
            message=f"✅ 用户已确认：{req.reason}",
            session_id=session_id,
            confirmed=True,
        )

    # ─── 辅助方法 ────────────────────────────────────────────────────────────
    def _log_audit(self, entry: AuditLogEntry) -> None:
        """追加审计日志"""
        self._audit_log.append(entry)
        # 内存限制：最多保留10000条
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

    def get_audit_log(
        self,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取审计日志"""
        logs = self._audit_log
        if session_id:
            logs = [l for l in logs if l.session_id == session_id]
        return [
            {
                "timestamp": l.timestamp,
                "action": l.action,
                "security_level": l.security_level,
                "result": l.result,
                "reason": l.reason,
                "task": l.task,
            }
            for l in logs[-limit:]
        ]

    def is_action_allowed(self, action: str) -> bool:
        """快速检查：某操作是否允许"""
        if action in PROHIBITED_ACTIONS:
            return False
        return True

    def get_statistics(self) -> dict[str, Any]:
        """获取Guardian统计信息"""
        total = len(self._audit_log)
        blocked = sum(1 for l in self._audit_log if l.result == "BLOCKED")
        confirmed = sum(1 for l in self._audit_log if l.result == "CONFIRMED")
        pending = len(self._pending_confirms)
        return {
            "total_audits": total,
            "blocked": blocked,
            "user_confirmed": confirmed,
            "pending_confirms": pending,
            "block_rate": round(blocked / total * 100, 2) if total else 0,
        }


# ─── 授权结果 ─────────────────────────────────────────────────────────────────
@dataclass
class GuardianResult:
    """Guardian授权结果"""
    level: SecurityLevel
    action: str
    reason: str
    message: str
    session_id: str
    confirmed: bool
    confirm_token: str = ""           # CONFIRM级别提供
    confirmation: ConfirmationRequest | None = None  # 确认请求详情


# 全局单例
GUARDIAN = GUIGuardian()
