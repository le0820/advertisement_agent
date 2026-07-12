"""creative_brief → 多个差异化创意候选 (LLM, JSON 数组)。

生成 num_candidates 个不同 creative_route 的结构化候选，供 scoring 评分。
候选不是最终 prompt；代码负责分配 candidate_id 并补齐缺失字段。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import chat_json_array

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "generate_creative_candidates.txt"
)
_REFERENCE_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "harness" / "reference_video_manifest.json"
)

_REQUIRED_FIELDS = (
    "creative_route", "one_sentence_idea", "hook", "target_emotion",
    "audience_insight", "product_truth", "visual_metaphor", "narrative_spine",
    "shot_plan",
)


def _normalize_candidate(
    raw: dict[str, Any],
    index: int,
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """补齐缺失字段并分配 candidate_id (C001, C002, ...)。"""
    brief = brief or {}
    cand: dict[str, Any] = {
        "schema_version": "2.0",
        "candidate_id": f"C{index:03d}",
    }
    for f in _REQUIRED_FIELDS:
        if f == "shot_plan":
            cand[f] = raw.get(f, [])
        else:
            cand[f] = raw.get(f, "")
    if not isinstance(cand["shot_plan"], list):
        cand["shot_plan"] = []
    for shot in cand["shot_plan"]:
        if isinstance(shot, dict) and not isinstance(shot.get("proof_tags"), list):
            shot["proof_tags"] = []

    profile = brief.get("category_profile") if isinstance(brief.get("category_profile"), dict) else {}
    strategy = raw.get("category_strategy") if isinstance(raw.get("category_strategy"), dict) else {}
    product_lock = strategy.get("product_fidelity_lock")
    if not isinstance(product_lock, dict):
        product_lock = {}
    cand["category_strategy"] = {
        "profile_id": str(strategy.get("profile_id") or profile.get("profile_id") or ""),
        "subcategory_id": str(strategy.get("subcategory_id") or profile.get("subcategory_id") or ""),
        "consumer_tension": str(strategy.get("consumer_tension") or ""),
        "product_first_seen_at": strategy.get("product_first_seen_at", 99),
        "proof_sequence": strategy.get("proof_sequence", [])
        if isinstance(strategy.get("proof_sequence"), list) else [],
        "required_proofs_covered": strategy.get("required_proofs_covered", [])
        if isinstance(strategy.get("required_proofs_covered"), list) else [],
        "claims_used": strategy.get("claims_used", [])
        if isinstance(strategy.get("claims_used"), list) else [],
        "product_fidelity_lock": {
            "must_keep": product_lock.get("must_keep", [])
            if isinstance(product_lock.get("must_keep"), list) else [],
            "must_not_add": product_lock.get("must_not_add", [])
            if isinstance(product_lock.get("must_not_add"), list) else [],
            "cross_shot_continuity": product_lock.get("cross_shot_continuity", [])
            if isinstance(product_lock.get("cross_shot_continuity"), list) else [],
        },
        "reference_pattern_ids": strategy.get("reference_pattern_ids", [])
        if isinstance(strategy.get("reference_pattern_ids"), list) else [],
    }

    risk = raw.get("renderer_risk") or raw.get("seedance_prompt_risk") or {}
    if not isinstance(risk, dict):
        risk = {}
    reasons = risk.get("risk_reasons", [])
    if not isinstance(reasons, list):
        reasons = []
    level = risk.get("risk_level", "medium")
    if level not in ("low", "medium", "high"):
        level = "medium"
    renderer_risk = {
        "risk_level": level,
        "risk_reasons": reasons,
        "fallback": str(risk.get("fallback", "")),
    }
    cand["renderer_risk"] = renderer_risk
    if "seedance_prompt_risk" in raw:
        cand["seedance_prompt_risk"] = {
            "risk_level": level,
            "risk_reasons": reasons,
        }
    return cand


def _template_block(template: dict[str, Any] | None) -> str:
    if not template:
        return "（无）"
    lines = [
        f"模版: {template.get('template_name', '')} ({template.get('template_id', '')})",
        f"调性: {template.get('system', '')}",
    ]
    for key, label in (
        ("best_for", "适用场景"),
        ("required_visual_proofs", "必备视觉证明"),
        ("allowed_person_policy", "允许人物策略"),
        ("disallowed", "禁止路线"),
    ):
        val = template.get(key)
        if isinstance(val, list) and val:
            lines.append(f"{label}: {'、'.join(str(x) for x in val)}")
    return "\n".join(lines)


def _reference_patterns_block(brief: dict[str, Any]) -> str:
    profile = brief.get("category_profile") if isinstance(brief.get("category_profile"), dict) else {}
    pattern_ids = profile.get("reference_pattern_ids", [])
    if not isinstance(pattern_ids, list) or not pattern_ids:
        return "（无）"
    with open(_REFERENCE_MANIFEST_PATH, "r", encoding="utf-8") as handle:
        patterns = json.load(handle).get("patterns", {})
    lines = []
    for pattern_id in pattern_ids:
        row = patterns.get(pattern_id, {})
        if row:
            lines.append(
                f"{pattern_id} {row.get('name', '')}: {row.get('description', '')}"
            )
    return "\n".join(lines) if lines else "（无）"


def validate_candidate_diversity(
    candidates: list[dict[str, Any]],
    expected_count: int | None = None,
) -> dict[str, Any]:
    """校验候选多样性, 防止 LLM 输出"换皮"的同质化创意 (GPT P3)。

    检查:
      - creative_route / hook / visual_metaphor 重复
      - shot_plan 为空
      - 实际数量与 expected_count 不符

    非致命: 返回 report, 由调用方决定如何处理。
    """
    warnings: list[str] = []
    duplicate_routes: list[str] = []
    empty_shot_plans: list[str] = []

    seen_routes: dict[str, str] = {}
    seen_hooks: dict[str, str] = {}
    seen_metaphors: dict[str, str] = {}

    for c in candidates:
        cid = c.get("candidate_id", "?")
        route = str(c.get("creative_route", "")).strip()
        hook = str(c.get("hook", "")).strip()
        metaphor = str(c.get("visual_metaphor", "")).strip()

        if route and route in seen_routes:
            warnings.append(
                f"{cid}: creative_route='{route}' 与 {seen_routes[route]} 重复"
            )
            duplicate_routes.append(cid)
        elif route:
            seen_routes[route] = cid

        if hook and hook in seen_hooks:
            warnings.append(f"{cid}: hook 与 {seen_hooks[hook]} 重复")
        elif hook:
            seen_hooks[hook] = cid

        if metaphor and metaphor in seen_metaphors:
            warnings.append(f"{cid}: visual_metaphor 与 {seen_metaphors[metaphor]} 重复")
        elif metaphor:
            seen_metaphors[metaphor] = cid

        if not c.get("shot_plan"):
            empty_shot_plans.append(cid)
            warnings.append(f"{cid}: shot_plan 为空")

    if expected_count is not None and len(candidates) != expected_count:
        warnings.append(
            f"候选数量 {len(candidates)} 与期望 {expected_count} 不符"
        )

    return {
        "warnings": warnings,
        "duplicate_routes": duplicate_routes,
        "empty_shot_plans": empty_shot_plans,
    }


def generate_creative_candidates(
    brief: dict[str, Any],
    template: dict[str, Any] | None = None,
    *,
    num_candidates: int = 8,
    model: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """生成 num_candidates 个差异化创意候选。

    Args:
        brief: build_creative_brief() 返回的 brief。
        template: match_template() 返回的模版 (可选, 作风格参考)。
        num_candidates: 候选数量, 默认 8。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        creative_candidate dict 列表 (见 schemas/creative_candidate.schema.json)。
        每个候选附加 diversity_report 字段。
    """
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        num_candidates=num_candidates,
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        category_profile_json=json.dumps(
            brief.get("category_profile", {}), ensure_ascii=False, indent=2
        ),
        template_block=_template_block(template),
        reference_patterns_block=_reference_patterns_block(brief),
    )
    raw_list = chat_json_array(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )
    candidates = []
    for i, raw in enumerate(raw_list, 1):
        if not isinstance(raw, dict):
            continue
        candidates.append(_normalize_candidate(raw, i, brief))

    # 多样性校验 (非致命, 附加到每个候选)
    report = validate_candidate_diversity(candidates, expected_count=num_candidates)
    for c in candidates:
        c["diversity_report"] = report
    return candidates
