from __future__ import annotations

import unittest
from unittest.mock import patch

from core.creative_scoring import (
    SCORE_WEIGHTS,
    compute_overall,
    score_creative_candidate,
    score_creative_candidates,
)


_FAKE_SCORE = {
    "candidate_id": "C001",
    "scores": {
        "first_3_seconds_hook": 90, "product_clarity": 80, "brand_fit": 70,
        "audience_relevance": 75, "visual_memorability": 85, "platform_fit": 80,
        "seedance_feasibility": 60, "generation_risk_control": 70,
        "commercial_intent": 75
    },
    "strengths": ["强hook"], "weaknesses": ["手部风险"],
    "revision_suggestions": ["简化手部"], "render_recommendation": "shortlist"
}


class TestComputeOverall(unittest.TestCase):
    def test_weighted_average(self):
        overall = compute_overall(_FAKE_SCORE["scores"])
        expected = round(
            90 * 0.15 + 80 * 0.15 + 70 * 0.10 + 75 * 0.10 + 85 * 0.15
            + 80 * 0.10 + 60 * 0.15 + 70 * 0.05 + 75 * 0.05
        )
        self.assertEqual(overall, expected)

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(SCORE_WEIGHTS.values()), 1.0, places=6)


class TestScoreCandidate(unittest.TestCase):
    @patch("core.creative_scoring.chat_json_object", return_value=dict(_FAKE_SCORE))
    def test_score_fills_overall(self, _mock):
        brief = {"product_name": "x"}
        cand = {"candidate_id": "C001", "creative_route": "品牌大片"}
        result = score_creative_candidate(brief, cand)
        self.assertEqual(result["candidate_id"], "C001")
        self.assertIn("overall", result["scores"])
        self.assertEqual(result["scores"]["overall"], compute_overall(_FAKE_SCORE["scores"]))
        self.assertEqual(result["render_recommendation"], "shortlist")

    @patch("core.creative_scoring.chat_json_object", return_value=dict(_FAKE_SCORE))
    def test_score_candidates_returns_list(self, _mock):
        brief = {"product_name": "x"}
        cands = [{"candidate_id": "C001"}, {"candidate_id": "C002"}]
        results = score_creative_candidates(brief, cands)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["candidate_id"], "C001")

    @patch(
        "core.creative_scoring.chat_json_object",
        return_value={"candidate_id": "C001", "scores": {"first_3_seconds_hook": 50},
                      "render_recommendation": "reject"},
    )
    def test_missing_score_dims_default_zero(self, _mock):
        result = score_creative_candidate({"x": 1}, {"candidate_id": "C001"})
        for dim in SCORE_WEIGHTS:
            self.assertIn(dim, result["scores"])
        self.assertEqual(result["scores"]["first_3_seconds_hook"], 50)
        self.assertEqual(result["scores"]["product_clarity"], 0)
        self.assertEqual(result["scores"]["overall"], round(50 * 0.15))


if __name__ == "__main__":
    unittest.main()
