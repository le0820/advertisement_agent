from __future__ import annotations

import json
import unittest
from pathlib import Path

from core.brief import build_creative_brief
from core.category_profiles import (
    SCORE_DIMENSIONS,
    build_taxonomy,
    evaluate_candidate_gates,
    list_category_taxonomy,
    load_category_profiles,
    score_weights_for,
)


ROOT = Path(__file__).resolve().parent.parent


def _candidate(tags, *, first_seen=0.5, claims=None):
    return {
        "candidate_id": "C001",
        "category_strategy": {
            "product_first_seen_at": first_seen,
            "required_proofs_covered": list(tags),
            "proof_sequence": [],
            "claims_used": claims or [],
        },
        "shot_plan": [
            {
                "shot_id": "S01",
                "time_range": "0-3s",
                "product_visibility": "hero",
                "proof_tags": list(tags),
            }
        ],
    }


class TestCategoryProfiles(unittest.TestCase):
    def test_registry_is_exactly_three_categories(self):
        taxonomy = list_category_taxonomy()
        self.assertEqual(
            taxonomy,
            {
                "美妆个护": ["美甲", "美妆", "护肤品", "医美用品"],
                "食品饮料": ["零食", "饮料", "速冻速食", "预制菜"],
                "服饰配件": ["服装", "饰品", "鞋包"],
            },
        )

    def test_profile_weights_cover_v2_dimensions(self):
        profiles = load_category_profiles()
        for profile in profiles["categories"].values():
            weights = profile["scoring"]["weights"]
            self.assertEqual(set(weights), set(SCORE_DIMENSIONS))
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)

    def test_legacy_jewelry_maps_to_accessory_with_detail_preserved(self):
        taxonomy = build_taxonomy(
            "珠宝饰品",
            "情侣对戒",
            text="银白金属对戒与蓝色主石",
        )
        self.assertEqual(taxonomy["primary_category"], "服饰配件")
        self.assertEqual(taxonomy["subcategory"], "饰品")
        self.assertEqual(
            taxonomy["subcategory_extension"]["candidate_name"],
            "情侣对戒",
        )

    def test_custom_status_survives_when_name_is_only_in_extension(self):
        taxonomy = build_taxonomy(
            "美妆个护",
            "",
            status="custom",
            extension={
                "candidate_name": "私护清洁",
                "parent_hint": "美妆个护",
                "reason": "reserved subcategories do not fit",
                "future_profile_required": True,
            },
        )
        self.assertEqual(taxonomy["subcategory_status"], "custom")
        self.assertEqual(
            taxonomy["subcategory_extension"]["candidate_name"],
            "私护清洁",
        )

    def test_each_category_uses_distinct_weights(self):
        briefs = [
            build_creative_brief({"category": "美妆个护", "sub_category": "美妆", "product_name": "x", "dense_caption": "口红"}),
            build_creative_brief({"category": "食品饮料", "sub_category": "零食", "product_name": "x", "dense_caption": "巧克力"}),
            build_creative_brief({"category": "服饰配件", "sub_category": "服装", "product_name": "x", "dense_caption": "针织外套"}),
        ]
        weight_sets = [tuple(score_weights_for(brief).values()) for brief in briefs]
        self.assertEqual(len(set(weight_sets)), 3)

    def test_beauty_candidate_passes_structured_gates(self):
        brief = build_creative_brief({
            "category": "美妆个护",
            "sub_category": "美妆",
            "product_name": "唇部彩妆",
            "dense_caption": "粉色瓶装唇部彩妆",
        })
        tags = {
            "product_pack",
            "application_demo",
            "application_area_closeup",
            "finish_result",
            "hero_lock",
        }
        result = evaluate_candidate_gates(brief, _candidate(tags))
        self.assertTrue(result["passed"])
        self.assertEqual(result["critical_group_coverage"], 1.0)

    def test_food_missing_consumption_proof_fails(self):
        brief = build_creative_brief({
            "category": "食品饮料",
            "sub_category": "零食",
            "product_name": "巧克力",
            "dense_caption": "红色礼盒与独立巧克力",
        })
        tags = {"package_identity", "sensory_macro", "texture_macro", "pack_lock"}
        result = evaluate_candidate_gates(brief, _candidate(tags))
        self.assertFalse(result["passed"])
        self.assertTrue(any("food_use" in failure for failure in result["failures"]))

    def test_unsafe_high_risk_claim_fails(self):
        brief = build_creative_brief({
            "category": "食品饮料",
            "sub_category": "零食",
            "product_name": "儿童软糖",
            "dense_caption": "罐装彩色软糖",
        })
        tags = {"package_identity", "sensory_macro", "texture_macro", "consumption_or_serving", "pack_lock"}
        claims = [{"text": "促进儿童发育", "basis": "inferred", "risk_level": "high"}]
        result = evaluate_candidate_gates(brief, _candidate(tags, claims=claims))
        self.assertFalse(result["passed"])
        self.assertEqual(result["unsafe_claims"], ["促进儿童发育"])

    def test_reference_manifest_tracks_all_samples(self):
        manifest = json.loads(
            (ROOT / "harness" / "reference_video_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(manifest["samples"]), 11)
        counts = {}
        for sample in manifest["samples"]:
            counts[sample["primary_category"]] = counts.get(sample["primary_category"], 0) + 1
        self.assertEqual(counts, {"美妆个护": 4, "食品饮料": 4, "服饰配件": 3})


if __name__ == "__main__":
    unittest.main()
