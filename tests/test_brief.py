from __future__ import annotations

import unittest

from core.brief import build_creative_brief


def _accessory_features():
    return {
        "schema_version": "2.0",
        "category": "服饰配件",
        "sub_category": "饰品",
        "product_name": "错金浪纹对戒",
        "selling_points": ["独特浪纹设计", "蓝色主石视觉"],
        "target_audience": "22-35岁情侣",
        "dense_caption": "宽版银白金属外观对戒，暖金浪纹和蓝色椭圆主石。",
        "visual_facts": {"colors": ["银白", "暖金", "蓝色"]},
        "truth_boundaries": {
            "observed": ["银白与暖金双色外观"],
            "inferred": [],
            "unknown": ["真实金属和宝石成分"],
            "forbidden_inferences": ["天然宝石", "贵金属纯度"],
        },
        "distribution_scenarios": ["douyin", "tiktok", "youtube"],
    }


def _apparel_features():
    return {
        "category": "服装鞋包",
        "sub_category": "高定礼服",
        "product_name": "不对称金绣白色礼服西装",
        "selling_points": ["金色刺绣外观", "不对称版型"],
        "target_audience": "30-45岁礼服消费者",
        "dense_caption": "白色礼服西装，肩线利落，腰线收束，金色刺绣和钉珠覆盖衣身。",
        "distribution_scenarios": ["douyin", "tiktok", "youtube"],
    }


class TestBuildCreativeBrief(unittest.TestCase):
    def test_defaults_include_v2_profile_snapshot(self):
        brief = build_creative_brief(_accessory_features())

        self.assertEqual(brief["schema_version"], "2.0")
        self.assertEqual(brief["category"], "服饰配件")
        self.assertEqual(brief["sub_category"], "饰品")
        self.assertEqual(brief["category_profile"]["profile_id"], "fashion_accessories_v2")
        self.assertTrue(brief["category_profile"]["critical_proof_groups"])
        self.assertEqual(sum(brief["category_profile"]["score_weights"].values()), 1.0)
        self.assertEqual(brief["commercial_goal"], "brand_film")
        self.assertEqual(brief["constraints"]["must_show_product_by_second"], 3)
        self.assertIn("天然宝石", brief["claim_boundaries"]["forbidden"])

    def test_legacy_categories_migrate_and_preserve_detail(self):
        features = _accessory_features()
        features["category"] = "珠宝饰品"
        features["sub_category"] = "情侣对戒"
        brief = build_creative_brief(features)

        self.assertEqual(brief["category"], "服饰配件")
        self.assertEqual(brief["sub_category"], "饰品")
        self.assertEqual(
            brief["taxonomy"]["subcategory_extension"]["candidate_name"],
            "情侣对戒",
        )

    def test_user_options_override(self):
        brief = build_creative_brief(_accessory_features(), {
            "platform": "xiaohongshu",
            "aspect_ratio": "16:9",
            "duration": 30,
            "commercial_goal": "brand_film",
            "slogan": "每一纹都有回声",
            "brand_name": "青雀",
        })
        self.assertEqual(brief["platform"], "xiaohongshu")
        self.assertEqual(brief["aspect_ratio"], "16:9")
        self.assertEqual(brief["duration_seconds"], 30)
        self.assertEqual(brief["commercial_goal"], "brand_film")
        self.assertEqual(brief["brand_assets"]["slogan"], "每一纹都有回声")
        self.assertEqual(brief["brand_name"], "青雀")

    def test_people_are_not_avoided_by_default(self):
        brief = build_creative_brief(_accessory_features(), {"commercial_goal": "brand_film"})
        policy = brief["constraints"]["person_policy"]
        self.assertFalse(brief["constraints"]["avoid_face_generation"])
        self.assertTrue(policy["face_allowed"])
        self.assertTrue(policy["human_body_allowed"])

    def test_manual_business_inputs(self):
        brief = build_creative_brief(_accessory_features(), {
            "target_audience": "30-40岁送礼人群",
            "selling_point": ["支持刻字", "礼盒可选"],
            "pain_point": "怕撞款",
            "usage_scene": "纪念日赠礼",
            "cta": "查看款式",
            "forbidden_claim": "天然蓝宝石",
        })
        self.assertEqual(brief["target_audience"], "30-40岁送礼人群")
        self.assertIn("支持刻字", brief["selling_points"])
        self.assertEqual(brief["pain_points"], ["怕撞款"])
        self.assertEqual(brief["usage_scenes"], ["纪念日赠礼"])
        self.assertEqual(brief["cta"], "查看款式")
        self.assertIn("天然蓝宝石", brief["brand_assets"]["forbidden_claims"])
        self.assertTrue(brief["constraints"]["must_have_cta"])

    def test_apparel_profile_requires_model_and_allows_face(self):
        brief = build_creative_brief(_apparel_features())
        policy = brief["constraints"]["person_policy"]

        self.assertEqual(brief["category"], "服饰配件")
        self.assertEqual(brief["sub_category"], "服装")
        self.assertTrue(policy["model_required"])
        self.assertTrue(policy["face_allowed"])
        self.assertIn("full body", policy["allowed_body_framing"])
        group_ids = {
            group["id"]
            for group in brief["category_profile"]["critical_proof_groups"]
        }
        self.assertIn("apparel_fit", group_ids)

    def test_explicit_avoid_face_keeps_body_proof(self):
        brief = build_creative_brief(_apparel_features(), {"avoid_face": True})
        policy = brief["constraints"]["person_policy"]

        self.assertFalse(policy["face_allowed"])
        self.assertTrue(policy["human_body_allowed"])
        self.assertTrue(policy["model_required"])
        self.assertIn("neck-down", policy["allowed_body_framing"])

    def test_custom_subcategory_is_preserved(self):
        features = {
            "category": "美妆个护",
            "sub_category": "私护清洁",
            "product_name": "管状私护洗液",
            "dense_caption": "粉色管状包装，标签可见。",
        }
        brief = build_creative_brief(features)

        self.assertEqual(brief["taxonomy"]["subcategory_status"], "custom")
        self.assertEqual(
            brief["taxonomy"]["subcategory_extension"]["candidate_name"],
            "私护清洁",
        )
        self.assertTrue(
            brief["taxonomy"]["subcategory_extension"]["future_profile_required"]
        )


if __name__ == "__main__":
    unittest.main()
