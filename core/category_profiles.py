"""Three-category taxonomy, proof contracts, and deterministic gates.

Codex owns semantic judgment. This module only normalizes taxonomy, snapshots
the selected category profile, and verifies structured proof/claim fields.
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parent.parent
CATEGORY_PROFILES_PATH = _ROOT / "harness" / "category_profiles.json"
REFERENCE_VIDEO_MANIFEST_PATH = _ROOT / "harness" / "reference_video_manifest.json"

SCORE_DIMENSIONS = (
    "hook_strength",
    "product_truth_fidelity",
    "category_proof_coverage",
    "consumer_relevance",
    "brand_fit",
    "visual_memorability",
    "narrative_coherence",
    "platform_fit",
    "renderer_feasibility",
    "risk_control",
    "commercial_intent",
)

DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "hook_strength": 0.10,
    "product_truth_fidelity": 0.15,
    "category_proof_coverage": 0.17,
    "consumer_relevance": 0.09,
    "brand_fit": 0.08,
    "visual_memorability": 0.10,
    "narrative_coherence": 0.06,
    "platform_fit": 0.06,
    "renderer_feasibility": 0.08,
    "risk_control": 0.06,
    "commercial_intent": 0.05,
}

_CATEGORY_KEYWORDS = {
    "美妆个护": (
        "美妆", "彩妆", "口红", "唇釉", "遮瑕", "粉底", "眼影", "睫毛",
        "美甲", "甲油", "指甲", "护肤", "面霜", "精华", "洁面", "面膜",
        "医美", "敷料", "私护", "洗液",
    ),
    "食品饮料": (
        "食品", "零食", "糖果", "巧克力", "软糖", "面包", "饮料", "饮品",
        "咖啡", "茶饮", "酒", "粉面", "速食", "速冻", "预制菜", "料理包",
        "食物", "小吃",
    ),
    "服饰配件": (
        "服装", "外套", "开衫", "针织", "毛衣", "西装", "礼服", "连衣裙",
        "旗袍", "衬衫", "裤", "鞋", "靴", "箱包", "手袋", "背包", "首饰",
        "珠宝", "戒指", "项链", "耳环", "手镯", "腕表", "饰品",
    ),
}

_SUBCATEGORY_KEYWORDS = {
    "美妆个护": {
        "美甲": ("美甲", "甲油", "指甲"),
        "美妆": ("美妆", "彩妆", "口红", "唇", "遮瑕", "粉底", "眼影", "睫毛", "妆效"),
        "护肤品": ("护肤", "面霜", "精华", "洁面", "面膜", "乳液", "爽肤"),
        "医美用品": ("医美", "医用敷料", "敷料", "医美耗材"),
    },
    "食品饮料": {
        "零食": ("零食", "糖果", "巧克力", "软糖", "饼干", "薯片", "坚果"),
        "饮料": ("饮料", "饮品", "咖啡", "茶饮", "果汁", "酒水", "汽水"),
        "速冻速食": ("速冻", "速食", "方便食品", "即食", "粉面", "酸辣粉", "泡面"),
        "预制菜": ("预制菜", "料理包", "半成品菜", "预制料理"),
    },
    "服饰配件": {
        "服装": ("服装", "外套", "开衫", "针织", "毛衣", "西装", "礼服", "连衣裙", "旗袍", "衬衫", "裤"),
        "饰品": ("饰品", "首饰", "珠宝", "戒指", "对戒", "项链", "耳环", "手镯", "手链", "腕表"),
        "鞋包": ("鞋包", "鞋履", "鞋", "靴", "箱包", "手袋", "背包", "托特", "包袋"),
    },
}


def _validate_profiles(data: dict[str, Any]) -> None:
    for key in ("framework_id", "version", "taxonomy_contract", "legacy_aliases", "categories"):
        if key not in data:
            raise ValueError(f"invalid category profiles, missing {key}")

    expected_categories = data["taxonomy_contract"].get("primary_category_enum", [])
    if list(data["categories"].keys()) != expected_categories:
        raise ValueError("category profile keys must match primary_category_enum in order")

    for category, profile in data["categories"].items():
        weights = profile.get("scoring", {}).get("weights", {})
        if set(weights) != set(SCORE_DIMENSIONS):
            raise ValueError(f"{category} score dimensions do not match v2 contract")
        if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
            raise ValueError(f"{category} score weights must sum to 1")


@lru_cache(maxsize=1)
def _load_default_profiles() -> dict[str, Any]:
    with open(CATEGORY_PROFILES_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    _validate_profiles(data)
    return data


def load_category_profiles(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the three-category profile registry."""
    if path is None:
        return copy.deepcopy(_load_default_profiles())
    with open(Path(path), "r", encoding="utf-8") as handle:
        data = json.load(handle)
    _validate_profiles(data)
    return data


