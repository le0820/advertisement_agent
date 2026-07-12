from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.brief import build_creative_brief
from core.category_profiles import SCORE_DIMENSIONS, score_weights_for
from core.creative_scoring import (
    SCORE_WEIGHTS,
    compute_overall,
    score_creative_candidate,
    score_creative_candidates,
)


def _score_payload(value=90, recommendation="render"):
    return json.dumps({
        "scores": {dimension: value for dimension in SCORE_DIMENSIONS},
        "strengths": ["证据链清楚"],
        "weaknesses": [],
        "revision_suggestions": [],
        "render_recommendation": recommendation,
    }, ensure_ascii=False)


def _brief(category="美妆个护", subcategory="美妆"):
    caption = {
        "美妆个护": "粉色瓶装唇部彩妆，透明高光质地。",
        "食品饮料": "红色礼盒与独立巧克力，表面可见可可粉。",
        "服饰配件": "灰色麻花纹针织开衫，完整上身轮廓。",
    }[category]
    return build_creative_brief({
        "category": category,
        "sub_category": subcategory,
        "product_name": "测试产品",
        "dense_caption": caption,
    })


def _candidate(category="美妆个护", *, complete=True, unsafe_claim=False):
    tags_by_category = {
        "美妆个护": {
            "product_pack", "application_demo", "application_area_closeup",
            "finish_result", "hero_lock",
        },
        "食品饮料": {
            "package_identity", "sensory_macro", "texture_macro",
            "consumption_or_serving", "pack_lock",
        },
        "服饰配件": {
            "on_body_or_carry", "worn_full_view", "material_construction",
            "silhouette_fit", "use_occasion", "hero_lock",
        },
    }
    tags = tags_by_category[category] if complete else {next(iter(tags_by_category[category]))}
    claims = []
    if unsafe_claim:
        claims = [{"text": "保证永久有效", "basis": "inferred", "risk_level": "high"}]
    return {
        "candidate_id": "C001",
        "creative_route": "证据品牌片",
        "product_truth": "只使用可见事实",
        "category_strategy": {
            "product_first_seen_at": 0.5,
            "required_proofs_covered": list(tags),
            "proof_sequence": [],
            "claims_used": claims,
        },
        "shot_plan": [{
            "shot_id": "S01",
            "time_range": "0-3s",
            "product_visibility": "hero",
            "proof_tags": list(tags),
        }],
    }


class TestComputeOverall(unittest.TestCase):
    def test_default_weights_cover_every_dimension(self):
        self.assertEqual(set(SCORE_WEIGHTS), set(SCORE_DIMENSIONS))
        self.assertAlmostEqual(sum(SCORE_WEIGHTS.values()), 1.0, places=9)

    def test_weighted_average(self):
        scores = {dimension: index * 7 for index, dimension in enumerate(SCORE_DIMENSIONS, 1)}
        expected = round(sum(scores[key] * SCORE_WEIGHTS[key] for key in SCORE_DIMENSIONS))
        self.assertEqual(compute_overall(scores), expected)

    def test_category_weights_change_overall(self):
        scores = {dimension: 50 for dimension in SCORE_DIMENSIONS}
        scores["category_proof_coverage"] = 100
        beauty_weights = score_weights_for(_brief("美妆个护", "美妆"))
        fashion_weights = score_weights_for(_brief("服饰配件", "服装"))
        self.assertNotEqual(
            compute_overall(scores, beauty_weights),
            compute_overall(scores, fashion_weights),
        )


class TestScoreCandidate(unittest.TestCase):
    @patch("core.creative_scoring.chat_text", return_value=_score_payload())
    def test_score_uses_profile_weights_and_v2_contract(self, _mock):
        brief = _brief()
        result = score_creative_candidate(brief, _candidate())

        self.assertEqual(result["score_version"], "2.0")
        self.assertEqual(result["profile_id"], "beauty_personal_care_v2")
        self.assertEqual(result["weights"], score_weights_for(brief))
        self.assertTrue(result["hard_gate_results"]["passed"])
        self.assertEqual(
            result["scores"]["overall"],
            compute_overall(result["scores"], result["weights"]),
        )
        self.assertEqual(result["render_recommendation"], "render")

    @patch("core.creative_scoring.chat_text", return_value=_score_payload())
    def test_score_candidates_returns_list(self, _mock):
        brief = _brief()
        first = _candidate()
        second = _candidate()
        second["candidate_id"] = "C002"
        results = score_creative_candidates(brief, [first, second])
        self.assertEqual([row["candidate_id"] for row in results], ["C001", "C002"])

    @patch(
        "core.creative_scoring.chat_text",
        return_value='{"scores":{"hook_strength":50},"render_recommendation":"reject"}',
    )
    def test_missing_score_dimensions_default_zero(self, _mock):
        result = score_creative_candidate(
            {"platform": "douyin"},
            {"candidate_id": "C001"},
        )
        for dimension in SCORE_DIMENSIONS:
            self.assertIn(dimension, result["scores"])
        self.assertEqual(result["scores"]["hook_strength"], 50)
        self.assertEqual(result["scores"]["product_truth_fidelity"], 0)
        self.assertEqual(
            result["scores"]["overall"],
            compute_overall(result["scores"], result["weights"]),
        )

    @patch("core.creative_scoring.chat_text", return_value=_score_payload())
    def test_score_model_override(self, mock_chat):
        score_creative_candidate(
            _brief(),
            _candidate(),
            score_model="custom-judge",
        )
        self.assertEqual(mock_chat.call_args.kwargs["model"], "custom-judge")

    @patch("core.creative_scoring.chat_text", return_value=_score_payload())
    def test_missing_category_proofs_forces_revision(self, _mock):
        result = score_creative_candidate(_brief(), _candidate(complete=False))

        self.assertFalse(result["hard_gate_results"]["passed"])
        self.assertLess(result["scores"]["category_proof_coverage"], 70)
        self.assertEqual(result["render_recommendation"], "revise")
        self.assertTrue(any("品类关键证据" in item for item in result["weaknesses"]))

    @patch("core.creative_scoring.chat_text", return_value=_score_payload())
    def test_unsafe_claim_caps_risk_control(self, _mock):
        result = score_creative_candidate(
            _brief("食品饮料", "零食"),
            _candidate("食品饮料", unsafe_claim=True),
        )
        self.assertLessEqual(result["scores"]["risk_control"], 40)
        self.assertEqual(result["render_recommendation"], "revise")

    @patch("core.creative_scoring.chat_text", return_value=_score_payload())
    def test_complete_apparel_candidate_can_render(self, _mock):
        result = score_creative_candidate(
            _brief("服饰配件", "服装"),
            _candidate("服饰配件"),
        )
        self.assertTrue(result["hard_gate_results"]["passed"])
        self.assertGreaterEqual(result["scores"]["category_proof_coverage"], 75)
        self.assertEqual(result["render_recommendation"], "render")


if __name__ == "__main__":
    unittest.main()
