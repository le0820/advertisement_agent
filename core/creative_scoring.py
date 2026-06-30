"""创意候选 → 结构化评分 (LLM + 代码加权 overall)。

评分维度 9 项由 LLM 给出 (0-100)，overall 由代码按固定权重加权平均，
render_recommendation 由 LLM 给出。避免 LLM 主观推荐代替结构化打分。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import parse_json_object
from .llm_client import chat_text, ARK_SCORE_DEFAULT_MODEL

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "score_creative_candidate.txt"
)

SCORE_WEIGHTS: dict[str, float] = {
    "first_3_seconds_hook": 0.15,
    "product_clarity": 0.15,
    "brand_fit": 0.10,
    "audience_relevance": 0.10,
    "visual_memorability": 0.15,
    "platform_fit": 0.10,
    "seedance_feasibility": 0.15,
    "generation_risk_control": 0.05,
    "commercial_intent": 0.05,
}

_SCORE_DIMS = tuple(SCORE_WEIGHTS.keys())


def compute_overall(scores: dict[str, Any]) -> int:
    """按 SCORE_WEIGHTS 加权平均, 结果四舍五入为整数 (0-100)。"""
    total = 0.0
    for dim, weight in SCORE_WEIGHTS.items():
        try:
            total += float(scores.get(dim, 0)) * weight
        except (TypeError, ValueError):
            total += 0.0
    return round(total)


def _normalize_score(raw: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    raw_scores = raw.get("scores") or {}
    if not isinstance(raw_scores, dict):
        raw_scores = {}
    # Fallback: if scores dict is empty, try top-level fields (LLM may flatten)
    if not raw_scores:
        for dim in _SCORE_DIMS:
            val = raw.get(dim)
            if val is not None and not isinstance(val, (list, dict)):
                raw_scores[dim] = val
    scores: dict[str, Any] = {}
    for dim in _SCORE_DIMS:
        try:
            val = int(raw_scores.get(dim, 0))
        except (TypeError, ValueError):
            val = 0
        scores[dim] = max(0, min(100, val))
    scores["overall"] = compute_overall(scores)

    rec = raw.get("render_recommendation", "revise")
    if rec not in ("reject", "revise", "shortlist", "render"):
        rec = "revise"

    def _str_list(key: str) -> list[str]:
        v = raw.get(key, [])
        return [str(x) for x in v] if isinstance(v, list) else []

    return {
        "candidate_id": candidate_id,
        "scores": scores,
        "strengths": _str_list("strengths"),
        "weaknesses": _str_list("weaknesses"),
        "revision_suggestions": _str_list("revision_suggestions"),
        "render_recommendation": rec,
    }


def score_creative_candidate(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    model: str | None = None,
    api_key: str | None = None,
    *,
    score_model: str | None = None,
    score_api_key: str | None = None,
) -> dict[str, Any]:
    """对单个候选打分 (默认使用 ARK doubao-seed-2-1-turbo-260628)。

    Args:
        brief: creative_brief。
        candidate: creative_candidate。
        model: 预留参数 (未使用)。
        api_key: 预留参数 (未使用)。
        score_model: ARK 裁判模型名覆盖；不传则默认 doubao-seed-2-1-turbo-260628。
        score_api_key: ARK API key 覆盖 (默认读 ARK_API_KEY)。

    Returns:
        creative_score dict (见 schemas/creative_score.schema.json)。
    """
    candidate_id = candidate.get("candidate_id", "")
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        candidate_json=json.dumps(candidate, ensure_ascii=False, indent=2),
        platform=brief.get("platform", "douyin"),
    )
    text = chat_text(
        prompt,
        model=score_model or ARK_SCORE_DEFAULT_MODEL,
        api_key=score_api_key,
    )
    raw = parse_json_object(text)
    return _normalize_score(raw, candidate_id)


def score_creative_candidates(
    brief: dict[str, Any],
    candidates: list[dict[str, Any]],
    model: str | None = None,
    api_key: str | None = None,
    *,
    score_model: str | None = None,
    score_api_key: str | None = None,
) -> list[dict[str, Any]]:
    """对多个候选依次打分。"""
    return [
        score_creative_candidate(
            brief, c, model=model, api_key=api_key,
            score_model=score_model, score_api_key=score_api_key,
        )
        for c in candidates
    ]