def list_category_taxonomy() -> dict[str, list[str]]:
    data = _load_default_profiles()
    return {
        category: list(profile.get("subcategories", {}).keys())
        for category, profile in data["categories"].items()
    }


def normalize_primary_category(category: Any) -> str:
    value = str(category or "").strip()
    data = _load_default_profiles()
    if value in data["categories"]:
        return value
    return str(data.get("legacy_aliases", {}).get("categories", {}).get(value, ""))


def normalize_subcategory(category: str, subcategory: Any) -> str:
    canonical_category = normalize_primary_category(category)
    value = str(subcategory or "").strip()
    if not canonical_category or not value:
        return ""
    subcategories = _load_default_profiles()["categories"][canonical_category]["subcategories"]
    if value in subcategories:
        return value
    aliases = (
        _load_default_profiles()
        .get("legacy_aliases", {})
        .get("subcategories", {})
        .get(canonical_category, {})
    )
    return str(aliases.get(value, ""))


def infer_taxonomy_from_text(text: Any) -> tuple[str, str]:
    haystack = str(text or "")
    category = ""
    best_hits = 0
    for candidate, keywords in _CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in haystack)
        if hits > best_hits:
            category, best_hits = candidate, hits
    if not category:
        return "", ""

    subcategory = ""
    sub_hits = 0
    for candidate, keywords in _SUBCATEGORY_KEYWORDS[category].items():
        hits = sum(1 for keyword in keywords if keyword in haystack)
        if hits > sub_hits:
            subcategory, sub_hits = candidate, hits
    return category, subcategory


def _extension_contract(
    *,
    candidate_name: str = "",
    parent_hint: str = "",
    reason: str = "",
    future_profile_required: bool = False,
    custom_attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "candidate_name": candidate_name,
        "parent_hint": parent_hint,
        "reason": reason,
        "future_profile_required": bool(future_profile_required),
        "custom_attributes": dict(custom_attributes or {}),
    }


