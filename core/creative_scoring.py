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

_FASHION_CATEGORY = "服装鞋包"
_FASHION_SUB_CATEGORIES = {
    "高定礼服", "男士西装", "婚礼礼服", "晚宴礼服", "旗袍 / 中式礼服",
    "女装连衣裙", "鞋履", "箱包",
}
_MANNEQUIN_TERMS = ("人台", "半身人台", "人体模特", "mannequin", "dress form")
_HUMAN_WORN_TERMS = (
    "不露脸模特", "模特", "背影", "侧影", "脖子以下", "半身", "全身",
    "走秀", "秀场", "手拎", "肩背", "斜挎", "上身", "上脚", "脚上",
    "穿着效果", "穿搭", "行走", "动态姿态", "torso", "neck-down", "model",
    "runway", "on-foot", "on foot", "on-body", "worn", "wearing", "carry",
)
_LIVING_MODEL_TERMS = (
    "不露脸模特", "真人", "人物", "背影", "侧影", "脖子以下", "走秀", "秀场",
    "手拎", "肩背", "斜挎", "上脚", "脚上", "行走", "动态姿态", "model",
    "neck-down", "runway", "on-foot", "on foot", "on-body", "worn by",
    "person", "wearer",
)
_OCCASION_TERMS = (
    "婚礼", "晚宴", "商务", "红毯", "秀场", "通勤", "舞会", "宴会",
    "品牌活动", "发布会", "典礼", "派对", "办公室", "会议", "礼堂",
    "酒店", "会场", "仪式", "occasion", "wedding", "gala", "business",
    "runway", "commute", "event", "red carpet",
)
_SILHOUETTE_TERMS = (
    "版型", "廓形", "轮廓", "肩线", "腰线", "垂坠", "剪裁", "比例",
    "收腰", "下摆", "袖口", "完整服装", "完整轮廓", "全身", "完整造型",
    "silhouette", "fit", "tailoring", "drape", "shoulder", "waist",
    "full look", "full-body",
)


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


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    text_l = text.lower()
    return any(term.lower() in text_l for term in terms)


def _candidate_text(candidate: dict[str, Any]) -> str:
    return json.dumps(candidate, ensure_ascii=False, sort_keys=True)


def _is_fashion_brief(brief: dict[str, Any]) -> bool:
    constraints = brief.get("constraints") or {}
    return (
        brief.get("category") == _FASHION_CATEGORY
        or brief.get("sub_category") in _FASHION_SUB_CATEGORIES
        or bool(constraints.get("category_requirements"))
    )


def _has_worn_display(text: str) -> bool:
    if not _contains_any(text, _HUMAN_WORN_TERMS):
        return False
    if _contains_any(text, _MANNEQUIN_TERMS) and not _contains_any(text, _LIVING_MODEL_TERMS):
        return False
    return True


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _downgrade_render_recommendation(current: str, target: str) -> str:
    order = {"reject": 0, "revise": 1, "shortlist": 2, "render": 3}
    if order.get(current, 1) > order[target]:
        return target
    return current


def _apply_fashion_hard_gates(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    score: dict[str, Any],
) -> dict[str, Any]:
    if not _is_fashion_brief(brief):
        return score

    text = _candidate_text(candidate)
    has_worn = _has_worn_display(text)
    has_occasion = _contains_any(text, _OCCASION_TERMS)
    has_silhouette = _contains_any(text, _SILHOUETTE_TERMS)

    scores = score["scores"]
    if not has_worn:
        scores["product_clarity"] = min(scores.get("product_clarity", 0), 65)
        score["render_recommendation"] = _downgrade_render_recommendation(
            score.get("render_recommendation", "revise"), "revise"
        )
        _append_once(score["weaknesses"], "服装缺少真人模特上身/全身/上脚/手拎展示")
        _append_once(score["revision_suggestions"], "加入脖子以下或背影模特镜头，展示真实穿着效果")
    if not has_occasion:
        scores["commercial_intent"] = min(scores.get("commercial_intent", 0), 70)
        _append_once(score["weaknesses"], "缺少婚礼、晚宴、商务、秀场或通勤等使用场合")
        _append_once(score["revision_suggestions"], "补充一个目标人群会购买和使用的明确场合镜头")
    if not has_silhouette:
        scores["product_clarity"] = min(scores.get("product_clarity", 0), 70)
        score["render_recommendation"] = _downgrade_render_recommendation(
            score.get("render_recommendation", "revise"), "shortlist"
        )
        _append_once(score["weaknesses"], "缺少版型、廓形、肩线、腰线或完整轮廓展示")
        _append_once(score["revision_suggestions"], "补充完整轮廓或行走镜头，证明剪裁和垂坠")

    scores["overall"] = compute_overall(scores)
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
    score = _normalize_score(raw, candidate_id)
    return _apply_fashion_hard_gates(brief, candidate, score)


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
