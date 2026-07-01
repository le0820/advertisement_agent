from __future__ import annotations

import unittest

from core.shortlist import select_shortlist


def _cand(cid, route="X"):
    return {"candidate_id": cid, "creative_route": route, "shot_plan": [],
            "seedance_prompt_risk": {"risk_level": "low", "risk_reasons": []}}


def _score(cid, overall, feasibility=80, clarity=80, rec="shortlist"):
    return {
        "candidate_id": cid,
        "scores": {
            "first_3_seconds_hook": overall, "product_clarity": clarity,
            "brand_fit": overall, "audience_relevance": overall,
            "visual_memorability": overall, "platform_fit": overall,
            "seedance_feasibility": feasibility,
            "generation_risk_control": overall, "commercial_intent": overall,
            "overall": overall,
        },
        "strengths": [], "weaknesses": [], "revision_suggestions": [],
        "render_recommendation": rec,
    }


class TestSelectShortlist(unittest.TestCase):
    def test_sorted_by_overall_desc(self):
        cands = [_cand("C001"), _cand("C002"), _cand("C003")]
        scores = [_score("C001", 70), _score("C002", 90), _score("C003", 80)]
        sl = select_shortlist(cands, scores, top_k=3, min_overall=0)
        self.assertEqual([s["candidate_id"] for s in sl], ["C002", "C003", "C001"])

    def test_min_overall_filter(self):
        cands = [_cand("C001"), _cand("C002")]
        scores = [_score("C001", 60), _score("C002", 90)]
        sl = select_shortlist(cands, scores, top_k=3, min_overall=80)
        self.assertEqual(len(sl), 1)
        self.assertEqual(sl[0]["candidate_id"], "C002")

    def test_low_feasibility_marks_ineligible(self):
        cands = [_cand("C001")]
        scores = [_score("C001", 95, feasibility=50)]
        sl = select_shortlist(cands, scores, top_k=3, min_feasibility=75)
        self.assertEqual(len(sl), 1)
        self.assertFalse(sl[0]["eligible_for_render"])
        self.assertTrue(sl[0]["ineligible_reasons"])

    def test_low_product_clarity_blocks_render(self):
        cands = [_cand("C001")]
        scores = [_score("C001", 95, clarity=60)]
        sl = select_shortlist(cands, scores, top_k=3)
        self.assertFalse(sl[0]["eligible_for_render"])
        self.assertTrue(any("product_clarity" in r or "产品" in r
                            for r in sl[0]["ineligible_reasons"]))

    def test_top_k_limit(self):
        cands = [_cand(f"C00{i}") for i in range(1, 5)]
        scores = [_score(f"C00{i}", 90 - i) for i in range(1, 5)]
        sl = select_shortlist(cands, scores, top_k=2)
        self.assertEqual(len(sl), 2)
        self.assertEqual(sl[0]["candidate_id"], "C001")

    def test_eligible_when_all_good(self):
        cands = [_cand("C001")]
        scores = [_score("C001", 90, feasibility=85, clarity=85, rec="render")]
        sl = select_shortlist(cands, scores, top_k=3)
        self.assertTrue(sl[0]["eligible_for_render"])
        self.assertEqual(sl[0]["ineligible_reasons"], [])
        self.assertEqual(sl[0]["overall"], 90)

    def test_candidate_score_pairing_by_id(self):
        cands = [_cand("C001"), _cand("C002")]
        scores = [_score("C002", 90), _score("C001", 70)]
        sl = select_shortlist(cands, scores, top_k=3)
        self.assertEqual(sl[0]["candidate_id"], "C002")

    def test_reject_recommendation_blocks_render(self):
        cands = [_cand("C001")]
        scores = [_score("C001", 95, rec="reject")]
        sl = select_shortlist(cands, scores, top_k=3)
        self.assertFalse(sl[0]["eligible_for_render"])

    def test_eligible_beats_higher_overall_ineligible(self):
        """GPT P0 bug: 低 overall 但可生成的候选不应被高 overall 不可生成候选挤掉。"""
        cands = [_cand("C001"), _cand("C002"), _cand("C003"), _cand("C004")]
        scores = [
            _score("C001", 95, clarity=60),   # ineligible (product_clarity<70)
            _score("C002", 93, feasibility=50),  # ineligible (feasibility<75)
            _score("C003", 91, rec="reject"),  # ineligible (reject)
            _score("C004", 88, feasibility=85, clarity=85, rec="render"),  # eligible
        ]
        sl = select_shortlist(cands, scores, top_k=3)
        # C004 (eligible) 应排在 ineligible 之前, 即使 overall 最低
        self.assertEqual(sl[0]["candidate_id"], "C004")
        self.assertTrue(sl[0]["eligible_for_render"])

    def test_top_k_picks_eligible_first(self):
        """top_k=1 时, eligible 候选优先于更高 overall 的 ineligible 候选。"""
        cands = [_cand("C001"), _cand("C002")]
        scores = [
            _score("C001", 95, clarity=60),  # ineligible
            _score("C002", 85, clarity=85, feasibility=85, rec="render"),  # eligible
        ]
        sl = select_shortlist(cands, scores, top_k=1)
        self.assertEqual(len(sl), 1)
        self.assertEqual(sl[0]["candidate_id"], "C002")
        self.assertTrue(sl[0]["eligible_for_render"])


if __name__ == "__main__":
    unittest.main()
