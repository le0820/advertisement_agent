from __future__ import annotations

import unittest
from unittest.mock import patch

from core.output_package import build_final_spec_package, build_report_md


_BRIEF = {
    "product_name": "错金浪纹对戒", "category": "珠宝饰品",
    "dense_caption": "宽版银白金属戒, 错金浪纹, 蓝宝石主石。",
    "selling_points": ["独特浪纹", "蓝宝石主石"], "target_audience": "22-35岁情侣",
    "brand_name": "", "brand_assets": {"slogan": "错金浪纹，见证唯一"},
    "commercial_goal": "creative_ad", "platform": "douyin",
    "aspect_ratio": "9:16", "duration_seconds": 15,
    "constraints": {"must_show_product_by_second": 3, "must_have_cta": False,
                    "avoid_face_generation": True, "avoid_complex_hand_motion": False},
}
_CAND = {"candidate_id": "C001", "creative_route": "品牌大片", "hook": "微距针穿刺",
         "one_sentence_idea": "金线生长成铠甲", "narrative_spine": "针→线→纹→龙",
         "shot_plan": [{"shot_id": "S01", "time_range": "0-3s", "purpose": "hook",
                        "visual": "微距", "camera": "慢推", "lighting": "侧逆光",
                        "sound": "落针声", "copy_or_voiceover": "",
                        "product_visibility": "partial"}]}
_SCORE = {"candidate_id": "C001", "scores": {"overall": 88},
          "render_recommendation": "render", "strengths": ["强hook"], "weaknesses": []}
_DECISION = {"recommended_candidate_id": "C001", "should_render": True, "confidence": 85,
             "reason": "强hook且可行", "expected_failure_modes": ["手部畸形"],
             "pre_render_checklist": ["确认产品颜色"],
             "if_first_render_fails": {"likely_causes": ["手部"], "recommended_fix": "简化手部",
                                        "do_not_retry_if": ["颜色错"]}}


class TestBuildFinalSpecPackage(unittest.TestCase):
    @patch("core.output_package.chat", return_value="# Brand Film Spec - 错金浪纹对戒\n\n规格书成品")
    def test_package_has_brand_film_spec_and_summary(self, _mock):
        pkg = build_final_spec_package(_BRIEF, _CAND, _SCORE, None, _DECISION)
        self.assertIn("Brand Film Spec", pkg["brand_film_spec"])
        self.assertTrue(pkg["summary"])
        self.assertEqual(pkg["selected_candidate"]["candidate_id"], "C001")
        self.assertIsNone(pkg["storyboard_simulation"])
        self.assertEqual(pkg["render_decision"]["recommended_candidate_id"], "C001")
        self.assertIsInstance(pkg["manual_upload_notes"], list)

    @patch("core.output_package.chat", return_value="成品")
    def test_report_answers_required_questions(self, _mock):
        pkg = build_final_spec_package(_BRIEF, _CAND, _SCORE, None, _DECISION)
        report = build_report_md(
            pkg,
            all_candidates_count=8,
            rejected=[{"candidate_id": "C002", "render_recommendation": "reject",
                       "scores": {"overall": 40}}],
            shortlisted=[{"candidate_id": "C001", "overall": 88,
                          "eligible_for_render": True, "ineligible_reasons": []}],
        )
        self.assertIn("8", report)
        self.assertIn("C001", report)
        self.assertIn("C002", report)
        self.assertIn("确认产品颜色", report)
        self.assertIn("简化手部", report)
        self.assertIn("强hook且可行", report)
        self.assertIn(".brand-film-spec.md", report)


if __name__ == "__main__":
    unittest.main()
