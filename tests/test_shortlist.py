from __future__ import annotations

import unittest

from core.shortlist import select_shortlist


def _candidate(candidate_id):
    return {"candidate_id": candidate_id, "creative_route": "X", "shot_plan": []}


def _score(
    candidate_id,
    overall,
    *,
    feasibility=80,
    truth=80,
    proof=80,
    risk=80,
    recommendation="shortlist",
    gates_passed=True,
):
    return {
        "score_version": "2.0",
        "candidate_id": candidate_id,
        "profile_id": "test_profile",
        "scores": {
            "hook_strength": overall,
            "product_truth_fidelity": truth,
            "category_proof_coverage": proof,
            "consumer_relevance": overall,
            "brand_fit": overall,
            "visual_memorability": overall,
            "narrative_coherence": overall,
            "platform_fit": overall,
            "renderer_feasibility": feasibility,
            "risk_control": risk,
            "commercial_intent": overall,
            "overall": overall,
        },
        "hard_gate_results": {
            "passed": gates_passed,
            "skipped": False,
            "failures": [] if gates_passed else ["missing critical proof"],
        },
        "render_recommendation": recommendation,
    }


class TestSelectShortlist(unittest.TestCase):
    def test_sorted_by_overall_desc(self):
        candidates = [_candidate("C001"), _candidate("C002"), _candidate("C003")]
        scores = [_score("C001", 70), _score("C002", 90), _score("C003", 80)]
        shortlist = select_shortlist(candidates, scores, top_k=3, min_overall=0)
        self.assertEqual([row["candidate_id"] for row in shortlist], ["C002", "C003", "C001"])

    def test_min_overall_filter(self):
        candidates = [_candidate("C001"), _candidate("C002")]
        scores = [_score("C001", 60), _score("C002", 90)]
        shortlist = select_shortlist(candidates, scores, top_k=3, min_overall=80)
        self.assertEqual([row["candidate_id"] for row in shortlist], ["C002"])

    def test_low_renderer_feasibility_marks_ineligible(self):
        shortlist = select_shortlist(
            [_candidate("C001")],
            [_score("C001", 95, feasibility=50)],
            min_feasibility=75,
        )
        self.assertFalse(shortlist[0]["eligible_for_render"])
        self.assertTrue(any("renderer_feasibility" in reason for reason in shortlist[0]["ineligible_reasons"]))

    def test_low_product_truth_blocks_render(self):
        shortlist = select_shortlist(
            [_candidate("C001")],
            [_score("C001", 95, truth=60)],
        )
        self.assertFalse(shortlist[0]["eligible_for_render"])
        self.assertTrue(any("product_truth_fidelity" in reason for reason in shortlist[0]["ineligible_reasons"]))

    def test_low_category_proof_blocks_render(self):
        shortlist = select_shortlist(
            [_candidate("C001")],
            [_score("C001", 95, proof=60)],
        )
        self.assertFalse(shortlist[0]["eligible_for_render"])
        self.assertTrue(any("category_proof_coverage" in reason for reason in shortlist[0]["ineligible_reasons"]))

    def test_failed_hard_gate_blocks_render(self):
        shortlist = select_shortlist(
            [_candidate("C001")],
            [_score("C001", 95, gates_passed=False)],
        )
        self.assertFalse(shortlist[0]["eligible_for_render"])
        self.assertIn("missing critical proof", shortlist[0]["ineligible_reasons"])

    def test_revise_and_reject_are_ineligible(self):
        candidates = [_candidate("C001"), _candidate("C002")]
        scores = [
            _score("C001", 95, recommendation="revise"),
            _score("C002", 94, recommendation="reject"),
        ]
        shortlist = select_shortlist(candidates, scores, top_k=2)
        self.assertTrue(all(not row["eligible_for_render"] for row in shortlist))

    def test_eligible_when_all_good(self):
        shortlist = select_shortlist(
            [_candidate("C001")],
            [_score("C001", 90, feasibility=85, truth=85, proof=85, risk=85, recommendation="render")],
        )
        self.assertTrue(shortlist[0]["eligible_for_render"])
        self.assertEqual(shortlist[0]["ineligible_reasons"], [])

    def test_candidate_score_pairing_by_id(self):
        candidates = [_candidate("C001"), _candidate("C002")]
        scores = [_score("C002", 90), _score("C001", 70)]
        shortlist = select_shortlist(candidates, scores, top_k=3)
        self.assertEqual(shortlist[0]["candidate_id"], "C002")

    def test_eligible_beats_higher_overall_ineligible(self):
        candidates = [_candidate("C001"), _candidate("C002"), _candidate("C003"), _candidate("C004")]
        scores = [
            _score("C001", 95, truth=60),
            _score("C002", 93, feasibility=50),
            _score("C003", 91, recommendation="reject"),
            _score("C004", 88, feasibility=85, truth=85, proof=85, recommendation="render"),
        ]
        shortlist = select_shortlist(candidates, scores, top_k=3)
        self.assertEqual(shortlist[0]["candidate_id"], "C004")
        self.assertTrue(shortlist[0]["eligible_for_render"])

    def test_top_k_picks_eligible_first(self):
        candidates = [_candidate("C001"), _candidate("C002")]
        scores = [
            _score("C001", 95, proof=60),
            _score("C002", 85, feasibility=85, truth=85, proof=85, recommendation="render"),
        ]
        shortlist = select_shortlist(candidates, scores, top_k=1)
        self.assertEqual([row["candidate_id"] for row in shortlist], ["C002"])


if __name__ == "__main__":
    unittest.main()
