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
    return {
        "name": name,
        "status": "passed" if ok else "failed",
        "message": message,
        "score": 1.0 if ok else 0.0,
    }


def _fashion_brief() -> dict[str, Any]:
    return {
        "product_name": "atelier evening suit",
        "category": "服装鞋包",
        "sub_category": "高定礼服",
        "platform": "douyin",
        "constraints": {
            "category_requirements": {
                "required_visual_proofs": ["worn display", "occasion", "silhouette"]
            },
            "person_policy": {
                "face_allowed": True,
                "human_body_allowed": True,
                "hands_allowed": True,
                "model_required": True,
                "allowed_body_framing": ["full body", "natural face", "runway silhouette"],
            },
        },
    }


BASE_SCORE_JSON = json.dumps(
    {
        "scores": {
            "first_3_seconds_hook": 92,
            "product_clarity": 92,
            "brand_fit": 92,
            "audience_relevance": 92,
            "visual_memorability": 92,
            "platform_fit": 92,
            "seedance_feasibility": 92,
            "generation_risk_control": 92,
            "commercial_intent": 92,
        },
        "strengths": ["strong visual hook"],
        "weaknesses": [],
        "revision_suggestions": [],
        "render_recommendation": "render",
    },
    ensure_ascii=False,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()

    repo = Path(args.submission).resolve()
    sys.path.insert(0, str(repo))

    from core.creative_scoring import score_creative_candidate

    checks: list[dict[str, Any]] = []
    brief = _fashion_brief()
    with patch("core.creative_scoring.chat_text", return_value=BASE_SCORE_JSON):
        mannequin_only = score_creative_candidate(
            brief,
            {
                "candidate_id": "C101",
                "shot_plan": [
                    {
                        "visual": "A mannequin and dress form on a pedestal, macro fabric details only."
                    }
                ],
            },
        )
        checks.append(_detail(
            "mannequin_only_caps_product_clarity",
            mannequin_only["scores"]["product_clarity"] <= 65,
            f"product_clarity={mannequin_only['scores']['product_clarity']}",
        ))
        checks.append(_detail(
            "mannequin_only_caps_commercial_intent",
            mannequin_only["scores"]["commercial_intent"] <= 70,
            f"commercial_intent={mannequin_only['scores']['commercial_intent']}",
        ))
        checks.append(_detail(
            "mannequin_only_downgrades_render",
            mannequin_only["render_recommendation"] == "revise",
            f"recommendation={mannequin_only['render_recommendation']}",
        ))

        missing_silhouette = score_creative_candidate(
            brief,
            {
                "candidate_id": "C102",
                "shot_plan": [
                    {
                        "visual": "A model wearing the suit at a wedding gala entrance, camera stays on face and room atmosphere."
                    }
                ],
            },
        )
        checks.append(_detail(
            "missing_silhouette_caps_product_clarity",
            missing_silhouette["scores"]["product_clarity"] <= 70,
            f"product_clarity={missing_silhouette['scores']['product_clarity']}",
        ))
        checks.append(_detail(
            "missing_silhouette_downgrades_to_shortlist",
            missing_silhouette["render_recommendation"] == "shortlist",
            f"recommendation={missing_silhouette['render_recommendation']}",
        ))

        complete = score_creative_candidate(
            brief,
            {
                "candidate_id": "C103",
                "shot_plan": [
                    {
                        "visual": "A full-body model wearing the suit at a wedding gala, with shoulder line, waist, tailoring, silhouette, and drape clearly shown."
                    }
                ],
            },
        )
        checks.append(_detail(
            "complete_fashion_candidate_can_render",
            complete["render_recommendation"] == "render"
            and complete["scores"]["product_clarity"] == 92
            and complete["scores"]["commercial_intent"] == 92,
            json.dumps(complete["scores"], ensure_ascii=False),
        ))

    passed = sum(1 for item in checks if item["status"] == "passed")
    total = len(checks)
    _emit({
        "valid": passed == total,
        "score": round(100 * passed / total, 2),
        "pass_rate": passed / total,
        "summary": f"{passed}/{total} hard-gate checks passed",
        "details": checks,
        "metrics": {"checks": total},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
