"""为 shortlist 候选生成关键帧 prompt (最小实现, P2 增强)。

不调用图片模型，只输出可复制给图片生成模型的关键帧 prompt。
默认在 decision 模式下不调用 (低成本), 仅 --storyboard 时启用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import chat_json_object

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "generate_storyboard_simulator.txt"
)


def _normalize(
    raw: dict[str, Any],
    candidate_id: str,
    profile_id: str = "",
) -> dict[str, Any]:
    keyframes = raw.get("keyframes") or []
    if not isinstance(keyframes, list):
        keyframes = []
    for keyframe in keyframes:
        if isinstance(keyframe, dict) and not isinstance(keyframe.get("proof_tags"), list):
            keyframe["proof_tags"] = []
    review = raw.get("storyboard_review") or {}
    if not isinstance(review, dict):
        review = {}
    review.setdefault("visual_consistency_risk", "")
    review.setdefault("product_fidelity_risk", "")
    review.setdefault("category_proof_risk", "")
    review.setdefault("model_difficulty", "medium")
    review.setdefault("recommendation", "acceptable")
    return {
        "candidate_id": candidate_id,
        "profile_id": profile_id,
        "keyframes": keyframes,
        "storyboard_review": review,
    }


def generate_storyboard_simulation(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """为单个候选生成关键帧级 storyboard prompt。

    Args:
        brief: creative_brief。
        candidate: creative_candidate (通常来自 shortlist)。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        storyboard_simulation dict (见 schemas/storyboard_simulation.schema.json)。
    """
    candidate_id = candidate.get("candidate_id", "")
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        candidate_json=json.dumps(candidate, ensure_ascii=False, indent=2),
    )
    raw = chat_json_object(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )
    profile_id = str(
        brief.get("category_profile", {}).get("profile_id", "")
        if isinstance(brief.get("category_profile"), dict) else ""
    )
    return _normalize(raw, candidate_id, profile_id)
