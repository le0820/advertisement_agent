"""Category-aware creative scoring with deterministic overall and gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .category_profiles import (
    DEFAULT_SCORE_WEIGHTS,
    SCORE_DIMENSIONS,
    evaluate_candidate_gates,
    score_weights_for,
)
from .json_utils import parse_json_object
from .llm_client import ARK_SCORE_DEFAULT_MODEL, chat_text


_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "score_creative_candidate.txt"
)

# Public compatibility name. Runtime scoring uses the selected category profile.
SCORE_WEIGHTS: dict[str, float] = dict(DEFAULT_SCORE_WEIGHTS)
_SCORE_DIMS = SCORE_DIMENSIONS

_LEGACY_SCORE_ALIASES: dict[str, tuple[str, ...]] = {
    "hook_strength": ("first_3_seconds_hook",),
    "product_truth_fidelity": ("product_clarity",),
    "category_proof_coverage": ("product_clarity",),
    "consumer_relevance": ("audience_relevance",),
    "brand_fit": (),
    "visual_memorability": (),
    "narrative_coherence": ("brand_fit",),
    "platform_fit": (),
    "renderer_feasibility": ("seedance_feasibility",),
    "risk_control": ("generation_risk_control",),
    "commercial_intent": (),
}


def compute_overall(
    scores: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> int:
    selected_weights = weights or SCORE_WEIGHTS
    total = 0.0
    for dimension in _SCORE_DIMS:
        try:
            total += float(scores.get(dimension, 0)) * float(selected_weights.get(dimension, 0))
        except (TypeError, ValueError):
            continue
    return round(total)


def _coerce_dimension(raw_scores: dict[str, Any], dimension: str) -> int:
    value = raw_scores.get(dimension)
    if value is None:
        for alias in _LEGACY_SCORE_ALIASES.get(dimension, ()):
            if raw_scores.get(alias) is not None:
                value = raw_scores[alias]
                break
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _str_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _downgrade(current: str, target: str) -> str:
    order = {"reject": 0, "revise": 1, "shortlist": 2, "render": 3}
    return target if order.get(current, 1) > order[target] else current


def _normalize_score(
    raw: dict[str, Any],
    candidate_id: str,
    *,
    weights: dict[str, float],
    profile_id: str,
    gate_results: dict[str, Any],
) -> dict[str, Any]:
    raw_scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    if not raw_scores:
        raw_scores = {
            key: raw.get(key)
            for key in set(_SCORE_DIMS).union(
                alias for aliases in _LEGACY_SCORE_ALIASES.values() for alias in aliases
            )
            if raw.get(key) is not None
        }
    scores = {
        dimension: _coerce_dimension(raw_scores, dimension)
        for dimension in _SCORE_DIMS
    }
    recommendation = str(raw.get("render_recommendation", "revise"))
    if recommendation not in ("reject", "revise", "shortlist", "render"):
        recommendation = "revise"

    result = {
        "score_version": "2.0",
        "candidate_id": candidate_id,
        "profile_id": profile_id,
        "weights": dict(weights),
        "scores": scores,
        "hard_gate_results": gate_results,
        "strengths": _str_list(raw, "strengths"),
        "weaknesses": _str_list(raw, "weaknesses"),
        "revision_suggestions": _str_list(raw, "revision_suggestions"),
        "render_recommendation": recommendation,
    }
    return result


def _apply_deterministic_gates(
    brief: dict[str, Any],
    score: dict[str, Any],
) -> dict[str, Any]:
    gate = score["hard_gate_results"]
    scores = score["scores"]
    if not gate.get("skipped") and not gate.get("passed"):
        if gate.get("product_first_seen_at") is None or (
            gate.get("product_first_seen_at", 99) > gate.get("product_deadline", 3)
        ):
            scores["hook_strength"] = min(scores["hook_strength"], 65)
            scores["product_truth_fidelity"] = min(scores["product_truth_fidelity"], 70)
            _append_once(score["weaknesses"], "产品未在品类约定的前 3 秒内清晰出现")
            _append_once(score["revision_suggestions"], "把可识别商品前移到 0-2 秒钩子")

        coverage = float(gate.get("critical_group_coverage", 0))
        minimum = float(gate.get("minimum_critical_group_coverage", 1))
        if coverage < minimum:
            scores["category_proof_coverage"] = min(
                scores["category_proof_coverage"], round(coverage * 100)
            )
            missing = [
                row.get("id", "")
                for row in gate.get("critical_groups", [])
                if not row.get("passed")
            ]
            _append_once(
                score["weaknesses"],
                "缺少品类关键证据: " + "、".join(item for item in missing if item),
            )
            _append_once(score["revision_suggestions"], "补齐缺失证据镜头后再进入 render")

        if gate.get("unsafe_claims"):
            scores["risk_control"] = min(scores["risk_control"], 40)
            _append_once(score["weaknesses"], "包含无依据的高风险 claim")
            _append_once(score["revision_suggestions"], "删除 claim 或补充用户可核验依据")

        score["render_recommendation"] = _downgrade(
            score.get("render_recommendation", "revise"), "revise"
        )

    floors = (
        brief.get("category_profile", {}).get("hard_score_floors", {})
        if isinstance(brief.get("category_profile"), dict)
        else {}
    )
    below = [
        f"{dimension}={scores.get(dimension, 0)}<{floor}"
        for dimension, floor in floors.items()
        if scores.get(dimension, 0) < int(floor)
    ]
    if below:
        score["render_recommendation"] = _downgrade(
            score.get("render_recommendation", "revise"), "revise"
        )
        _append_once(score["weaknesses"], "未通过品类评分底线: " + "; ".join(below))

    scores["overall"] = compute_overall(scores, score["weights"])
    return score


def score_creative_candidate(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    model: str | None = None,
    api_key: str | None = None,
    *,
    score_model: str | None = None,
    score_api_key: str | None = None,
) -> dict[str, Any]:
    """Ask the legacy score client for judgment, then apply v2 profile rules."""
    del model, api_key
    candidate_id = str(candidate.get("candidate_id", ""))
    gate_results = evaluate_candidate_gates(brief, candidate)
    weights = score_weights_for(brief)
    profile_id = str(
        brief.get("category_profile", {}).get("profile_id", "")
        if isinstance(brief.get("category_profile"), dict)
        else ""
    )
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        candidate_json=json.dumps(candidate, ensure_ascii=False, indent=2),
        category_profile_json=json.dumps(
            brief.get("category_profile", {}), ensure_ascii=False, indent=2
        ),
        gate_results_json=json.dumps(gate_results, ensure_ascii=False, indent=2),
        platform=brief.get("platform", "douyin"),
    )
    text = chat_text(
        prompt,
        model=score_model or ARK_SCORE_DEFAULT_MODEL,
        api_key=score_api_key,
    )
    raw = parse_json_object(text)
    score = _normalize_score(
        raw,
        candidate_id,
        weights=weights,
        profile_id=profile_id,
        gate_results=gate_results,
    )
    return _apply_deterministic_gates(brief, score)


def score_creative_candidates(
    brief: dict[str, Any],
    candidates: list[dict[str, Any]],
    model: str | None = None,
    api_key: str | None = None,
    *,
    score_model: str | None = None,
    score_api_key: str | None = None,
) -> list[dict[str, Any]]:
    return [
        score_creative_candidate(
            brief,
            candidate,
            model=model,
            api_key=api_key,
            score_model=score_model,
            score_api_key=score_api_key,
        )
        for candidate in candidates
    ]
