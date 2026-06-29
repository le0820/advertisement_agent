from __future__ import annotations

import unittest
from unittest.mock import patch

from core.storyboard_simulator import generate_storyboard_simulation


_FAKE = {
    "candidate_id": "C001",
    "keyframes": [
        {"keyframe_id": "KF01", "time": "0s", "frame_purpose": "hook",
         "image_prompt_cn": "微距针穿刺", "image_prompt_en": "macro needle",
         "negative_prompt": "no text", "continuity_notes": "暖金光",
         "product_fidelity_notes": "银白金属"}
    ],
    "storyboard_review": {
        "visual_consistency_risk": "low", "product_fidelity_risk": "low",
        "model_difficulty": "medium", "recommendation": "acceptable"
    }
}


class TestStoryboardSimulator(unittest.TestCase):
    @patch("core.storyboard_simulator.chat_json_object", return_value=dict(_FAKE))
    def test_generates_keyframes(self, _mock):
        brief = {"dense_caption": "戒指", "product_name": "对戒"}
        cand = {"candidate_id": "C001", "creative_route": "品牌大片",
                "shot_plan": [{"shot_id": "S01", "time_range": "0-3s"}]}
        sim = generate_storyboard_simulation(brief, cand)
        self.assertEqual(sim["candidate_id"], "C001")
        self.assertEqual(len(sim["keyframes"]), 1)
        self.assertEqual(sim["keyframes"][0]["keyframe_id"], "KF01")
        self.assertEqual(sim["storyboard_review"]["recommendation"], "acceptable")

    @patch(
        "core.storyboard_simulator.chat_json_object",
        return_value={"candidate_id": "C002"},
    )
    def test_missing_fields_filled(self, _mock):
        sim = generate_storyboard_simulation({}, {"candidate_id": "C002"})
        self.assertEqual(sim["candidate_id"], "C002")
        self.assertEqual(sim["keyframes"], [])
        self.assertEqual(sim["storyboard_review"]["recommendation"], "acceptable")
        self.assertEqual(sim["storyboard_review"]["model_difficulty"], "medium")


if __name__ == "__main__":
    unittest.main()
