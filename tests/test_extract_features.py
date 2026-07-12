from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.extract_features import extract_features


class TestExtractFeatureNormalization(unittest.TestCase):
    @patch("core.extract_features.chat_with_image")
    def test_legacy_jewelry_misclassification_becomes_apparel(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "category": "珠宝饰品",
            "sub_category": "设计师首饰",
            "product_name": "不对称金绣白色礼服西装",
            "selling_points": ["金色刺绣", "不对称版型"],
            "target_audience": "30-45岁礼服消费者",
            "dense_caption": "白色礼服西装，肩线利落，腰线收束，面料上有金绣和钉珠。",
        }, ensure_ascii=False)

        features = extract_features("suit.jpg")

        self.assertEqual(features["schema_version"], "2.0")
        self.assertEqual(features["category"], "服饰配件")
        self.assertEqual(features["sub_category"], "服装")
        self.assertEqual(features["taxonomy"]["primary_category_id"], "fashion_accessories_v2")
        self.assertEqual(features["category_conflict"]["original_category"], "珠宝饰品")

    @patch("core.extract_features.chat_with_image")
    def test_legacy_jewelry_becomes_accessory(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "category": "珠宝饰品",
            "sub_category": "情侣对戒",
            "product_name": "蓝色主石对戒",
            "selling_points": ["蓝色主石视觉"],
            "target_audience": "纪念日送礼人群",
            "dense_caption": "银白金属外观对戒，暖金纹理和蓝色椭圆主石。",
        }, ensure_ascii=False)

        features = extract_features("ring.jpg")

        self.assertEqual(features["category"], "服饰配件")
        self.assertEqual(features["sub_category"], "饰品")
        self.assertEqual(
            features["taxonomy"]["subcategory_extension"]["candidate_name"],
            "情侣对戒",
        )

    @patch("core.extract_features.chat_with_image")
    def test_accepts_nested_v2_product_understanding(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "schema_version": "2.0",
            "product_identity": {
                "product_name": "多色甲油",
                "visible_brand_text": ["TEST"],
                "visible_product_text": ["NAIL"],
                "variant_or_set": "多色",
            },
            "taxonomy": {
                "primary_category": "美妆个护",
                "subcategory": "美甲",
                "subcategory_confidence": 0.95,
                "subcategory_evidence": ["IMG01 可见指甲和甲油瓶"],
                "subcategory_extension": {},
            },
            "visual_facts": {
                "product_form": ["瓶装"],
                "colors": ["绿色", "蓝色"],
                "visible_material_appearance": ["玻璃感瓶身"],
                "packaging": ["小瓶"],
                "visible_details": ["猫眼光泽"],
                "usage_cues": ["完成甲面"],
            },
            "commercial_hypotheses": {
                "selling_points": ["多色选择"],
                "target_audiences": ["美甲用户"],
                "usage_scenes": ["美甲店"],
                "consumer_tensions": ["希望色彩有变化"],
            },
            "truth_boundaries": {
                "observed": ["IMG01 可见猫眼光泽"],
                "inferred": [],
                "unknown": ["成分"],
                "forbidden_inferences": ["无毒"],
            },
            "dense_caption": "多色瓶装甲油与猫眼光泽甲面。",
        }, ensure_ascii=False)

        features = extract_features("nail.jpg")

        self.assertEqual(features["category"], "美妆个护")
        self.assertEqual(features["sub_category"], "美甲")
        self.assertEqual(features["product_identity"]["visible_brand_text"], ["TEST"])
        self.assertEqual(features["truth_boundaries"]["forbidden_inferences"], ["无毒"])
        self.assertEqual(features["source_images"][0]["source"], "nail.jpg")


if __name__ == "__main__":
    unittest.main()
