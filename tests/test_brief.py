from __future__ import annotations

import unittest

from core.brief import build_creative_brief


def _features():
    return {
        "category": "珠宝饰品",
        "sub_category": "情侣对戒",
        "product_name": "错金浪纹对戒",
        "selling_points": ["独特浪纹设计", "蓝宝石主石"],
        "target_audience": "22-35岁情侣",
        "dense_caption": "宽版银白金属戒，错金浪纹，蓝宝石主石。",
        "distribution_scenarios": ["douyin", "tiktok", "youtube"],
    }


def _fashion_features():
    return {
        "category": "服装鞋包",
        "sub_category": "高定礼服",
        "product_name": "不对称金绣白色礼服西装",
        "selling_points": ["手工金绣", "不对称版型"],
        "target_audience": "30-45岁高定礼服消费者",
        "dense_caption": "白色礼服西装，肩线利落，腰线收束，金线刺绣和钉珠覆盖衣身。",
        "distribution_scenarios": ["douyin", "tiktok", "youtube"],
        "category_conflict": {
            "original_category": "珠宝饰品",
            "corrected_category": "服装鞋包",
            "reason": "检测到服装关键词",
            "matched_keywords": ["礼服", "西装"],
        },
    }


class TestBuildCreativeBrief(unittest.TestCase):
    def test_defaults_from_features(self):
        b = build_creative_brief(_features())
        self.assertEqual(b["product_name"], "错金浪纹对戒")
        self.assertEqual(b["category"], "珠宝饰品")
        self.assertEqual(b["selling_points"], ["独特浪纹设计", "蓝宝石主石"])
        self.assertEqual(b["platform"], "douyin")
        self.assertEqual(b["aspect_ratio"], "9:16")
        self.assertEqual(b["duration_seconds"], 15)
        self.assertEqual(b["commercial_goal"], "creative_ad")
        self.assertEqual(b["brand_stage"], "awareness")
        self.assertEqual(b["constraints"]["must_show_product_by_second"], 3)
        self.assertFalse(b["brand_assets"]["slogan"])

    def test_user_options_override(self):
        b = build_creative_brief(_features(), {
            "platform": "xiaohongshu", "aspect_ratio": "16:9",
            "duration": 30, "commercial_goal": "brand_film",
            "slogan": "每一针一线", "brand_name": "青雀",
        })
        self.assertEqual(b["platform"], "xiaohongshu")
        self.assertEqual(b["aspect_ratio"], "16:9")
        self.assertEqual(b["duration_seconds"], 30)
        self.assertEqual(b["commercial_goal"], "brand_film")
        self.assertEqual(b["brand_stage"], "awareness")
        self.assertEqual(b["brand_assets"]["slogan"], "每一针一线")
        self.assertEqual(b["brand_name"], "青雀")

    def test_sensitive_category_avoids_face(self):
        f = _features()
        b = build_creative_brief(f, {"commercial_goal": "brand_film"})
        self.assertTrue(b["constraints"]["avoid_face_generation"])

    def test_selling_points_string_coerced(self):
        f = _features()
        f["selling_points"] = "单一卖点"
        b = build_creative_brief(f)
        self.assertEqual(b["selling_points"], ["单一卖点"])

    def test_missing_distribution_defaults(self):
        f = _features()
        f.pop("distribution_scenarios")
        b = build_creative_brief(f)
        self.assertEqual(b["distribution_scenarios"], ["douyin", "tiktok", "youtube"])

    def test_manual_business_inputs(self):
        """GPT P4: 人工商业输入应进入 brief。"""
        b = build_creative_brief(_features(), {
            "target_audience": "30-40岁送礼男性",
            "selling_point": "可刻字定制",
            "pain_point": "怕撞款",
            "usage_scene": "纪念日赠礼",
            "cta": "点击定制专属对戒",
            "forbidden_claim": "最便宜",
        })
        self.assertEqual(b["target_audience"], "30-40岁送礼男性")
        self.assertIn("可刻字定制", b["selling_points"])
        self.assertEqual(b["pain_points"], ["怕撞款"])
        self.assertEqual(b["usage_scenes"], ["纪念日赠礼"])
        self.assertEqual(b["cta"], "点击定制专属对戒")
        self.assertEqual(b["brand_assets"]["forbidden_claims"], ["最便宜"])
        self.assertTrue(b["constraints"]["must_have_cta"])  # cta 隐含开启

    def test_selling_point_list_appends(self):
        b = build_creative_brief(_features(), {
            "selling_point": ["卖点A", "卖点B"],
        })
        self.assertIn("卖点A", b["selling_points"])
        self.assertIn("卖点B", b["selling_points"])
        # 原始卖点保留
        self.assertIn("独特浪纹设计", b["selling_points"])

    def test_fashion_person_policy_keeps_no_face_model_allowed(self):
        b = build_creative_brief(_fashion_features())
        policy = b["constraints"]["person_policy"]
        self.assertFalse(b["constraints"]["avoid_face_generation"])
        self.assertTrue(policy["face_allowed"])
        self.assertTrue(policy["human_body_allowed"])
        self.assertTrue(policy["hands_allowed"])
        self.assertTrue(policy["model_required"])
        self.assertIn("full body", policy["allowed_body_framing"])
        self.assertIn("natural face", policy["allowed_body_framing"])
        self.assertFalse(b["constraints"]["category_requirements"]["mannequin_only_allowed"])
        self.assertEqual(b["category_conflict"]["original_category"], "珠宝饰品")

    def test_fashion_can_still_explicitly_avoid_face(self):
        b = build_creative_brief(_fashion_features(), {"avoid_face": True})
        policy = b["constraints"]["person_policy"]
        self.assertTrue(b["constraints"]["avoid_face_generation"])
        self.assertFalse(policy["face_allowed"])
        self.assertTrue(policy["human_body_allowed"])
        self.assertIn("neck-down", policy["allowed_body_framing"])


if __name__ == "__main__":
    unittest.main()
