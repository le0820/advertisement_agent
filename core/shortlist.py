"""评分 → shortlist (纯规则, P1 核心价值)。

让系统能拒绝低质量创意，而不是永远生成一个最终 prompt。
规则:
  1. 低于 min_overall 的候选不进入 shortlist。
  2. 计算 render eligibility (category gates / truth / proof / renderer / risk)。
  3. 排序: eligible_for_render 优先 → overall 高 → renderer_feasibility 高。
  4. 取 top_k 个。
这样可生成候选不会被高 overall 但不可生成的候选挤掉。
"""

from __future__ import annotations

from typing import Any

_DEFAULT_TRUTH_FLOOR = 70
_DEFAULT_PROOF_FLOOR = 70
_DEFAULT_RISK_FLOOR = 60


def _compute_eligibility(
    row: dict[str, Any],
    min_feasibility: int,
    brief: dict[str, Any] | None,
) -> None:
    """就地填充 eligible_for_render / ineligible_reasons。"""
    sc = row["score"].get("scores", {})
    reasons: list[str] = []
    try:
        feasibility = int(sc.get("renderer_feasibility", 0))
    except (TypeError, ValueError):
        feasibility = 0
    if feasibility < min_feasibility:
        reasons.append(
            f"renderer_feasibility={feasibility} 低于 {min_feasibility}, 生成失败风险高"
        )
    profile_floors = {}
    if isinstance(brief, dict) and isinstance(brief.get("category_profile"), dict):
        profile_floors = brief["category_profile"].get("hard_score_floors", {}) or {}
    truth_floor = int(profile_floors.get("product_truth_fidelity", _DEFAULT_TRUTH_FLOOR))
    proof_floor = int(profile_floors.get("category_proof_coverage", _DEFAULT_PROOF_FLOOR))
    risk_floor = int(profile_floors.get("risk_control", _DEFAULT_RISK_FLOOR))
    try:
        truth = int(sc.get("product_truth_fidelity", 0))
    except (TypeError, ValueError):
        truth = 0
    if truth < truth_floor:
        reasons.append(
            f"product_truth_fidelity={truth} 低于 {truth_floor}, 产品事实保真不足"
        )
    try:
        proof = int(sc.get("category_proof_coverage", 0))
    except (TypeError, ValueError):
        proof = 0
    if proof < proof_floor:
        reasons.append(
            f"category_proof_coverage={proof} 低于 {proof_floor}, 品类证据不足"
        )
    try:
        risk = int(sc.get("risk_control", 0))
    except (TypeError, ValueError):
        risk = 0
    if risk < risk_floor:
        reasons.append(f"risk_control={risk} 低于 {risk_floor}, 风险控制不足")

    gates = row["score"].get("hard_gate_results", {})
    if isinstance(gates, dict) and not gates.get("skipped") and not gates.get("passed"):
        reasons.extend(str(value) for value in gates.get("failures", []))
    recommendation = row["score"].get("render_recommendation")
    if recommendation in ("reject", "revise"):
        reasons.append(f"render_recommendation={recommendation}")
    if reasons:
        row["eligible_for_render"] = False
        row["ineligible_reasons"] = reasons


def _sort_key(row: dict[str, Any]) -> tuple[int, int, int]:
    """eligible 优先 → overall 高 → renderer_feasibility 高。"""
    eligible = 1 if row.get("eligible_for_render") else 0
    overall = int(row.get("overall", 0))
    try:
        feas = int(row["score"].get("scores", {}).get("renderer_feasibility", 0))
    except (TypeError, ValueError):
        feas = 0
    return (eligible, overall, feas)


def select_shortlist(
    candidates: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    *,
    top_k: int = 3,
    min_overall: int = 80,
    min_feasibility: int = 75,
    brief: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """从候选+评分中选出 shortlist。

    Args:
        candidates: creative_candidate 列表。
        scores: creative_score 列表 (与 candidates 按 candidate_id 配对)。
        top_k: 最多保留多少个。
        min_overall: 进入 shortlist 的 overall 门槛。
        min_feasibility: 进入 render 的 renderer_feasibility 门槛。
        brief: v2 brief, 提供品类评分底线；为空时使用兼容默认值。

    Returns:
        shortlist item 列表, 按 (eligible, overall, feasibility) 降序。
    """
    score_by_id = {s.get("candidate_id"): s for s in scores}
    cand_by_id = {c.get("candidate_id"): c for c in candidates}

    rows: list[dict[str, Any]] = []
    for sid, score in score_by_id.items():
        cand = cand_by_id.get(sid)
        if cand is None:
            continue
        overall = int(score.get("scores", {}).get("overall", 0))
        if overall < min_overall:
            continue
        rows.append({
            "candidate_id": sid,
            "candidate": cand,
            "score": score,
            "overall": overall,
            "eligible_for_render": True,
            "ineligible_reasons": [],
            "category_profile_id": score.get("profile_id", ""),
        })

    # 先算 eligibility, 再按 eligible 优先排序, 最后截 top_k
    for row in rows:
        _compute_eligibility(row, min_feasibility, brief)
    rows.sort(key=_sort_key, reverse=True)
    return rows[:top_k]
