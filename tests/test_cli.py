from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import main


def _features():
    return {"category": "服饰配件", "sub_category": "饰品",
            "product_name": "对戒", "selling_points": ["浪纹"],
            "target_audience": "情侣", "dense_caption": "银白金属戒",
            "distribution_scenarios": ["douyin"]}


def _cand(cid):
    proof_tags = ["product_macro", "worn_scale", "craft_detail",
                  "styling_context", "accessory_hero"]
    return {"candidate_id": cid, "creative_route": "品牌大片", "hook": "h",
            "one_sentence_idea": "idea", "narrative_spine": "s",
            "product_truth": "银白金属外观戒指",
            "category_strategy": {
                "profile_id": "fashion_accessories_v2", "subcategory_id": "accessory",
                "consumer_tension": "纪念物需要独特视觉", "product_first_seen_at": 0.5,
                "proof_sequence": [], "required_proofs_covered": proof_tags,
                "claims_used": [],
                "product_fidelity_lock": {"must_keep": ["银白色"],
                                          "must_not_add": ["logo"],
                                          "cross_shot_continuity": ["结构不变"]},
                "reference_pattern_ids": ["A01"]},
            "shot_plan": [{"shot_id": "S01", "time_range": "0-3s",
                           "purpose": "hook", "visual": "佩戴微距",
                           "camera": "慢推", "lighting": "侧光", "sound": "轻响",
                           "copy_or_voiceover": "", "product_visibility": "hero",
                           "proof_tags": proof_tags, "product_fidelity": "结构不变"}],
            "renderer_risk": {"risk_level": "low", "risk_reasons": [],
                              "fallback": "静态佩戴"}}


_FAKE_SCORE_JSON = (
    '{"candidate_id": "C001", '
    '"scores": {"hook_strength":90, "product_truth_fidelity":90, '
    '"category_proof_coverage":90, "consumer_relevance":85, "brand_fit":80, '
    '"visual_memorability":85, "narrative_coherence":85, "platform_fit":80, '
    '"renderer_feasibility":85, "risk_control":85, "commercial_intent":80}, '
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
            "decision_evidence": ["品类证据完整"], "blocking_gates": [],
            "pre_render_checklist": ["确认颜色"],
            "renderer_plan": {"adapter_requirements": ["结构不变"],
                              "optional_keyframes": [], "retry_budget": 1,
                              "replace_candidate_on": ["产品变款"]},
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


class TestCliCodexMode(unittest.TestCase):
    @patch("main.extract_features")
    def test_codex_mode_writes_run_context_without_llm_calls(self, mock_extract):
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "hero.jpg")
            ref = os.path.join(d, "macro.jpg")
            out = os.path.join(d, "out.txt")
            rc = main.main([
                "--mode", "codex", img, "-o", out,
                "--reference-image", ref,
                "--commercial-goal", "brand_film",
                "--platform", "douyin",
            ])

            self.assertEqual(rc, 0)
            mock_extract.assert_not_called()
            context_path = out.replace(".txt", ".codex-run.json")
            self.assertTrue(os.path.exists(context_path))
            with open(context_path) as fh:
                context = json.loads(fh.read())
            self.assertEqual(context["owner_agent"]["id"], "codex")
            self.assertEqual(context["model_policy"]["external_llm_vlm_runtime"],
                             "disabled_by_default")
            self.assertEqual(len(context["image_inputs"]), 2)
            self.assertEqual(context["user_options"]["commercial_goal"], "brand_film")
            self.assertEqual(context["reference_evidence"]["sample_count"], 11)
            self.assertEqual(set(context["available_categories"]),
                             {"美妆个护", "食品饮料", "服饰配件"})

    @patch("main.extract_features")
    def test_codex_is_default_mode(self, mock_extract):
        with tempfile.TemporaryDirectory() as directory:
            image = os.path.join(directory, "hero.jpg")
            output = os.path.join(directory, "out")
            rc = main.main([image, "-o", output, "--category-hint", "美妆个护"])

            self.assertEqual(rc, 0)
            mock_extract.assert_not_called()
            with open(output + ".codex-run.json") as handle:
                context = json.load(handle)
            self.assertEqual(context["user_options"]["category_hint"], "美妆个护")


if __name__ == "__main__":
    unittest.main()
