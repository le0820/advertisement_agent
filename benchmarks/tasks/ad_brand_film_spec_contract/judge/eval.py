from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

START_MARKER = ">>>>> Start Structured Result"
END_MARKER = ">>>>> End Structured Result"


def _emit(result: dict[str, Any]) -> None:
    print(START_MARKER)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(END_MARKER)


def _detail(name: str, ok: bool, message: str = "") -> dict[str, Any]:
    return {"name": name, "status": "passed" if ok else "failed", "message": message, "score": 1.0 if ok else 0.0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()

    repo = Path(args.submission).resolve()
    sys.path.insert(0, str(repo))

    prompt_path = repo / "prompts" / "build_brand_film_spec.txt"
    prompt = prompt_path.read_text(encoding="utf-8")
    required_placeholders = [
        "{brief_json}",
        "{candidate_json}",
        "{score_json}",
        "{decision_json}",
        "{storyboard_block}",
        "{dense_caption}",
        "{sensitive_constraints}",
        "{must_show_second}",
        "{product_name}",
    ]
    required_sections = ["## 结论", "## 背景与判断", "## 电影化路线", "## 15秒节奏", "## 制作控制", "## 原创性与风险", "## Seedance 生成注意"]

    from core.output_package import build_final_spec_package, build_report_md

    brief = {
        "product_name": "Moonlit Silver Ring",
        "category": "珠宝饰品",
        "dense_caption": "Wide silver ring with wave engraving and a blue stone.",
        "platform": "douyin",
        "aspect_ratio": "9:16",
        "duration_seconds": 15,
        "constraints": {"must_show_product_by_second": 3, "avoid_face_generation": True},
    }
    candidate = {"candidate_id": "C201", "creative_route": "品牌大片", "one_sentence_idea": "Moonlight becomes a ring."}
    score = {"candidate_id": "C201", "scores": {"overall": 91}, "render_recommendation": "render"}
    decision = {
        "recommended_candidate_id": "C201",
        "should_render": True,
        "confidence": 87,
        "reason": "Strong product truth and feasible visual route.",
        "expected_failure_modes": ["blue stone color drift"],
        "pre_render_checklist": ["Confirm wave engraving is visible"],
        "if_first_render_fails": {"likely_causes": ["macro blur"], "recommended_fix": "simplify camera motion", "do_not_retry_if": ["product color changes"]},
    }
    fake_spec = "# Brand Film Spec - Moonlit Silver Ring\n\n## 结论\n## 背景与判断\n## 电影化路线\n## 15秒节奏\n## 制作控制\n## 原创性与风险\n## Seedance 生成注意\n"
    with patch("core.output_package.chat", return_value=fake_spec):
        package = build_final_spec_package(brief, candidate, score, None, decision)
        report = build_report_md(package, all_candidates_count=4, rejected=[], shortlisted=[{"candidate_id": "C201", "overall": 91, "eligible_for_render": True, "ineligible_reasons": []}])

    checks = [
        _detail("prompt_title_contract", "# Brand Film Spec - {product_name}" in prompt),
        _detail("prompt_has_all_context_placeholders", all(item in prompt for item in required_placeholders), json.dumps([p for p in required_placeholders if p not in prompt], ensure_ascii=False)),
        _detail("prompt_has_required_sections", all(section in prompt for section in required_sections), json.dumps([s for s in required_sections if s not in prompt], ensure_ascii=False)),
        _detail("prompt_mentions_downstream_agent", "小云雀" in prompt and "Seedance" in prompt),
        _detail("prompt_enforces_product_truth", "dense_caption" in prompt and "不得改颜色" in prompt),
        _detail("package_uses_brand_film_spec_key", package.get("brand_film_spec", "").startswith("# Brand Film Spec")),
        _detail("package_preserves_selected_candidate", package.get("selected_candidate", {}).get("candidate_id") == "C201"),
        _detail("report_points_to_brand_film_spec_file", ".brand-film-spec.md" in report),
        _detail("manual_upload_notes_include_checklist", any("wave engraving" in item or "Confirm" in item for item in package.get("manual_upload_notes", [])), str(package.get("manual_upload_notes", []))),
    ]
    passed = sum(1 for item in checks if item["status"] == "passed")
    total = len(checks)
    _emit({
        "valid": passed == total,
        "score": round(100 * passed / total, 2),
        "pass_rate": passed / total,
        "summary": f"{passed}/{total} brand-film-spec contract checks passed",
        "details": checks,
        "metrics": {"prompt_path": str(prompt_path)},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
