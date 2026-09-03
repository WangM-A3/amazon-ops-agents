"""
AI 内容合规规则库（v1.2.0 新增）

覆盖两大平台对 AI 生成内容的披露/标注要求：
1. 亚马逊（Amazon）：AI 生成的逼真人物图片需在元数据中添加披露标签
   （Amazon 于 2025 年起执行 "contains-synthetic-performer" 类元数据标签要求，
   未标注的 AI 生成人物图可能面临 Listing 违规风险）
2. TikTok Shop：要求标注 AI 生成内容，明确禁止用 AI 篡改商品外观或捏造不实效果

本模块提供：
- 平台政策常量（供 Agent 引用与展示）
- 规则判断函数：图片是否含 AI 生成人物 → 是否必须打标签
- 合规检查函数：输入素材描述 → 输出合规清单/风险提示
"""

from __future__ import annotations

from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# 亚马逊：AI 生成人物图片元数据披露
# ──────────────────────────────────────────────────────────────────────────────

AMAZON_AI_IMAGE_POLICY: dict[str, Any] = {
    "platform": "Amazon",
    "policy_name": "AI 生成逼真人物图片元数据披露",
    "effective": "2025 年逐步执行（以卖家平台政策页面为准）",
    "requirement": (
        "商品图片/Listing/A+ 内容中若使用 AI 生成的逼真人物形象（synthetic media），"
        "必须通过元数据标签（如 synthetic media / contains-synthetic-performer 标记）"
        "向买家披露；未标注将面临图片审核不通过或 Listing 违规风险。"
    ),
    "scope": ["商品主图", "A+ 内容", "品牌旗舰店", "广告素材", "视频缩略图"],
    "metadata_tags": [
        "contains-synthetic-performer",
        "synthetic-media",
        "ai-generated-image",
    ],
    "exceptions": [
        "完全由真人实拍、未经 AI 生成或修饰的人物图片",
        "纯产品图（无人物出现）不受人物披露要求约束",
    ],
    "risk_if_not_labeled": "图片审核不通过 / Listing 下架 / 账号健康度扣分",
    "source": "Amazon Seller Central 政策更新（卖家论坛公告）",
}

# ──────────────────────────────────────────────────────────────────────────────
# TikTok Shop：AI 生成内容标注 + 禁用 AI 篡改商品外观
# ──────────────────────────────────────────────────────────────────────────────

TIKTOK_SHOP_AI_POLICY: dict[str, Any] = {
    "platform": "TikTok Shop",
    "policy_name": "AI 生成内容标注与商品外观真实性要求",
    "effective": "持续执行（AIGC 内容须显著标识）",
    "requirement": (
        "1) 所有 AI 生成或深度合成的内容（图片/视频/直播）必须在内容中显著标注 AI 生成；"
        "2) 明确禁止使用 AI 篡改商品外观、夸大真实效果或捏造不实功能；"
        "3) 商品主图与详情须与实物一致，AI 修图不得误导买家。"
    ),
    "scope": ["商品图片", "商品视频", "直播画面", "广告素材"],
    "forbidden": [
        "AI 篡改商品外观（改变颜色/材质/尺寸使与实物不符）",
        "AI 捏造不实效果（如虚构使用场景、夸大功能参数）",
        "AI 生成虚假评价或 UGC 内容",
    ],
    "disclosure_label": "显著标注「AI 生成内容」标识（含自动标识与主动披露）",
    "risk_if_violated": "商品下架 / 账号限流 / 封店 / 保证金扣罚",
    "source": "TikTok Shop 平台规则（AIGC 内容治理）",
}

# ──────────────────────────────────────────────────────────────────────────────
# 综合政策
# ──────────────────────────────────────────────────────────────────────────────

