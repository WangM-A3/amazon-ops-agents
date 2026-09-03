"""
Amazon Ops Silicon Army - Compliance 合规模块
包含：AI 内容合规（亚马逊/TikTok Shop AI 生成内容标注）、传统政策合规检查
"""

from .ai_content_rules import (
    AI_CONTENT_POLICY,
    AMAZON_AI_IMAGE_POLICY,
    TIKTOK_SHOP_AI_POLICY,
    check_ai_content_compliance,
    ai_image_label_required,
    amazon_ai_metadata_tags,
    tiktok_ai_disclosure_required,
)

__all__ = [
    "AI_CONTENT_POLICY",
    "AMAZON_AI_IMAGE_POLICY",
    "TIKTOK_SHOP_AI_POLICY",
    "check_ai_content_compliance",
    "ai_image_label_required",
    "amazon_ai_metadata_tags",
    "tiktok_ai_disclosure_required",
]
