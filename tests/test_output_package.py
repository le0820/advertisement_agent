from __future__ import annotations

import unittest
from unittest.mock import patch

from core.brief import build_creative_brief
from core.output_package import build_final_spec_package, build_report_md


_BRIEF = build_creative_brief({
    "category": "服饰配件",
    "sub_category": "饰品",
    "product_name": "错金浪纹对戒",
    "dense_caption": "宽版银白金属外观对戒，暖金浪纹和蓝色椭圆主石。",
    "selling_points": ["独特浪纹", "蓝色主石视觉"],
    "target_audience": "22-35岁情侣",
    "truth_boundaries": {
        "observed": ["银白与暖金双色外观"],
        "inferred": [],
        "unknown": ["材质成分"],
        "forbidden_inferences": ["天然宝石", "贵金属纯度"],
    },
}, {"commercial_goal": "brand_film"})

_CANDIDATE = {
    "candidate_id": "C001",
    "creative_route": "材质工艺",
    "one_sentence_idea": "两道纹理在同一束光中相遇",
    "category_strategy": {
        "product_fidelity_lock": {
            "must_keep": ["银白、暖金与蓝色"],
            "must_not_add": ["品牌 logo", "天然宝石 claim"],
            "cross_shot_continuity": ["两枚戒指结构不变"],
        }
    },
    "shot_plan": [],
}

_SCORE = {
    "score_version": "2.0",
    "candidate_id": "C001",
    "scores": {"overall": 88},
    "hard_gate_results": {"passed": True, "critical_group_coverage": 1.0},
    "render_recommendation": "render",
    "strengths": ["证据完整"],
    "weaknesses": [],
}

_DECISION = {
    "decision_version": "2.0",
    "category_profile_id": "fashion_accessories_v2",
    "recommended_candidate_id": "C001",
    "should_render": True,
    "confidence": 85,
    "reason": "品类证据完整且生成风险可控",
    "decision_evidence": ["critical proof coverage=1.0"],
    "blocking_gates": [],
    "expected_failure_modes": ["手部畸形"],
    "pre_render_checklist": ["确认产品颜色"],
    "renderer_plan": {
        "adapter_requirements": ["锁定产品结构"],
        "optional_keyframes": [],
        "retry_budget": 1,
        "replace_candidate_on": ["产品变款"],
    },
    "if_first_render_fails": {
        "likely_causes": ["手部"],
        "recommended_fix": "简化手部",
        "do_not_retry_if": ["颜色错"],
    },
}


class TestBuildFinalSpecPackage(unittest.TestCase):
    @patch("core.output_package.chat", return_value="# Brand Film Spec - 错金浪纹对戒\n\n规格书成品")
    def test_package_has_v2_renderer_contract(self, _mock):
        package = build_final_spec_package(
            _BRIEF, _CANDIDATE, _SCORE, None, _DECISION
        )
        self.assertEqual(package["package_version"], "2.0")
        self.assertIn("Brand Film Spec", package["brand_film_spec"])
        self.assertEqual(package["category_profile"]["profile_id"], "fashion_accessories_v2")
        self.assertEqual(
            package["product_fidelity_lock"]["must_keep"],
            ["银白、暖金与蓝色"],
        )
        self.assertEqual(package["renderer_handoff"]["port_id"], "pluggable_video_renderer")
        self.assertIn("claim boundaries", package["renderer_handoff"]["adapter_must_not_rewrite"])
        self.assertIn("天然宝石", package["claim_boundaries"]["forbidden"])

    @patch("core.output_package.chat", return_value="成品")
    def test_report_answers_required_questions(self, _mock):
        package = build_final_spec_package(
            _BRIEF, _CANDIDATE, _SCORE, None, _DECISION
        )
        report = build_report_md(
            package,
            all_candidates_count=6,
            rejected=[{
                "candidate_id": "C002",
                "render_recommendation": "reject",
                "scores": {"overall": 40},
            }],
            shortlisted=[{
                "candidate_id": "C001",
                "overall": 88,
                "eligible_for_render": True,
                "ineligible_reasons": [],
            }],
        )
        self.assertIn("服饰配件", report)
        self.assertIn("C001", report)
        self.assertIn("C002", report)
        self.assertIn("确认产品颜色", report)
        self.assertIn("简化手部", report)
        self.assertIn("category_gates_passed: True", report)
        self.assertIn("天然宝石", report)
        self.assertIn(".brand-film-spec.md", report)


if __name__ == "__main__":
    unittest.main()
