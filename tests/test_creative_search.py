from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.creative_search import (
    _normalize_candidate,
    generate_creative_candidates,
    validate_candidate_diversity,
)


_FAKE_LLM_OUTPUT = """
[
  {
    "creative_route": "品牌大片",
    "one_sentence_idea": "金线生长成铠甲",
    "hook": "微距绣针穿刺",
    "target_emotion": "震撼",
    "audience_insight": "渴望仪式感",
    "product_truth": "手工刺绣",
    "visual_metaphor": "金线蔓延",
    "narrative_spine": "针→线→纹→龙",
    "shot_plan": [{"shot_id": "S01", "time_range": "0-3s", "purpose": "hook",
                   "visual": "微距针穿刺", "camera": "慢推", "lighting": "侧逆光",
                   "sound": "落针声", "copy_or_voiceover": "",
                   "product_visibility": "partial"}],
    "seedance_prompt_risk": {"risk_level": "medium", "risk_reasons": ["手部细节"]}
  },
  {
    "creative_route": "产品感官特写",
    "one_sentence_idea": "材质舞蹈",
    "hook": "亮片闪烁",
    "target_emotion": "惊艳",
    "audience_insight": "看重工艺",
    "product_truth": "重工钉珠",
    "visual_metaphor": "亮片如星",
    "narrative_spine": "暗→光→绽放",
    "shot_plan": [],
    "seedance_prompt_risk": {"risk_level": "low", "risk_reasons": []}
  }
]
"""


class TestGenerateCreativeCandidates(unittest.TestCase):
    @patch(
        "core.creative_search.chat_json_array",
        return_value=json.loads(_FAKE_LLM_OUTPUT),
    )
    def test_generates_and_assigns_ids(self, _mock):
        brief = {"product_name": "礼服", "dense_caption": "刺绣礼服"}
        cands = generate_creative_candidates(brief, num_candidates=2)
        self.assertEqual(len(cands), 2)
        self.assertEqual(cands[0]["candidate_id"], "C001")
        self.assertEqual(cands[1]["candidate_id"], "C002")
        self.assertEqual(cands[0]["creative_route"], "品牌大片")
        self.assertIn("shot_plan", cands[0])
        self.assertIn("seedance_prompt_risk", cands[0])

    def test_missing_fields_filled(self):
        c = _normalize_candidate({"creative_route": "X"}, 1)
        self.assertEqual(c["candidate_id"], "C001")
        self.assertEqual(c["hook"], "")
        self.assertEqual(c["shot_plan"], [])
        self.assertEqual(c["seedance_prompt_risk"]["risk_level"], "medium")

    def test_invalid_risk_level_normalized(self):
        c = _normalize_candidate(
            {"creative_route": "X", "seedance_prompt_risk": {"risk_level": "extreme"}},
            1,
        )
        self.assertEqual(c["seedance_prompt_risk"]["risk_level"], "medium")


class TestValidateDiversity(unittest.TestCase):
    def _c(self, cid, route, hook="", metaphor="", shot_plan=None):
        return {
            "candidate_id": cid, "creative_route": route, "hook": hook,
            "visual_metaphor": metaphor, "shot_plan": shot_plan if shot_plan is not None else [],
        }

    def test_no_warnings_when_diverse(self):
        cands = [
            self._c("C001", "品牌大片", "微距针", "金线蔓延", [{"shot_id": "S01"}]),
            self._c("C002", "产品感官", "亮片闪", "亮片如星", [{"shot_id": "S01"}]),
        ]
        report = validate_candidate_diversity(cands, expected_count=2)
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["duplicate_routes"], [])
        self.assertEqual(report["empty_shot_plans"], [])

    def test_flags_duplicate_routes(self):
        cands = [self._c("C001", "品牌大片"), self._c("C002", "品牌大片")]
        report = validate_candidate_diversity(cands, expected_count=2)
        self.assertIn("C002", report["duplicate_routes"])
        self.assertTrue(any("creative_route" in w for w in report["warnings"]))

    def test_flags_duplicate_hooks(self):
        cands = [self._c("C001", "A", hook="微距针"), self._c("C002", "B", hook="微距针")]
        report = validate_candidate_diversity(cands, expected_count=2)
        self.assertTrue(any("hook" in w for w in report["warnings"]))

    def test_flags_duplicate_metaphors(self):
        cands = [
            self._c("C001", "A", metaphor="金线蔓延"),
            self._c("C002", "B", metaphor="金线蔓延"),
        ]
        report = validate_candidate_diversity(cands, expected_count=2)
        self.assertTrue(any("visual_metaphor" in w for w in report["warnings"]))

    def test_flags_empty_shot_plans(self):
        cands = [
            self._c("C001", "A", shot_plan=[]),
            self._c("C002", "B", shot_plan=[{"shot_id": "S01"}]),
        ]
        report = validate_candidate_diversity(cands, expected_count=2)
        self.assertIn("C001", report["empty_shot_plans"])

    def test_flags_count_mismatch(self):
        cands = [self._c("C001", "A")]
        report = validate_candidate_diversity(cands, expected_count=3)
        self.assertTrue(any("数量" in w or "count" in w.lower() for w in report["warnings"]))

    @patch(
        "core.creative_search.chat_json_array",
        return_value=[
            {"creative_route": "品牌大片", "hook": "h1", "visual_metaphor": "m1",
             "shot_plan": [{"shot_id": "S01"}]},
            {"creative_route": "品牌大片", "hook": "h1", "visual_metaphor": "m1",
             "shot_plan": []},
        ],
    )
    def test_generate_attaches_diversity_report(self, _mock):
        cands = generate_creative_candidates({"product_name": "x"}, num_candidates=3)
        self.assertEqual(len(cands), 2)
        # 每个候选都带 diversity_report
        for c in cands:
            self.assertIn("diversity_report", c)
        # 第二个候选应有 empty_shot_plan 警告
        self.assertIn("C002", cands[1]["diversity_report"]["empty_shot_plans"])


if __name__ == "__main__":
    unittest.main()
