from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import main


def _features():
    return {"category": "珠宝饰品", "sub_category": "情侣对戒",
            "product_name": "对戒", "selling_points": ["浪纹"],
            "target_audience": "情侣", "dense_caption": "银白金属戒",
            "distribution_scenarios": ["douyin"]}


def _cand(cid):
    return {"candidate_id": cid, "creative_route": "品牌大片", "hook": "h",
            "one_sentence_idea": "idea", "narrative_spine": "s", "shot_plan": [],
            "seedance_prompt_risk": {"risk_level": "low", "risk_reasons": []}}


_FAKE_SCORE_JSON = (
    '{"candidate_id": "C001", '
    '"scores": {"first_3_seconds_hook":90, "product_clarity":85, "brand_fit":80, '
    '"audience_relevance":80, "visual_memorability":85, "platform_fit":80, '
    '"seedance_feasibility":82, "generation_risk_control":80, "commercial_intent":80}, '
    '"strengths": [], "weaknesses": [], "revision_suggestions": [], '
    '"render_recommendation": "render"}'
)


class TestCliFastMode(unittest.TestCase):
    @patch("main.generate_final_prompt", return_value="FAST PROMPT")
    @patch("main.match_template",
           return_value={"template_id": "t", "template_name": "n"})
    @patch("main.extract_features", return_value=_features())
    def test_fast_mode_writes_txt_and_features(self, _f, _t, _p):
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "ring.jpg")
            open(img, "w").close()
            out = os.path.join(d, "out.txt")
            rc = main.main(["--mode", "fast", img, "-o", out])
            self.assertEqual(rc, 0)
            with open(out) as fh:
                self.assertEqual(fh.read(), "FAST PROMPT")
            self.assertTrue(os.path.exists(out.replace(".txt", ".features.json")))


class TestCliDecisionMode(unittest.TestCase):
    @patch("core.output_package.chat", return_value="# Brand Film Spec - 对戒\n\nFINAL SPEC")
    @patch("core.render_decision.chat_json_object")
    @patch("core.creative_scoring.chat_text", return_value=_FAKE_SCORE_JSON)
    @patch("core.creative_search.chat_json_array")
    @patch("main.match_template",
           return_value={"template_id": "t", "template_name": "n"})
    @patch("main.extract_features", return_value=_features())
    def test_decision_mode_writes_all_artifacts(self, _f, _t, mock_search, mock_score,
                                                mock_decision, _chat):
        mock_search.return_value = [_cand("C001")]
        mock_decision.return_value = {
            "recommended_candidate_id": "C001", "should_render": True,
            "confidence": 85, "reason": "值得", "expected_failure_modes": ["手部"],
            "pre_render_checklist": ["确认颜色"],
            "if_first_render_fails": {"likely_causes": ["手部"], "recommended_fix": "简化",
                                       "do_not_retry_if": ["颜色错"]}}
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "ring.jpg")
            open(img, "w").close()
            out = os.path.join(d, "out.txt")
            rc = main.main(["--mode", "decision", img, "-o", out,
                            "--num-candidates", "1", "--top-k", "1", "--min-score", "80"])
            self.assertEqual(rc, 0)
            stem = out[:-4]
            for suffix in [".features.json", ".brief.json", ".candidates.json",
                           ".scores.json", ".shortlist.json", ".decision.json",
                           ".package.json", ".brand-film-spec.md", ".report.md"]:
                self.assertTrue(os.path.exists(stem + suffix), f"missing {suffix}")
            with open(stem + ".brand-film-spec.md") as fh:
                self.assertIn("FINAL SPEC", fh.read())
            with open(stem + ".package.json") as fh:
                pkg = json.loads(fh.read())
            self.assertIn("brand_film_spec", pkg)
            self.assertEqual(pkg["selected_candidate"]["candidate_id"], "C001")


class TestCliExploreMode(unittest.TestCase):
    @patch("core.creative_scoring.chat_text", return_value=_FAKE_SCORE_JSON)
    @patch("core.creative_search.chat_json_array")
    @patch("main.match_template",
           return_value={"template_id": "t", "template_name": "n"})
    @patch("main.extract_features", return_value=_features())
    def test_explore_mode_skips_final_prompt(self, _f, _t, mock_search, mock_score):
        mock_search.return_value = [_cand("C001")]
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "ring.jpg")
            open(img, "w").close()
            out = os.path.join(d, "out.txt")
            rc = main.main(["--mode", "explore", img, "-o", out,
                            "--num-candidates", "1", "--top-k", "1"])
            self.assertEqual(rc, 0)
            stem = out[:-4]
            for suffix in [".features.json", ".brief.json", ".candidates.json",
                           ".scores.json", ".shortlist.json"]:
                self.assertTrue(os.path.exists(stem + suffix), f"missing {suffix}")
            self.assertFalse(os.path.exists(stem + ".decision.json"))
            self.assertFalse(os.path.exists(stem + ".package.json"))


if __name__ == "__main__":
    unittest.main()
