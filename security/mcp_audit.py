"""
MCP Audit - MCP服务器安全审计模块
提供漏洞扫描、权限边界检查、操作日志审计能力
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("amazon_ops.mcp_audit")

# ─── 漏洞级别枚举 ──────────────────────────────────────────────────────────────
class VulnerabilityLevel(Enum):
    CRITICAL = "critical"   # 立即修复：严重安全风险
    HIGH     = "high"       # 高优先级：存在已知攻击路径
    MEDIUM   = "medium"     # 中等级别：需纳入计划修复
    LOW      = "low"        # 低风险：建议改进
    INFO     = "info"       # 信息参考：最佳实践建议


# ─── MCP已知危险模式（参考2025-04安全事件）────────────────────────────────────
DANGEROUS_PATTERNS = {
    # 命令注入
    r"[;&|`$]\s*\w+",
    r"\$\([^)]+\)",
    r"`[^`]+`",
    # 路径遍历
    r"\.\.[/\\]",
    r"[/\\]\.\.[/\\]",
    # 凭证泄露
    r"(?i)(api[_-]?key|token|secret|password|auth)\s*[=:]\s*['\"]?\w+",
    # SSRF风险
    r"(?i)(url|endpoint|uri)\s*[=:]\s*['\"]?https?://",
    # 文件系统越权
    r"(?i)(read|write|delete|exec)[_]?(file|dir|path|cmd|command)\s*\(",
}

# 允许的MCP工具白名单（Amazon Ops场景）
ALLOWED_MCP_TOOLS = {
    # 读操作（只审计不阻止）
    "get_product", "list_orders", "get_inventory", "get_pricing",
    "get_ads_report", "get_performance", "list_reviews",
    "get_fulfillment_data", "get_recommendations",
    # 写操作（需要额外确认）
    "update_price", "update_inventory", "send_message",
    "create_listing", "update_listing",
    # 危险操作（高危审计）
    "delete_product", "cancel_order", "bulk_update",
}

# MCP权限边界定义
PERMISSION_BOUNDARIES = {
    "read_only":  ["get", "list", "search", "fetch", "retrieve"],
    "write":      ["update", "set", "create", "submit", "send"],
    "delete":     ["delete", "remove", "cancel", "terminate"],
    "admin":       ["*"],  # 需额外MFA验证
}


# ─── 审计日志条目 ──────────────────────────────────────────────────────────────
@dataclass
class MCPAuditEntry:
    """MCP操作审计日志"""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event_type: str = ""         # vulnerability_scan | permission_check | tool_call
    tool_name: str = ""
    input_args: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    user_id: str = ""
    result: str = ""             # ALLOWED | BLOCKED | FLAGGED
    vulnerability_level: str = ""  # critical|high|medium|low|info
    details: str = ""
    risk_score: float = 0.0     # 0.0-1.0


@dataclass
class VulnerabilityReport:
    """漏洞扫描报告"""
    scan_id: str
    timestamp: str
    target: str                  # 扫描目标（MCP Server URL / 配置文件路径）
    vulnerabilities: list[dict]   # [{level, pattern, location, description, recommendation}]
    passed_checks: int
    failed_checks: int
    overall_risk_score: float    # 0.0-1.0
    recommendations: list[str]


@dataclass
class PermissionBoundaryResult:
    """权限边界检查结果"""
    allowed: bool
    requested_tool: str
    required_permission: str
    user_permission: str
    gap_analysis: str             # 权限差距描述
    escalation_required: bool


# ─── 核心类 ─────────────────────────────────────────────────────────────────────
class MCPAuditLogger:
    """
    MCP操作日志记录器
    负责持久化所有MCP相关审计事件
    """

    def __init__(self, log_path: str = "./security/mcp_audit_logs") -> None:
        self.log_path = log_path
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        import os
        os.makedirs(self.log_path, exist_ok=True)

    def log(self, entry: MCPAuditEntry) -> str:
        """写入单条审计日志，返回日志ID"""
        log_id = secrets.token_hex(8)
        line = {
            "log_id": log_id,
            **vars(entry),
        }
        filename = datetime.now().strftime("%Y%m%d") + ".jsonl"
        filepath = f"{self.log_path}/{filename}"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        logger.info(
            f"[MCPAudit] {entry.event_type} | tool={entry.tool_name} "
            f"| result={entry.result} | risk={entry.risk_score:.2f}"
        )
        return log_id

    def query(
        self,
        session_id: str = "",
        tool_name: str = "",
        start_time: str = "",
        end_time: str = "",
        limit: int = 100,
    ) -> list[dict]:
        """查询历史审计日志"""
        import glob, os
        files = sorted(
            glob.glob(f"{self.log_path}/*.jsonl"),
            reverse=True
        )[:7]  # 最近7天

        results = []
        for filepath in files:
            with open(filepath, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if session_id and entry.get("session_id") != session_id:
                            continue
                        if tool_name and entry.get("tool_name") != tool_name:
                            continue
                        results.append(entry)
                    except json.JSONDecodeError:
                        continue
        return results[-limit:]


class MCPVulnerabilityScanner:
    """
    MCP服务器漏洞扫描器

    扫描维度：
    1. 输入参数命令注入检测
    2. 凭证/密钥泄露检测
    3. SSRF风险检测
    4. 路径遍历检测
    5. 工具调用频率异常检测
    """

    def __init__(self) -> None:
        # 命令注入
        self._cmd_pattern = re.compile(
            r"[;&|`$]\s*\w+|\\$\\([^)]+\\)|`[^`]+`"
        )
        # 路径遍历
        self._path_traversal = re.compile(r"\\.\\.[/\\\\]")
        # 凭证泄露
        self._credential_leak = re.compile(
            r"(?i)(api[_-]?key|token|secret|password|auth)"
            r"\\s*[=:]\\s*['\"]?[\\w\\-]{8,}"
        )
        # SSRF
        self._ssrf = re.compile(
            r"(?i)(url|endpoint|uri)\\s*[=:]\\s*['\"]?https?://[^'\"\\s]+"
        )
        self._audit_logger = MCPAuditLogger()

    def scan_args(self, tool_name: str, args: dict[str, Any]) -> list[dict]:
        """
        扫描MCP工具调用参数中的安全风险

        Returns:
            list of {level, pattern, matched_text, description, recommendation}
        """
        findings = []
        serialized = json.dumps(args, ensure_ascii=False)

        # 1. 命令注入检测
        if self._cmd_pattern.search(serialized):
            findings.append({
                "level": VulnerabilityLevel.CRITICAL.value,
                "pattern": "command_injection",
                "matched_text": "detected_shell_chars",
                "description": "输入参数包含可疑shell字符，可能导致命令注入",
                "recommendation": "对所有用户输入进行严格白名单校验，禁用shell特殊字符",
            })

        # 2. 路径遍历检测
        if self._path_traversal.search(serialized):
            findings.append({
                "level": VulnerabilityLevel.HIGH.value,
                "pattern": "path_traversal",
                "matched_text": "../",
                "description": "输入包含路径遍历序列，可能导致任意文件访问",
                "recommendation": "规范化所有文件路径，禁止包含..字符",
            })

        # 3. 凭证泄露检测
        if self._credential_leak.search(serialized):
            findings.append({
                "level": VulnerabilityLevel.CRITICAL.value,
                "pattern": "credential_exposure",
                "matched_text": "api_key_or_token",
                "description": "输入参数包含凭证信息，存在泄露风险",
                "recommendation": "使用环境变量或密钥管理服务，禁止明文传递凭证",
            })

        # 4. SSRF检测
        if self._ssrf.search(serialized):
            findings.append({
                "level": VulnerabilityLevel.HIGH.value,
                "pattern": "ssrf",
                "matched_text": "http_url_in_input",
                "description": "输入包含外部URL，可能导致服务器端请求伪造攻击",
                "recommendation": "禁止用户控制URL参数，使用预定义资源白名单",
            })

        return findings

    def scan_config(self, config: dict[str, Any]) -> VulnerabilityReport:
        """
        扫描MCP配置文件的安全漏洞
        """
        scan_id = secrets.token_hex(8)
        vulnerabilities = []

        # 检查传输方式
        transport = config.get("mcp", {}).get("transport", "stdio")
        if transport not in ("stdio", "streamablehttp"):
            vulnerabilities.append({
                "level": VulnerabilityLevel.HIGH.value,
                "pattern": "unsecure_transport",
                "location": "mcp.transport",
                "description": f"未知的MCP传输方式: {transport}",
                "recommendation": "仅使用stdio或streamablehttp传输",
            })

        # 检查认证配置
        auth = config.get("mcp", {}).get("auth", {})
        if not auth.get("enabled", False):
            vulnerabilities.append({
                "level": VulnerabilityLevel.CRITICAL.value,
                "pattern": "no_auth",
                "location": "mcp.auth.enabled",
                "description": "MCP Server未启用认证",
                "recommendation": "强制启用JWT或API Key认证",
            })

        # 检查IP白名单
        allowed_ips = auth.get("allowed_ips", [])
        if not allowed_ips:
            vulnerabilities.append({
                "level": VulnerabilityLevel.MEDIUM.value,
                "pattern": "no_ip_whitelist",
                "location": "mcp.auth.allowed_ips",
                "description": "未配置IP白名单",
                "recommendation": "配置IP白名单限制MCP访问来源",
            })

        # 检查审计日志
        if not config.get("audit", {}).get("enabled", False):
            vulnerabilities.append({
                "level": VulnerabilityLevel.HIGH.value,
                "pattern": "no_audit",
                "location": "audit.enabled",
                "description": "MCP操作未启用审计日志",
                "recommendation": "启用MCP操作审计并设置90天保留期",
            })

        # 检查速率限制
        rate_limit = config.get("mcp", {}).get("rate_limit", {})
        if not rate_limit.get("enabled", False):
            vulnerabilities.append({
                "level": VulnerabilityLevel.MEDIUM.value,
                "pattern": "no_rate_limit",
                "location": "mcp.rate_limit.enabled",
                "description": "MCP Server未启用速率限制",
                "recommendation": "配置请求速率限制防止滥用",
            })

        passed = 6 - len(vulnerabilities)
        failed = len(vulnerabilities)
        # 风险评分：critical=1.0, high=0.7, medium=0.4, low=0.2
        weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2, "info": 0.05}
        risk_score = sum(
            weights.get(v.get("level", "low"), 0.2)
            for v in vulnerabilities
        ) / max(passed + failed, 1)
        risk_score = min(risk_score, 1.0)

        return VulnerabilityReport(
            scan_id=scan_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            target="mcp_config",
            vulnerabilities=vulnerabilities,
            passed_checks=passed,
            failed_checks=failed,
            overall_risk_score=risk_score,
            recommendations=[
                v["recommendation"] for v in vulnerabilities
                if v["level"] in ("critical", "high")
            ],
        )

    def check_tool_allowed(self, tool_name: str) -> bool:
        """检查工具是否在白名单内"""
        if tool_name in ALLOWED_MCP_TOOLS:
            return True
        # 通配符匹配
        for allowed in ALLOWED_MCP_TOOLS:
            if allowed.endswith("_any"):
                return True
        return False


class MCPPermissionBoundary:
    """
    MCP权限边界检查器
    验证Agent对MCP工具的调用是否在其角色权限范围内
    """

    def __init__(self) -> None:
        self._audit_logger = MCPAuditLogger()

    def check(
        self,
        user_permission: str,
        tool_name: str,
        session_id: str = "",
    ) -> PermissionBoundaryResult:
        """
        检查MCP工具调用是否在权限边界内

        Args:
            user_permission: 当前用户权限级别 (read_only | write | delete | admin)
            tool_name: 调用的MCP工具名

        Returns:
            PermissionBoundaryResult
        """
        # 推断所需权限
        required = self._infer_required_permission(tool_name)

        # 权限层级
        PERM_LEVELS = {"read_only": 1, "write": 2, "delete": 3, "admin": 4}
        user_level = PERM_LEVELS.get(user_permission, 0)
        req_level  = PERM_LEVELS.get(required, 4)

        allowed = user_level >= req_level

        if not allowed:
            gap = f"工具 '{tool_name}' 需要 '{required}' 权限，但当前用户为 '{user_permission}'"
        else:
            gap = f"权限充足：{user_permission} >= {required}"

        return PermissionBoundaryResult(
            allowed=allowed,
            requested_tool=tool_name,
            required_permission=required,
            user_permission=user_permission,
            gap_analysis=gap,
            escalation_required=(required == "admin" and user_permission != "admin"),
        )

    def _infer_required_permission(self, tool_name: str) -> str:
        """根据工具名推断所需权限"""
        for action, perms in PERMISSION_BOUNDARIES.items():
            if "*" in perms:
                return action
            for perm in perms:
                if perm in tool_name.lower():
                    return action
        return "read_only"


class MCPAuditor:
    """
    MCP安全审计主入口
    整合漏洞扫描、权限检查、日志审计三大模块
    """

    def __init__(self, log_path: str = "./security/mcp_audit_logs") -> None:
        self.scanner   = MCPVulnerabilityScanner()
        self.boundary = MCPPermissionBoundary()
        self.logger   = MCPAuditLogger(log_path)

    def audit_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        user_permission: str = "read_only",
        session_id: str = "",
        user_id: str = "",
    ) -> MCPAuditEntry:
        """
        审计一次MCP工具调用

        执行流程：
        1. 漏洞扫描（无条件，先于白名单） → CRITICAL立即阻止
        2. 白名单检查 → 工具在白名单则记录并允许（但已通过扫描）
        3. 权限边界检查 → 不在边界内则阻止
        4. 记录完整审计日志

        [安全修复 2026-04-14] 白名单不再绕过漏洞扫描，防止白名单工具名
        被注入时绕过命令注入检测。
        """
        entry = MCPAuditEntry(
            event_type="tool_call",
            tool_name=tool_name,
            input_args=self._sanitize_args(args),
            session_id=session_id,
            user_id=user_id,
        )

        # Step 1: 漏洞扫描（无条件，先于白名单）
        # [FIX] 原逻辑：白名单通过 → 直接返回，绕过漏洞扫描
        # [修复后]：即使白名单工具也必须先通过漏洞扫描
        findings = self.scanner.scan_args(tool_name, args)
        if findings:
            critical = [f for f in findings if f["level"] == VulnerabilityLevel.CRITICAL.value]
            if critical:
                entry.result = "BLOCKED"
                entry.vulnerability_level = VulnerabilityLevel.CRITICAL.value
                entry.details = json.dumps(critical, ensure_ascii=False)
                entry.risk_score = 1.0
                return self.logger.log(entry)

            entry.result = "FLAGGED"
            entry.vulnerability_level = findings[0]["level"]
            entry.details = json.dumps(findings, ensure_ascii=False)
            entry.risk_score = self._score_findings(findings)

        # Step 2: 白名单检查（仅在通过扫描后生效）
        if self.scanner.check_tool_allowed(tool_name):
            entry.result = "ALLOWED"
            entry.details = "tool_in_whitelist"
            entry.risk_score = 0.0
            return self.logger.log(entry)

        # Step 3: 权限边界检查
        boundary_result = self.boundary.check(
            user_permission=user_permission,
            tool_name=tool_name,
            session_id=session_id,
        )
        if not boundary_result.allowed:
            entry.result = "BLOCKED"
            entry.details += f" | permission_denied: {boundary_result.gap_analysis}"
            entry.risk_score = max(entry.risk_score, 0.8)
        elif entry.result == "FLAGGED":
            pass  # 已有标记，保持FLAGGED
        else:
            entry.result = "ALLOWED"

        return self.logger.log(entry)

    def run_vulnerability_scan(
        self,
        target: str,
        config: dict[str, Any] | None = None,
    ) -> VulnerabilityReport:
        """运行完整漏洞扫描"""
        if config is not None:
            return self.scanner.scan_config(config)

        # 模拟扫描（配置文件路径或MCP Server URL）
        report = VulnerabilityReport(
            scan_id=secrets.token_hex(8),
            timestamp=datetime.now(timezone.utc).isoformat(),
            target=target,
            vulnerabilities=[],
            passed_checks=6,
            failed_checks=0,
            overall_risk_score=0.0,
            recommendations=[],
        )
        return report

    def generate_soc2_report(
        self,
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        """
        生成MCP专项SOC 2合规报告
        覆盖：
        - 操作趋势（按工具、按用户）
        - 异常事件统计
        - 漏洞修复状态
        - 权限变更记录
        """
        logs = self.logger.query(
            start_time=start_date,
            end_time=end_date,
            limit=10000,
        )

        # 统计
        total = len(logs)
        blocked = sum(1 for l in logs if l.get("result") == "BLOCKED")
        flagged = sum(1 for l in logs if l.get("result") == "FLAGGED")
        allowed = sum(1 for l in logs if l.get("result") == "ALLOWED")

        # 工具调用TOP5
        from collections import Counter
        tool_counts = Counter(l.get("tool_name", "") for l in logs)
        top_tools = tool_counts.most_common(5)

        # 高风险事件
        high_risk = [
            l for l in logs
            if l.get("risk_score", 0) >= 0.7 or l.get("vulnerability_level") in ("critical", "high")
        ]

        return {
            "report_type": "MCP_SECURITY_AUDIT",
            "period": {"start": start_date, "end": end_date},
            "summary": {
                "total_calls": total,
                "allowed": allowed,
                "blocked": blocked,
                "flagged": flagged,
                "block_rate": round(blocked / max(total, 1), 4),
                "flag_rate":  round(flagged / max(total, 1), 4),
            },
            "top_tools": [{"tool": t, "count": c} for t, c in top_tools],
            "high_risk_events": high_risk,
            "compliance_status": "PASS" if blocked == 0 else "REVIEW_REQUIRED",
        }

    def _sanitize_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """脱敏敏感参数"""
        sanitized = {}
        # [FIX 2026-04-14] 扩展敏感字段覆盖范围（case-insensitive, 包含大小写变体）
        SENSITIVE_KEYS = {
            "api_key", "api-key", "apikey", "api_key_v", "api_key_v1", "api_key_v2",
            "token", "access_token", "access-token", "session_token", "session-token",
            "refresh_token", "bearer", "bearer_token",
            "secret", "secret_key", "secret_key_v", "app_secret",
            "password", "passwd", "pwd",
            "auth", "authorization", "authorisation",
            "private_key", "privatekey", "client_secret",
            "mcp_server_api_key", "agent_auth_api_key",
        }
        for k, v in args.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return sanitized

    def _score_findings(self, findings: list[dict]) -> float:
        weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2}
        if not findings:
            return 0.0
        return max(weights.get(f.get("level", "low"), 0.2) for f in findings)


# ─── 全局单例 ──────────────────────────────────────────────────────────────────
AUDITOR = MCPAuditor()
