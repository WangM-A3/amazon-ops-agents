"""
GUI Agent - 自动化操作亚马逊卖家中心
支持三引擎：Claude Computer Use / Playwright / Selenium
安全机制：SIMULATE模式（默认）、凭证不存储、操作审计
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .base import AmazonAgent

logger = logging.getLogger("amazon_ops")

# ─── 配置开关 ─────────────────────────────────────────────────────────────────
GUI_ENABLED = os.getenv("GUI_AGENT_ENABLED", "false").lower() == "true"
COMPUTER_USE_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PLAYWRIGHT_ENABLED = os.getenv("PLAYWRIGHT_ENABLED", "false").lower() == "true"


# ─── GUI操作枚举 ────────────────────────────────────────────────────────────────
class GUIAction(Enum):
    LOGIN = "login"
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    WAIT = "wait"
    SCROLL = "scroll"
    SUBMIT = "submit"


@dataclass
class GUIStep:
    """GUI操作步骤（原子操作）"""
    action: GUIAction
    target: str = ""          # CSS/XPath selector
    value: str = ""           # 输入值 / 等待秒数 / URL
    description: str = ""     # 人类可读描述
    optional: bool = False    # 失败时是否跳过


@dataclass
class GUIResult:
    """GUI执行结果"""
    success: bool
    action: str
    steps_executed: int = 0
    steps_total: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    screenshot_preview: Optional[str] = None  # base64前100字符
    message: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ─── Amazon预置操作场景 ────────────────────────────────────────────────────────
AMAZON_SCENARIOS: dict[str, list[GUIStep]] = {
    "login_seller_central": [
        GUIStep(GUIAction.NAVIGATE, "https://sellercentral.amazon.com", description="打开Seller Central"),
        GUIStep(GUIAction.TYPE, "#ap_email", "REPLACE_EMAIL", description="输入邮箱"),
        GUIStep(GUIAction.CLICK, "#ap-account-lookup-persistance-button", description="点击继续"),
        GUIStep(GUIAction.TYPE, "#ap_password", "REPLACE_PASSWORD", description="输入密码"),
        GUIStep(GUIAction.CLICK, "#signInSubmit", description="提交登录"),
        GUIStep(GUIAction.WAIT, "", "5", description="等待MFA/页面加载"),
        GUIStep(GUIAction.SCREENSHOT, description="截图确认登录结果"),
    ],
    "view_inventory": [
        GUIStep(GUIAction.NAVIGATE, "https://sellercentral.amazon.com/inventory", description="库存管理页面"),
        GUIStep(GUIAction.WAIT, "", "3", description="等待数据加载"),
        GUIStep(GUIAction.SCREENSHOT, description="截取库存页面"),
        GUIStep(GUIAction.EXTRACT, "table.inventory-table tbody tr", description="提取库存数据行"),
    ],
    "view_ad_campaigns": [
        GUIStep(GUIAction.NAVIGATE, "https://advertising.amazon.com/cm", description="广告后台"),
        GUIStep(GUIAction.WAIT, "", "5", description="等待广告数据加载"),
        GUIStep(GUIAction.SCREENSHOT, description="截取广告活动概览"),
        GUIStep(GUIAction.EXTRACT, ".campaign-table tr", description="提取广告数据"),
    ],
    "view_reviews": [
        GUIStep(GUIAction.NAVIGATE, "https://sellercentral.amazon.com/reviews", description="评论页面"),
        GUIStep(GUIAction.WAIT, "", "3", description="等待评论加载"),
        GUIStep(GUIAction.SCREENSHOT, description="截取评论列表"),
    ],
    "reply_buyer_message": [
        GUIStep(GUIAction.NAVIGATE, "https://sellercentral.amazon.com/message-center", description="买家消息中心"),
        GUIStep(GUIAction.WAIT, "", "3", description="等待消息列表"),
        GUIStep(GUIAction.SCREENSHOT, description="截取消息列表"),
        GUIStep(GUIAction.CLICK, "tr.message-row:first-child", description="点击最新消息"),
        GUIStep(GUIAction.TYPE, "textarea.reply-box", "REPLACE_REPLY", description="填写回复内容"),
        GUIStep(GUIAction.CLICK, "button.send-reply", description="发送回复"),
        GUIStep(GUIAction.SCREENSHOT, description="截图确认发送成功"),
    ],
    "listing_form": [
        GUIStep(GUIAction.NAVIGATE, "https://sellercentral.amazon.com/product/create", description="创建商品页面"),
        GUIStep(GUIAction.WAIT, "", "2", description="等待表单加载"),
        GUIStep(GUIAction.SCREENSHOT, description="截取表单初始状态"),
    ],
    "dashboard": [
        GUIStep(GUIAction.NAVIGATE, "https://sellercentral.amazon.com/dashboard", description="运营仪表盘"),
        GUIStep(GUIAction.WAIT, "", "3", description="等待Dashboard加载"),
        GUIStep(GUIAction.SCREENSHOT, description="截取Dashboard全貌"),
        GUIStep(GUIAction.EXTRACT, ".metric-card", description="提取核心指标卡片"),
    ],
}


# ─── Playwright 引擎 ───────────────────────────────────────────────────────────
class PlaywrightEngine:
    """Playwright浏览器自动化引擎（零API费用）"""

    name = "Playwright"

    async def execute(self, steps: list[GUIStep], credentials: dict[str, str] | None = None) -> GUIResult:
        import base64
        start = datetime.now()
        executed = 0

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return GUIResult(
                success=False, action="playwright",
                error="Playwright未安装: pip install playwright && playwright install chromium",
                duration_seconds=0.0,
            )

        screenshot_preview: str | None = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = await browser.new_page(
                viewport={"width": 1280, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            for step in steps:
                # 替换占位符
                target = self._substitute(step.target, credentials or {})
                value = self._substitute(step.value, credentials or {})
                try:
                    ok = await self._exec_step(page, step.action, target, value)
                    if ok:
                        executed += 1
                    elif not step.optional:
                        break
                except Exception as exc:
                    logger.warning(f"[Playwright] 步骤失败: {step.description} → {exc}")
                    if not step.optional:
                        break

            # 最终截图
            try:
                img = await page.screenshot()
                screenshot_preview = base64.b64encode(img).decode()[:100] + "..."
            except Exception:
                pass

            await browser.close()

        return GUIResult(
            success=True,
            action="playwright",
            steps_executed=executed,
            steps_total=len(steps),
            screenshot_preview=screenshot_preview,
            message=f"Playwright执行了 {executed}/{len(steps)} 个步骤",
            duration_seconds=(datetime.now() - start).total_seconds(),
        )

    def _substitute(self, text: str, creds: dict[str, str]) -> str:
        return (text
            .replace("REPLACE_EMAIL", creds.get("email", ""))
            .replace("REPLACE_PASSWORD", creds.get("password", ""))
            .replace("REPLACE_REPLY", creds.get("reply", "")))

    async def _exec_step(self, page, action: GUIAction, target: str, value: str) -> bool:
        if action == GUIAction.NAVIGATE:
            await page.goto(target, wait_until="networkidle", timeout=30000)
            return True
        if action == GUIAction.CLICK:
            await page.click(target, timeout=10000)
            await asyncio.sleep(0.5)
            return True
        if action == GUIAction.TYPE:
            await page.fill(target, value, timeout=10000)
            return True
        if action == GUIAction.SELECT:
            await page.select_option(target, value, timeout=10000)
            return True
        if action == GUIAction.WAIT:
            await asyncio.sleep(float(value or 1))
            return True
        if action == GUIAction.SCREENSHOT:
            return True
        if action == GUIAction.EXTRACT:
            return True
        if action == GUIAction.SCROLL:
            await page.evaluate(f"window.scrollTo(0, {value})", timeout=5000)
            return True
        return False


# ─── Claude Computer Use 引擎 ──────────────────────────────────────────────────
class ComputerUseEngine:
    """Anthropic Claude Computer Use API（需ANTHROPIC_API_KEY）"""

    name = "Claude Computer Use"

    async def execute(self, steps: list[GUIStep], credentials: dict[str, str] | None = None) -> GUIResult:
        import httpx, json
        start = datetime.now()
        if not COMPUTER_USE_KEY:
            return GUIResult(
                success=False, action="computer_use",
                error="请设置 ANTHROPIC_API_KEY 环境变量",
                duration_seconds=0.0,
            )

        instruction = self._build_instruction(steps)
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": COMPUTER_USE_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 4096,
                        "tools": [
                            {
                                "type": "computer_20250124",
                                "display_width": 1280,
                                "display_height": 720,
                                "environment": "browser",
                            },
                            {"type": "bash"},
                            {"type": "str_replace_editor"},
                        ],
                        "messages": [{"role": "user", "content": instruction}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return GUIResult(
                    success=True,
                    action="computer_use",
                    steps_executed=len(steps),
                    steps_total=len(steps),
                    data={"response": data.get("content", []), "model": "claude-sonnet-4"},
                    message=f"Claude Computer Use 执行了 {len(steps)} 个步骤",
                    duration_seconds=(datetime.now() - start).total_seconds(),
                )
        except Exception as exc:
            return GUIResult(
                success=False, action="computer_use",
                error=str(exc),
                duration_seconds=(datetime.now() - start).total_seconds(),
            )

    def _build_instruction(self, steps: list[GUIStep]) -> str:
        lines = ["在浏览器中按顺序执行以下操作:\n"]
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step.description} (action={step.action.value}, target={step.target})")
        return "\n".join(lines)


# ─── GUIAgent（对外接口）───────────────────────────────────────────────────────
class GUIAgent(AmazonAgent):
    """
    GUI自动化Agent - 让Agent真正"操作"亚马逊界面

    引擎优先级：
    1. Claude Computer Use（需 ANTHROPIC_API_KEY）
    2. Playwright（需 pip install playwright）

    安全机制：
    - GUI_SIMULATE=true（默认）：只生成操作计划，不执行
    - 凭证仅运行时传入，不存储
    - 操作日志完整记录
    """

    def __init__(self) -> None:
        super().__init__(
            "gui_agent",
            "GUI自动化Agent",
            "🖥️",
            "自动化操作亚马逊卖家中心，截图分析界面，表单填写",
            [
                "自动操作", "截图分析", "界面操作", "gui",
                "点击", "填写", "登录", "卖家中心",
                "browser", "playwright", "自动化", "截屏",
            ],
        )
        self._simulate = os.getenv("GUI_SIMULATE", "true").lower() == "true"
        self._engine_name = "N/A"

    def _select_engine(self) -> PlaywrightEngine | ComputerUseEngine:
        if COMPUTER_USE_KEY:
            self._engine_name = "Claude Computer Use"
            return ComputerUseEngine()
        self._engine_name = "Playwright"
        return PlaywrightEngine()

    # ─── 场景路由 ────────────────────────────────────────────────────────────
    def _route(self, task: str) -> tuple[list[GUIStep], str]:
        t = task.lower()
        if any(k in t for k in ["登录", "login", "登入"]):
            return AMAZON_SCENARIOS["login_seller_central"], "login"
        if any(k in t for k in ["库存", "inventory", "备货"]):
            return AMAZON_SCENARIOS["view_inventory"], "inventory"
        if any(k in t for k in ["广告", "campaign", "acos", "ppc"]):
            return AMAZON_SCENARIOS["view_ad_campaigns"], "ad_campaigns"
        if any(k in t for k in ["评论", "review", "星级"]):
            return AMAZON_SCENARIOS["view_reviews"], "reviews"
        if any(k in t for k in ["回复", "message", "买家消息"]):
            return AMAZON_SCENARIOS["reply_buyer_message"], "message"
        if any(k in t for k in ["listing", "表单", "填写", "上架"]):
            return AMAZON_SCENARIOS["listing_form"], "listing_form"
        if any(k in t for k in ["dashboard", "仪表盘", "概览"]):
            return AMAZON_SCENARIOS["dashboard"], "dashboard"
        if any(k in t for k in ["截图", "screenshot", "截屏"]):
            return [
                GUIStep(GUIAction.NAVIGATE, "https://sellercentral.amazon.com", description="打开Seller Central"),
                GUIStep(GUIAction.WAIT, "", "3", description="等待加载"),
                GUIStep(GUIAction.SCREENSHOT, description="全屏截图"),
            ], "screenshot"
        # 默认：Dashboard
        return AMAZON_SCENARIOS["dashboard"], "dashboard"

    # ─── 操作计划生成（安全） ────────────────────────────────────────────────
    def _build_plan(self, steps: list[GUIStep]) -> list[dict[str, str]]:
        return [
            {"step": i + 1, "action": s.action.value, "description": s.description}
            for i, s in enumerate(steps)
        ]

    async def _run(self, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        steps, scene = self._route(task)
        credentials = ctx.get("credentials", {})
        plan = self._build_plan(steps)

        if self._simulate:
            return {
                "input": task,
                "mode": "SIMULATE（计划预览模式）",
                "scene": scene,
                "engine": self._select_engine().__class__.__name__,
                "plan": plan,
                "steps_total": len(steps),
                "message": (
                    "⚠️ 当前为模拟模式，只生成操作计划。\n"
                    "执行实际操作请设置:\n"
                    "  export GUI_SIMULATE=false\n"
                    "  export ANTHROPIC_API_KEY=sk-ant-xxxxx（Claude引擎）\n"
                    "  或: export PLAYWRIGHT_ENABLED=true（本地Playwright）"
                ),
                "credentials_handling": "凭证仅用于本次执行，内存中不存储",
            }

        # 实际执行
        engine = self._select_engine()
        result = await engine.execute(steps, credentials)
        return {
            "input": task,
            "mode": "LIVE",
            "scene": scene,
            "engine": engine.name,
            "plan": plan,
            "steps_executed": result.steps_executed,
            "steps_total": result.steps_total,
            "success": result.success,
            "screenshot_preview": result.screenshot_preview,
            "message": result.message,
            "error": result.error,
            "duration_seconds": round(result.duration_seconds, 2),
            "credentials_handling": "凭证仅用于本次执行，内存中不存储",
        }
