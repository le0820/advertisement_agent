from __future__ import annotations

import unittest
from unittest.mock import patch

from core.render_decision import make_render_decision, pick_top_eligible


def _sl(cid, overall, eligible=True):
    return {
        "candidate_id": cid,
        "candidate": {"candidate_id": cid, "creative_route": "X", "shot_plan": []},
        "score": {"candidate_id": cid, "scores": {"overall": overall,
                                                   "seedance_feasibility": 80},
                  "render_recommendation": "render"},
        "overall": overall,
        "eligible_for_render": eligible,
        "ineligible_reasons": [] if eligible else ["x"],
    }


class TestPickTopEligible(unittest.TestCase):
    def test_picks_highest_eligible(self):
        sl = [_sl("C001", 80, False), _sl("C002", 90, True), _sl("C003", 85, True)]
        self.assertEqual(pick_top_eligible(sl), "C002")

    def test_none_eligible_returns_none(self):
        sl = [_sl("C001", 90, False)]
        self.assertIsNone(pick_top_eligible(sl))

    def test_empty_returns_none(self):
        self.assertIsNone(pick_top_eligible([]))


class TestMakeRenderDecision(unittest.TestCase):
    @patch("core.render_decision.chat_json_object")
    def test_should_render_true(self, mock_chat):
        mock_chat.return_value = {
            "recommended_candidate_id": "C002",
            "should_render": True, "confidence": 85,
            "reason": "强hook且可行", "expected_failure_modes": ["手部"],
            "pre_render_checklist": ["确认产品颜色"],
            "if_first_render_fails": {"likely_causes": ["手部畸形"],
                                       "recommended_fix": "简化手部",
                                       "do_not_retry_if": ["产品颜色错"]}
        }
        brief = {"product_name": "x"}
        sl = [_sl("C001", 80), _sl("C002", 90)]
        dec = make_render_decision(brief, sl, [])
        self.assertTrue(dec["should_render"])
        self.assertEqual(dec["recommended_candidate_id"], "C002")
        self.assertEqual(dec["confidence"], 85)
        self.assertIn("确认产品颜色", dec["pre_render_checklist"])

    @patch("core.render_decision.chat_json_object")
    def test_no_eligible_forces_should_render_false(self, mock_chat):
        mock_chat.return_value = {
            "recommended_candidate_id": "C001", "should_render": True,
            "confidence": 50, "reason": "", "expected_failure_modes": [],
            "pre_render_checklist": [],
            "if_first_render_fails": {"likely_causes": [], "recommended_fix": "",
                                       "do_not_retry_if": []}
        }
        sl = [_sl("C001", 90, eligible=False)]
        dec = make_render_decision({"x": 1}, sl, [])
        self.assertFalse(dec["should_render"])
        self.assertIsNone(dec["recommended_candidate_id"])

    @patch("core.render_decision.chat_json_object")
    def test_empty_shortlist_skips_render(self, mock_chat):
        mock_chat.return_value = {
            "recommended_candidate_id": None, "should_render": False,
            "confidence": 0, "reason": "无候选", "expected_failure_modes": [],
            "pre_render_checklist": [],
            "if_first_render_fails": {"likely_causes": [], "recommended_fix": "",
                                       "do_not_retry_if": []}
        }
        dec = make_render_decision({"x": 1}, [], [])
        self.assertFalse(dec["should_render"])
        self.assertIsNone(dec["recommended_candidate_id"])


if __name__ == "__main__":
    unittest.main()
