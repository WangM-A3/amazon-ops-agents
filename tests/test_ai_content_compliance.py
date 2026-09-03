"""
tests/test_ai_content_compliance.py — AI 内容合规层测试（v2.1 新增）
覆盖：亚马逊 AI 人物图打标判断、TikTok Shop AIGC 判定、综合检查入口
"""

import unittest

from compliance.ai_content_rules import (
    AMAZON_AI_IMAGE_POLICY,
    TIKTOK_SHOP_AI_POLICY,
    ai_image_label_required,
    amazon_ai_metadata_tags,
    check_ai_content_compliance,
    tiktok_ai_disclosure_required,
)


class TestAmazonAIImagePolicy(unittest.TestCase):
    def test_ai_generated_real_human_requires_label(self):
        self.assertTrue(
            ai_image_label_required(has_real_human=True, is_ai_generated=True)
        )

    def test_pure_product_no_human_no_label(self):
        self.assertFalse(
            ai_image_label_required(has_real_human=False, is_ai_generated=False)
        )

    def test_ai_modified_human_requires_label(self):
        self.assertTrue(
            ai_image_label_required(has_real_human=True, is_ai_modified=True)
        )

    def test_real_photo_no_label(self):
        # 真人实拍（非 AI 生成/修饰）无需 AI 披露标签
        self.assertFalse(
            ai_image_label_required(has_real_human=True, is_ai_generated=False, is_ai_modified=False)
        )

    def test_metadata_tags_content(self):
        tags = amazon_ai_metadata_tags(has_real_human=True, is_ai_generated=True)
        self.assertIn("contains-synthetic-performer", tags)
        self.assertIn("synthetic-media", tags)

    def test_no_tags_when_not_required(self):
        self.assertEqual(
            amazon_ai_metadata_tags(has_real_human=False, is_ai_generated=False),
            [],
        )

    def test_policy_has_source(self):
        self.assertIn("source", AMAZON_AI_IMAGE_POLICY)
        self.assertIn("risk_if_not_labeled", AMAZON_AI_IMAGE_POLICY)


class TestTikTokShopAIPolicy(unittest.TestCase):
    def test_ai_content_needs_disclosure(self):
        r = tiktok_ai_disclosure_required(is_ai_content=True)
        self.assertTrue(r["need_disclosure"])
        self.assertEqual(r["risk_level"], "medium")

    def test_appearance_modified_is_violation(self):
        r = tiktok_ai_disclosure_required(is_product_appearance_modified=True)
        self.assertTrue(r["violations"])
        self.assertEqual(r["risk_level"], "high")

    def test_fake_effect_is_violation(self):
        r = tiktok_ai_disclosure_required(is_fake_effect=True)
        self.assertTrue(any("AI 捏造不实效果" in v for v in r["violations"]))

    def test_plain_content_no_risk(self):
        r = tiktok_ai_disclosure_required()
        self.assertFalse(r["need_disclosure"])
        self.assertEqual(r["risk_level"], "low")

    def test_policy_has_forbidden_list(self):
        self.assertIn("forbidden", TIKTOK_SHOP_AI_POLICY)


class TestCheckAIContentCompliance(unittest.TestCase):
    def test_all_platforms_ai_human_image(self):
        r = check_ai_content_compliance(
            platform="all",
            image_has_real_human=True,
            image_is_ai_generated=True,
            tiktok_is_ai_content=True,
        )
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(r["risk_level"], "medium")  # 需标注（无违规）
        self.assertFalse(r["all_pass"])

    def test_amazon_only(self):
        r = check_ai_content_compliance(platform="amazon", image_has_real_human=True, image_is_ai_generated=True)
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["platform"], "Amazon")
        self.assertEqual(r["items"][0]["status"], "需标注")

    def test_all_pass_clean(self):
        r = check_ai_content_compliance(platform="all")
        self.assertTrue(r["all_pass"])
        self.assertEqual(r["risk_level"], "low")

    def test_tiktok_violation_high_risk(self):
        r = check_ai_content_compliance(
            platform="tiktok",
            tiktok_is_ai_content=True,
            tiktok_product_appearance_modified=True,
        )
        self.assertEqual(r["risk_level"], "high")
        self.assertEqual(r["items"][0]["status"], "需整改")


if __name__ == "__main__":
    unittest.main()
