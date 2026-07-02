from __future__ import annotations

import unittest

from core.storyboard import list_categories, match_template


class TestStoryboards(unittest.TestCase):
    def test_fashion_category_is_available(self):
        categories = list_categories()
        self.assertIn("服装鞋包", categories)
        self.assertIn("高定礼服", categories["服装鞋包"])
        self.assertIn("晚宴礼服", categories["服装鞋包"])
        self.assertIn("女装连衣裙", categories["服装鞋包"])

    def test_matches_haute_couture_template(self):
        template = match_template("服装鞋包", "高定礼服")
        self.assertIsNotNone(template)
        self.assertEqual(template["template_id"], "fashion_haute_couture_001")
        self.assertIn("真人模特上身或全身", template["required_visual_proofs"])
        self.assertIn("full body", template["allowed_person_policy"])
        self.assertIn("natural face", template["allowed_person_policy"])


if __name__ == "__main__":
    unittest.main()
