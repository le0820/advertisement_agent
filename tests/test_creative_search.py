from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.creative_search import _normalize_candidate, generate_creative_candidates


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


if __name__ == "__main__":
    unittest.main()
