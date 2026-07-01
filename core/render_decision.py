"""shortlist → render_decision (规则选 + LLM 推理)。

规则层: 从 eligible_for_render 候选中选 overall 最高者;
若没有 eligible 候选, should_render=false 且 recommended_candidate_id=null。
LLM 层: 生成 reason / 失败模式 / 上传前检查项 / 首轮失败修正建议。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import chat_json_object

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "make_render_decision.txt"
)


def pick_top_eligible(shortlisted: list[dict[str, Any]]) -> str | None:
    """从 shortlist 中选 overall 最高的 eligible 候选; 无则 None。"""
    eligible = [r for r in shortlisted if r.get("eligible_for_render")]
    if not eligible:
        return None
    eligible.sort(key=lambda r: int(r.get("overall", 0)), reverse=True)
    return eligible[0].get("candidate_id")


def _storyboard_block(simulations: list[dict[str, Any]]) -> str:
    if not simulations:
        return "（未启用关键帧预演）"
    return json.dumps(simulations, ensure_ascii=False, indent=2)


def _clamp_int(v: Any, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def _normalize(raw: dict[str, Any], fallback_id: str | None,
               force_skip: bool) -> dict[str, Any]:
    fail = raw.get("if_first_render_fails") or {}
    if not isinstance(fail, dict):
        fail = {}

    def _str_list(key):
        v = raw.get(key, [])
        return [str(x) for x in v] if isinstance(v, list) else []

    def _fail_list(key):
        v = fail.get(key, [])
        return [str(x) for x in v] if isinstance(v, list) else []

    should_render = bool(raw.get("should_render", False)) and not force_skip
    recommended = None if force_skip else (raw.get("recommended_candidate_id") or fallback_id)

    return {
        "recommended_candidate_id": recommended,
        "should_render": should_render,
        "confidence": _clamp_int(raw.get("confidence", 0), 0, 100),
        "reason": str(raw.get("reason", "")),
        "expected_failure_modes": _str_list("expected_failure_modes"),
        "pre_render_checklist": _str_list("pre_render_checklist"),
        "if_first_render_fails": {
            "likely_causes": _fail_list("likely_causes"),
            "recommended_fix": str(fail.get("recommended_fix", "")),
            "do_not_retry_if": _fail_list("do_not_retry_if"),
        },
    }


def make_render_decision(
    brief: dict[str, Any],
    shortlisted: list[dict[str, Any]],
    storyboard_simulations: list[dict[str, Any]] | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """决定哪一版值得消耗一次视频积分。

    Args:
        brief: creative_brief。
        shortlisted: select_shortlist() 的返回值。
        storyboard_simulations: 关键帧预演结果 (可选, 可为空列表)。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        render_decision dict (见 schemas/render_decision.schema.json)。
    """
    sims = storyboard_simulations or []
    fallback_id = pick_top_eligible(shortlisted)

    # 没有可生成候选时直接 fast-fail, 不调用 LLM (省一次 API 调用)
    if fallback_id is None:
        eligible_total = len([r for r in shortlisted if r.get("eligible_for_render")])
        return {
            "recommended_candidate_id": None,
            "should_render": False,
            "confidence": 0,
            "reason": (
                f"没有候选通过 render eligibility 门槛 (eligible {eligible_total}/"
                f"{len(shortlisted)}), 不值得消耗视频积分。"
            ),
            "expected_failure_modes": [],
            "pre_render_checklist": [],
            "if_first_render_fails": {
                "likely_causes": [],
                "recommended_fix": "",
                "do_not_retry_if": [],
            },
        }

    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        shortlist_json=json.dumps(shortlisted, ensure_ascii=False, indent=2),
        storyboard_block=_storyboard_block(sims),
    )
    raw = chat_json_object(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )
    return _normalize(raw, fallback_id, force_skip=False)
