from __future__ import annotations

import unittest

from core.storyboard import list_categories, match_template


class TestStoryboards(unittest.TestCase):
    def test_only_three_profile_categories_are_available(self):
        categories = list_categories()
        self.assertEqual(set(categories), {"美妆个护", "食品饮料", "服饰配件"})
        self.assertEqual(categories["美妆个护"], ["美甲", "美妆", "护肤品", "医美用品"])
        self.assertEqual(categories["食品饮料"], ["零食", "饮料", "速冻速食", "预制菜"])
        self.assertEqual(categories["服饰配件"], ["服装", "饰品", "鞋包"])

    def test_subcategory_uses_base_template_and_profile_override(self):
        template = match_template("服饰配件", "饰品")
        self.assertIsNotNone(template)
        self.assertEqual(template["template_id"], "fashion_accessories_base_001")
        self.assertEqual(template["resolved_taxonomy"]["subcategory"], "饰品")
        group_ids = {
            group["id"]
            for group in template["category_profile"]["critical_proof_groups"]
        }
        self.assertIn("accessory_scale", group_ids)
        self.assertIn("accessory_craft", group_ids)

    def test_legacy_category_is_migrated_but_not_listed(self):
        self.assertNotIn("珠宝饰品", list_categories())
        template = match_template("珠宝饰品", "情侣对戒")
        self.assertEqual(template["resolved_taxonomy"]["primary_category"], "服饰配件")
        self.assertEqual(template["resolved_taxonomy"]["subcategory"], "饰品")


if __name__ == "__main__":
    unittest.main()
