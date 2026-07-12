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


def _cand(cid: str) -> dict[str, Any]:
    return {"candidate_id": cid, "creative_route": "route", "shot_plan": []}


def _score(cid: str, overall: int, feasibility: int = 88, clarity: int = 88, rec: str = "shortlist") -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "scores": {
            "first_3_seconds_hook": overall,
            "product_clarity": clarity,
            "brand_fit": overall,
            "audience_relevance": overall,
            "visual_memorability": overall,
            "platform_fit": overall,
            "seedance_feasibility": feasibility,
            "generation_risk_control": overall,
            "commercial_intent": overall,
            "overall": overall,
        },
        "strengths": [],
        "weaknesses": [],
        "revision_suggestions": [],
        "render_recommendation": rec,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()

    repo = Path(args.submission).resolve()
    sys.path.insert(0, str(repo))

    from core.shortlist import select_shortlist

    candidates = [_cand("C101"), _cand("C102"), _cand("C103"), _cand("C104"), _cand("C105")]
    scores = [
        _score("C101", 98, clarity=62, rec="render"),
        _score("C102", 96, feasibility=54, rec="render"),
        _score("C103", 90, feasibility=86, clarity=88, rec="render"),
        _score("C104", 86, feasibility=84, clarity=86, rec="shortlist"),
        _score("C105", 79, feasibility=90, clarity=90, rec="render"),
    ]

    top_two = select_shortlist(candidates, scores, top_k=2, min_overall=80, min_feasibility=75)
    full = select_shortlist(candidates, scores, top_k=4, min_overall=80, min_feasibility=75)
    ids_top_two = [row["candidate_id"] for row in top_two]
    ids_full = [row["candidate_id"] for row in full]
    by_id = {row["candidate_id"]: row for row in full}

    checks = [
        _detail("top_k_prefers_eligible_candidates", ids_top_two == ["C103", "C104"], str(ids_top_two)),
        _detail("below_min_overall_filtered", "C105" not in ids_full, str(ids_full)),
        _detail("ineligible_candidates_still_annotated", not by_id["C101"]["eligible_for_render"] and not by_id["C102"]["eligible_for_render"], json.dumps(by_id, ensure_ascii=False)),
        _detail("product_clarity_reason_present", any("product_clarity" in item for item in by_id["C101"]["ineligible_reasons"]), str(by_id["C101"]["ineligible_reasons"])),
        _detail("feasibility_reason_present", any("seedance_feasibility" in item for item in by_id["C102"]["ineligible_reasons"]), str(by_id["C102"]["ineligible_reasons"])),
        _detail("eligible_rows_have_empty_reasons", by_id["C103"]["ineligible_reasons"] == [] and by_id["C104"]["ineligible_reasons"] == [], json.dumps(by_id, ensure_ascii=False)),
    ]
    passed = sum(1 for item in checks if item["status"] == "passed")
    total = len(checks)
    _emit({
        "valid": passed == total,
        "score": round(100 * passed / total, 2),
        "pass_rate": passed / total,
        "summary": f"{passed}/{total} shortlist checks passed",
        "details": checks,
        "metrics": {"top_two": ids_top_two, "full_order": ids_full},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
