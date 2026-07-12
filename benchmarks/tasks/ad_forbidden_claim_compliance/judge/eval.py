from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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

    from core.brief import build_creative_brief

    features = {
        "product_name": "Sensitive supplement",
        "category": "美妆",
        "dense_caption": "Small bottle with white label and gold cap.",
        "selling_points": ["portable", "clean texture"],
        "target_audience": "urban commuters",
    }
    brief = build_creative_brief(
        features,
        {
            "forbidden_claim": ["No.1", "lowest price", "guaranteed cure"],
            "selling_point": ["gift-ready packaging"],
            "cta": "Learn more",
        },
    )
    candidate_prompt = (repo / "prompts" / "generate_creative_candidates.txt").read_text(encoding="utf-8")
    spec_prompt = (repo / "prompts" / "build_brand_film_spec.txt").read_text(encoding="utf-8")

    forbidden = brief.get("brand_assets", {}).get("forbidden_claims", [])
    checks = [
        _detail("brief_preserves_all_forbidden_claims", forbidden == ["No.1", "lowest price", "guaranteed cure"], str(forbidden)),
        _detail("brief_keeps_user_selling_point", "gift-ready packaging" in brief.get("selling_points", []), str(brief.get("selling_points"))),
        _detail("brief_marks_sensitive_category", brief.get("constraints", {}).get("avoid_face_generation") is True, json.dumps(brief.get("constraints"), ensure_ascii=False)),
        _detail("candidate_prompt_explicitly_forbids_claims", "forbidden_claims" in candidate_prompt and "不得出现禁用 claim" in candidate_prompt),
        _detail("final_spec_receives_full_brief", "{brief_json}" in spec_prompt),
        _detail("final_spec_forbids_fake_claim_like_data", "不可证实的市场数据" in spec_prompt and "虚假的品牌历史" in spec_prompt),
        _detail("cta_sets_must_have_cta", brief.get("constraints", {}).get("must_have_cta") is True, json.dumps(brief.get("constraints"), ensure_ascii=False)),
    ]
    passed = sum(1 for item in checks if item["status"] == "passed")
    total = len(checks)
    _emit({
        "valid": passed == total,
        "score": round(100 * passed / total, 2),
        "pass_rate": passed / total,
        "summary": f"{passed}/{total} forbidden-claim compliance checks passed",
        "details": checks,
        "metrics": {"forbidden_claims": forbidden},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
