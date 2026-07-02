from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.extract_features import extract_features


class TestExtractFeatureGuardrails(unittest.TestCase):
    @patch("core.extract_features.chat_with_image")
    def test_corrects_haute_couture_suit_from_jewelry(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "category": "珠宝饰品",
            "sub_category": "设计师首饰",
            "product_name": "不对称金绣白色礼服西装",
            "selling_points": ["金线刺绣", "不对称版型"],
            "target_audience": "30-45岁高定礼服消费者",
            "dense_caption": "白色礼服西装，肩线利落，腰线收束，面料上有金绣和钉珠。",
        }, ensure_ascii=False)

        features = extract_features("suit.jpg")

        self.assertEqual(features["category"], "服装鞋包")
        self.assertEqual(features["sub_category"], "高定礼服")
        self.assertEqual(features["category_conflict"]["original_category"], "珠宝饰品")
        self.assertIn("礼服", features["category_conflict"]["matched_keywords"])

    @patch("core.extract_features.chat_with_image")
    def test_keeps_jewelry_when_product_name_is_jewelry(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "category": "珠宝饰品",
            "sub_category": "情侣对戒",
            "product_name": "蓝宝石对戒",
            "selling_points": ["蓝宝石主石"],
            "target_audience": "纪念日送礼人群",
            "dense_caption": "银白金属对戒，适合搭配晚宴裙佩戴。",
        }, ensure_ascii=False)

        features = extract_features("ring.jpg")

        self.assertEqual(features["category"], "珠宝饰品")
        self.assertEqual(features["sub_category"], "情侣对戒")
        self.assertNotIn("category_conflict", features)


if __name__ == "__main__":
    unittest.main()