def build_taxonomy(
    category: Any,
    subcategory: Any = "",
    *,
    text: Any = "",
    status: Any = None,
    confidence: Any = None,
    evidence: list[str] | None = None,
    extension: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize old/new labels into the extensible taxonomy artifact."""
    raw_category = str(category or "").strip()
    raw_subcategory = str(subcategory or "").strip()
    canonical_category = normalize_primary_category(raw_category)
    canonical_subcategory = normalize_subcategory(canonical_category, raw_subcategory)
    inferred_category, inferred_subcategory = infer_taxonomy_from_text(text)

    category_inferred = False
    subcategory_inferred = False
    if not canonical_category and inferred_category:
        canonical_category = inferred_category
        category_inferred = True
    if (
        canonical_category
        and raw_category
        and raw_category != canonical_category
        and inferred_category == canonical_category
        and inferred_subcategory
    ):
        canonical_subcategory = inferred_subcategory
        subcategory_inferred = True
    if canonical_category and not canonical_subcategory and inferred_category == canonical_category:
        canonical_subcategory = inferred_subcategory
        subcategory_inferred = bool(inferred_subcategory)

    profile = _load_default_profiles().get("categories", {}).get(canonical_category, {})
    subprofile = profile.get("subcategories", {}).get(canonical_subcategory, {})
    incoming_extension = extension if isinstance(extension, dict) else {}
    requested_status = str(status or "").strip()
    if canonical_subcategory:
        resolved_status = "provisional" if category_inferred or subcategory_inferred else "matched"
        if requested_status in ("matched", "provisional"):
            resolved_status = requested_status
    elif raw_subcategory:
        resolved_status = "custom"
    elif requested_status in ("custom", "unresolved"):
        resolved_status = requested_status
    elif incoming_extension.get("candidate_name"):
        resolved_status = "custom"
    else:
        resolved_status = "unresolved"

    default_confidence = {
        "matched": 1.0,
        "provisional": 0.75,
        "custom": 0.5,
        "unresolved": 0.0,
    }[resolved_status]
    try:
        confidence_value = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence_value = default_confidence

    normalized_detail = (
        raw_subcategory
        if raw_subcategory and raw_subcategory != canonical_subcategory
        else ""
    )
    extension_value = _extension_contract(
        candidate_name=str(
            incoming_extension.get("candidate_name")
            or normalized_detail
            or (raw_subcategory if resolved_status == "custom" else "")
        ),
        parent_hint=str(
            incoming_extension.get("parent_hint")
            or canonical_subcategory
            or canonical_category
        ),
        reason=str(
            incoming_extension.get("reason")
            or ("subcategory is outside the current registry" if resolved_status == "custom" else "")
            or ("detail label normalized under a reserved parent subcategory" if normalized_detail else "")
        ),
        future_profile_required=bool(
            incoming_extension.get("future_profile_required", resolved_status == "custom")
        ),
        custom_attributes=incoming_extension.get("custom_attributes")
        if isinstance(incoming_extension.get("custom_attributes"), dict)
        else {},
    )
    return {
        "primary_category": canonical_category,
        "primary_category_id": str(profile.get("profile_id", "")),
        "subcategory": canonical_subcategory,
        "subcategory_id": str(subprofile.get("id", "")),
        "subcategory_status": resolved_status,
        "subcategory_confidence": confidence_value,
        "subcategory_evidence": [str(item) for item in (evidence or []) if item],
        "subcategory_extension": extension_value,
    }


def _category_from_artifact(artifact: dict[str, Any] | str | None) -> str:
    if isinstance(artifact, str):
        return normalize_primary_category(artifact)
    if not isinstance(artifact, dict):
        return ""
    taxonomy = artifact.get("taxonomy") if isinstance(artifact.get("taxonomy"), dict) else {}
    return normalize_primary_category(
        taxonomy.get("primary_category") or artifact.get("category")
    )


def _subcategory_from_artifact(artifact: dict[str, Any] | None, category: str) -> str:
    if not isinstance(artifact, dict):
        return ""
    taxonomy = artifact.get("taxonomy") if isinstance(artifact.get("taxonomy"), dict) else {}
    return normalize_subcategory(
        category,
        taxonomy.get("subcategory") or artifact.get("sub_category"),
    )


def get_category_profile(artifact: dict[str, Any] | str | None) -> dict[str, Any] | None:
    category = _category_from_artifact(artifact)
    profile = _load_default_profiles().get("categories", {}).get(category)
    return copy.deepcopy(profile) if isinstance(profile, dict) else None


def get_subcategory_profile(artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    category = _category_from_artifact(artifact)
    subcategory = _subcategory_from_artifact(artifact, category)
    profile = _load_default_profiles().get("categories", {}).get(category, {})
    subprofile = profile.get("subcategories", {}).get(subcategory)
    return copy.deepcopy(subprofile) if isinstance(subprofile, dict) else None


def resolve_critical_proof_groups(
    category_profile: dict[str, Any],
    subcategory_profile: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    base = copy.deepcopy(
        category_profile.get("creative_contract", {}).get("critical_proof_groups", [])
    )
    if not subcategory_profile:
        return base
    specific = copy.deepcopy(subcategory_profile.get("critical_proof_groups", []))
    if subcategory_profile.get("critical_group_mode") == "replace":
        return specific
    by_id = {group.get("id"): group for group in base if group.get("id")}
    for group in specific:
        if group.get("id"):
            by_id[group["id"]] = group
    return list(by_id.values())


def build_category_requirements(artifact: dict[str, Any]) -> dict[str, Any]:
    category = _category_from_artifact(artifact)
    subcategory = _subcategory_from_artifact(artifact, category)
    profile = get_category_profile(artifact)
    subprofile = get_subcategory_profile(artifact)
    if not profile:
        return {}
    creative = profile.get("creative_contract", {})
    required_tags = list(creative.get("required_proof_tags", []))
    if subprofile:
        required_tags.extend(subprofile.get("additional_proof_tags", []))
    required_tags = list(dict.fromkeys(str(tag) for tag in required_tags if tag))
    data = _load_default_profiles()
    return {
        "framework_version": data["version"],
        "profile_id": profile.get("profile_id", ""),
        "category": category,
        "subcategory": subcategory,
        "subcategory_id": (subprofile or {}).get("id", ""),
        "required_proof_tags": required_tags,
        "critical_proof_groups": resolve_critical_proof_groups(profile, subprofile),
        "recommended_beat_order": list(creative.get("recommended_beat_order", [])),
        "route_families": list(creative.get("route_families", [])),
        "reference_pattern_ids": list(creative.get("reference_pattern_ids", [])),
        "minimum_critical_group_coverage": profile.get("scoring", {}).get(
            "minimum_critical_group_coverage", 1.0
        ),
        "hard_score_floors": copy.deepcopy(
            profile.get("scoring", {}).get("hard_floors", {})
        ),
        "score_weights": copy.deepcopy(profile.get("scoring", {}).get("weights", {})),
        "claim_guardrails": list(profile.get("claim_guardrails", [])),
        "renderer_risks": list(profile.get("renderer_risks", [])),
        "spec_contract": copy.deepcopy(profile.get("spec_contract", {})),
    }


def score_weights_for(artifact: dict[str, Any] | None) -> dict[str, float]:
    profile = get_category_profile(artifact)
    weights = profile.get("scoring", {}).get("weights") if profile else None
    if not isinstance(weights, dict) or set(weights) != set(SCORE_DIMENSIONS):
        return dict(DEFAULT_SCORE_WEIGHTS)
    return {key: float(weights[key]) for key in SCORE_DIMENSIONS}


def collect_proof_tags(candidate: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    strategy = candidate.get("category_strategy")
    if isinstance(strategy, dict):
        for value in strategy.get("required_proofs_covered", []):
            if value:
                tags.add(str(value))
        for proof in strategy.get("proof_sequence", []):
            if not isinstance(proof, dict):
                continue
            if proof.get("proof_tag"):
                tags.add(str(proof["proof_tag"]))
            for value in proof.get("proof_tags", []):
                if value:
                    tags.add(str(value))
    for shot in candidate.get("shot_plan", []):
        if not isinstance(shot, dict):
            continue
        for value in shot.get("proof_tags", []):
            if value:
                tags.add(str(value))
    return tags


def _parse_start_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else None


def _product_first_seen_at(candidate: dict[str, Any]) -> float | None:
    strategy = candidate.get("category_strategy")
    if isinstance(strategy, dict):
        parsed = _parse_start_seconds(strategy.get("product_first_seen_at"))
        if parsed is not None:
            return parsed
    starts: list[float] = []
    for shot in candidate.get("shot_plan", []):
        if not isinstance(shot, dict):
            continue
        if shot.get("product_visibility") not in ("clear", "hero"):
            continue
        parsed = _parse_start_seconds(shot.get("time_range"))
        if parsed is not None:
            starts.append(parsed)
    return min(starts) if starts else None


def _unsafe_claims(candidate: dict[str, Any]) -> list[str]:
    strategy = candidate.get("category_strategy")
    claims = strategy.get("claims_used", []) if isinstance(strategy, dict) else []
    unsafe: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        basis = str(claim.get("basis", "none"))
        risk_level = str(claim.get("risk_level", "medium"))
        if risk_level == "high" and basis not in ("observed", "user_provided", "verified_brand_asset"):
            unsafe.append(str(claim.get("text", "unnamed high-risk claim")))
    return unsafe


def evaluate_candidate_gates(
    brief: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate only structured evidence fields; do not re-judge creative text."""
    requirements = build_category_requirements(brief)
    if not requirements:
        return {
            "profile_id": "",
            "passed": True,
            "skipped": True,
            "failures": [],
            "critical_group_coverage": 1.0,
            "critical_groups": [],
            "product_first_seen_at": _product_first_seen_at(candidate),
            "product_deadline": 3,
            "unsafe_claims": [],
        }

    tags = collect_proof_tags(candidate)
    group_results = []
    for group in requirements.get("critical_proof_groups", []):
        alternatives = [str(value) for value in group.get("any_of", [])]
        matched = sorted(tags.intersection(alternatives))
        group_results.append({
            "id": str(group.get("id", "")),
            "passed": bool(matched),
            "matched_tags": matched,
            "expected_any_of": alternatives,
        })
    satisfied = len([row for row in group_results if row["passed"]])
    coverage = satisfied / len(group_results) if group_results else 1.0

    profile_deadline = 3.0
    try:
        brief_deadline = float(
            brief.get("constraints", {}).get("must_show_product_by_second", 3)
        )
    except (TypeError, ValueError):
        brief_deadline = 3.0
    deadline = min(profile_deadline, brief_deadline)
    first_seen = _product_first_seen_at(candidate)
    first_seen_passed = first_seen is not None and first_seen <= deadline
    unsafe_claims = _unsafe_claims(candidate)
    minimum_coverage = float(requirements.get("minimum_critical_group_coverage", 1.0))

    failures: list[str] = []
    if not first_seen_passed:
        failures.append(
            f"product_first_seen_at={first_seen!r} exceeds or misses {deadline:g}s deadline"
        )
    if coverage < minimum_coverage:
        missing = [row["id"] for row in group_results if not row["passed"]]
        failures.append(
            f"critical proof coverage {coverage:.2f} below {minimum_coverage:.2f}: {', '.join(missing)}"
        )
    if unsafe_claims:
        failures.append("unsupported high-risk claims: " + "; ".join(unsafe_claims))

    return {
        "profile_id": requirements.get("profile_id", ""),
        "subcategory_id": requirements.get("subcategory_id", ""),
        "passed": not failures,
        "skipped": False,
        "failures": failures,
        "proof_tags": sorted(tags),
        "critical_group_coverage": round(coverage, 4),
        "minimum_critical_group_coverage": minimum_coverage,
        "critical_groups": group_results,
        "product_first_seen_at": first_seen,
        "product_deadline": deadline,
        "unsafe_claims": unsafe_claims,
    }