AI_CONTENT_POLICY: dict[str, Any] = {
    "amazon": AMAZON_AI_IMAGE_POLICY,
    "tiktok_shop": TIKTOK_SHOP_AI_POLICY,
    "summary": (
        "双平台 AI 内容合规要点：亚马逊要求 AI 逼真人物图加元数据披露标签；"
        "TikTok Shop 要求 AI 内容显著标注且禁止 AI 篡改商品外观/捏造效果。"
        "跨境卖家凡使用 AI 生成产品图/人物图/视频素材，均需先过合规检查。"
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# 规则函数
# ──────────────────────────────────────────────────────────────────────────────


def ai_image_label_required(
    has_real_human: bool = False,
    is_ai_generated: bool = False,
    is_ai_modified: bool = False,
) -> bool:
    """
    判断该图片是否必须标注 AI 披露标签（亚马逊人物图标准）。

    Args:
        has_real_human: 图片中是否出现真人（实拍人物）
        is_ai_generated: 图片是否为 AI 生成（含人物）
        is_ai_modified: 图片是否经 AI 修饰（人脸/人物合成）

    Returns:
        True = 必须添加 AI 披露元数据标签
    """
    # 亚马逊要求：AI 生成的逼真人物形象需披露
    if is_ai_generated and (has_real_human or is_ai_modified):
        return True
    # AI 深度合成人物（即便以"真人"形式呈现）也必须披露
    if is_ai_modified and has_real_human:
        return True
    return False


def amazon_ai_metadata_tags(
    has_real_human: bool = False,
    is_ai_generated: bool = False,
    is_ai_modified: bool = False,
) -> list[str]:
    """返回应添加到图片元数据的 AI 披露标签列表（无需标注时返回空列表）。"""
    if not ai_image_label_required(has_real_human, is_ai_generated, is_ai_modified):
        return []
    tags = list(AMAZON_AI_IMAGE_POLICY["metadata_tags"])
    # 纯 AI 生成（无真人实拍混合）优先主标签
    if is_ai_generated and not is_ai_modified:
        return [tags[0], tags[1]]
    if is_ai_modified:
        return tags
    return [tags[1]]


def tiktok_ai_disclosure_required(
    is_ai_content: bool = False,
    is_product_appearance_modified: bool = False,
    is_fake_effect: bool = False,
) -> dict[str, Any]:
    """
    TikTok Shop AI 内容合规判定。

    Returns:
        {
            "need_disclosure": bool,   # 是否需要显著标注 AI 生成
            "violations": list[str],   # 违反的禁用项（非空 = 需整改）
            "risk_level": str,         # low / medium / high
        }
    """
    violations: list[str] = []
    if is_product_appearance_modified:
        violations.append("AI 篡改商品外观（禁止）")
    if is_fake_effect:
        violations.append("AI 捏造不实效果（禁止）")

    need_disclosure = is_ai_content or bool(violations)

    if violations:
        risk = "high"
    elif is_ai_content:
        risk = "medium"
    else:
        risk = "low"

    return {
        "need_disclosure": need_disclosure,
        "violations": violations,
        "risk_level": risk,
    }


def check_ai_content_compliance(
    platform: str = "all",
    image_has_real_human: bool = False,
    image_is_ai_generated: bool = False,
    image_is_ai_modified: bool = False,
    tiktok_is_ai_content: bool = False,
    tiktok_product_appearance_modified: bool = False,
    tiktok_fake_effect: bool = False,
) -> dict[str, Any]:
    """
    综合合规检查入口：输入素材属性 → 输出各平台合规清单。

    Args:
        platform: "amazon" / "tiktok" / "all"
        其余参数见各函数说明。

    Returns:
        {
            "summary": str,
            "items": [ {platform, status, action, detail} ... ],
            "risk_level": "low" | "medium" | "high",
            "all_pass": bool,
        }
    """
    items: list[dict[str, Any]] = []

    if platform in ("amazon", "all"):
        need_label = ai_image_label_required(
            has_real_human=image_has_real_human,
            is_ai_generated=image_is_ai_generated,
            is_ai_modified=image_is_ai_modified,
        )
        items.append({
            "platform": "Amazon",
            "status": "需标注" if need_label else "合规",
            "action": (
                "在图片元数据添加 AI 披露标签: "
                + ", ".join(
                    amazon_ai_metadata_tags(
                        has_real_human=image_has_real_human,
                        is_ai_generated=image_is_ai_generated,
                        is_ai_modified=image_is_ai_modified,
                    )
                )
                if need_label
                else "无人物图或纯实拍，无需 AI 人物披露标签"
            ),
            "detail": AMAZON_AI_IMAGE_POLICY["requirement"],
        })

    if platform in ("tiktok", "all"):
        tk = tiktok_ai_disclosure_required(
            is_ai_content=tiktok_is_ai_content,
            is_product_appearance_modified=tiktok_product_appearance_modified,
            is_fake_effect=tiktok_fake_effect,
        )
        items.append({
            "platform": "TikTok Shop",
            "status": "需整改" if tk["violations"] else ("需标注" if tk["need_disclosure"] else "合规"),
            "action": (
                "整改: " + "；".join(tk["violations"])
                if tk["violations"]
                else ("内容显著标注「AI 生成内容」" if tk["need_disclosure"] else "无 AI 内容，无需标注")
            ),
            "detail": TIKTOK_SHOP_AI_POLICY["requirement"],
        })

    risk = "high" if any(i["status"] == "需整改" for i in items) else (
        "medium" if any(i["status"] == "需标注" for i in items) else "low"
    )
    all_pass = all(i["status"] == "合规" for i in items)

    return {
        "summary": AI_CONTENT_POLICY["summary"],
        "items": items,
        "risk_level": risk,
        "all_pass": all_pass,
    }
