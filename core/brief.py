"""Product understanding to a category-aware creative brief.

This is a deterministic adapter. Codex owns product understanding and creative
judgment; the adapter normalizes taxonomy, snapshots the profile, and merges
explicit user commercial inputs without calling a model.
"""

from __future__ import annotations

from typing import Any

from .category_profiles import (
    build_category_requirements,
    build_taxonomy,
    get_category_profile,
)


_BRAND_STAGE_BY_GOAL = {
    "brand_film": "awareness",
    "creative_ad": "awareness",
    "direct_response": "conversion",
    "social_post": "retargeting",
}

_DEFAULT_DISTRIBUTION = ["douyin", "tiktok", "youtube"]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    text = str(value).strip()
    return [text] if text else []


def _normalized_taxonomy(
    features: dict[str, Any],
    options: dict[str, Any],
    product_name: str,
    dense_caption: str,
) -> dict[str, Any]:
    incoming = features.get("taxonomy") if isinstance(features.get("taxonomy"), dict) else {}
    category = options.get("category_hint") or incoming.get("primary_category") or features.get("category")
    subcategory = (
        options.get("subcategory_hint")
        or incoming.get("subcategory")
        or features.get("sub_category")
    )
    evidence = _as_list(incoming.get("subcategory_evidence"))
    if options.get("category_hint"):
        evidence.append("user category hint")
    if options.get("subcategory_hint"):
        evidence.append("user subcategory hint")
    return build_taxonomy(
        category,
        subcategory,
        text=f"{product_name} {dense_caption}",
        status=incoming.get("subcategory_status"),
        confidence=incoming.get("subcategory_confidence"),
        evidence=evidence,
        extension=incoming.get("subcategory_extension")
        if isinstance(incoming.get("subcategory_extension"), dict)
        else None,
    )


def _build_person_policy(
    default_policy: dict[str, Any],
    avoid_face: bool,
    avoid_hand: bool,
) -> dict[str, Any]:
    allowed = [str(value) for value in default_policy.get("allowed_body_framing", [])]
    if avoid_face:
        allowed = [
            value for value in allowed
            if "face" not in value.lower() and "portrait" not in value.lower()
        ]
        for fallback in ("back view", "side profile without face", "neck-down", "hands", "product-only"):
            if fallback not in allowed:
                allowed.append(fallback)
    if avoid_hand:
        allowed = [value for value in allowed if "hand" not in value.lower()]
    return {
        "face_allowed": bool(default_policy.get("face_allowed", True)) and not avoid_face,
        "human_body_allowed": bool(default_policy.get("human_body_allowed", True)),
        "hands_allowed": bool(default_policy.get("hands_allowed", True)) and not avoid_hand,
        "model_required": bool(default_policy.get("model_required", False)),
        "allowed_body_framing": allowed,
    }


def build_creative_brief(
    features: dict[str, Any],
    user_options: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Build a v2 creative brief from a v2 or legacy feature artifact."""
    del model
    options = user_options or {}
    identity = features.get("product_identity") if isinstance(features.get("product_identity"), dict) else {}
    product_name = str(features.get("product_name") or identity.get("product_name") or "")
    dense_caption = str(features.get("dense_caption") or "")
    taxonomy = _normalized_taxonomy(features, options, product_name, dense_caption)
    category = taxonomy["primary_category"]
    subcategory = taxonomy["subcategory"]

    hypotheses = (
        features.get("commercial_hypotheses")
        if isinstance(features.get("commercial_hypotheses"), dict)
        else {}
    )
    selling_points = _as_list(
        features.get("selling_points") or hypotheses.get("selling_points")
    )
    selling_points.extend(_as_list(options.get("selling_point")))
    selling_points = list(dict.fromkeys(selling_points))

    target_audience = str(
        options.get("target_audience")
        or features.get("target_audience")
        or next(iter(_as_list(hypotheses.get("target_audiences"))), "")
    )
    pain_points = _as_list(options.get("pain_point"))
    if not pain_points:
        pain_points = _as_list(hypotheses.get("consumer_tensions"))
    usage_scenes = _as_list(options.get("usage_scene"))
    if not usage_scenes:
        usage_scenes = _as_list(hypotheses.get("usage_scenes"))

    distribution_scenarios = _as_list(features.get("distribution_scenarios"))
    if not distribution_scenarios:
        distribution_scenarios = list(_DEFAULT_DISTRIBUTION)

    commercial_goal = str(options.get("commercial_goal") or "brand_film")
    brand_stage = str(
        options.get("brand_stage")
        or _BRAND_STAGE_BY_GOAL.get(commercial_goal, "awareness")
    )
    cta = str(options.get("cta") or "")
    forbidden_claims = _as_list(options.get("forbidden_claim"))

    profile = get_category_profile(category) or {}
    requirements_seed = {
        "taxonomy": taxonomy,
        "category": category,
        "sub_category": subcategory,
    }
    category_requirements = build_category_requirements(requirements_seed)
    default_policy = profile.get("person_policy", {}) if isinstance(profile, dict) else {}
    avoid_face = bool(options.get("avoid_face", False))
    avoid_hand = bool(options.get("avoid_hand", False))
    person_policy = _build_person_policy(default_policy, avoid_face, avoid_hand)

    truth_boundaries = (
        features.get("truth_boundaries")
        if isinstance(features.get("truth_boundaries"), dict)
        else {"observed": [], "inferred": [], "unknown": [], "forbidden_inferences": []}
    )
    visual_facts = (
        features.get("visual_facts")
        if isinstance(features.get("visual_facts"), dict)
        else {}
    )
    claim_guardrails = _as_list(category_requirements.get("claim_guardrails"))
    forbidden = list(dict.fromkeys(
        forbidden_claims + _as_list(truth_boundaries.get("forbidden_inferences"))
    ))

    constraints = {
        "must_show_product_by_second": float(options.get("must_show_product_by_second") or 3),
        "must_have_cta": bool(options.get("must_have_cta", False)) or bool(cta),
        "avoid_face_generation": avoid_face,
        "avoid_complex_hand_motion": avoid_hand,
        "person_policy": person_policy,
        "category_requirements": category_requirements,
    }

    brief: dict[str, Any] = {
        "schema_version": "2.0",
        "product_name": product_name,
        "taxonomy": taxonomy,
        "category": category,
        "sub_category": subcategory,
        "dense_caption": dense_caption,
        "product_truth": visual_facts,
        "truth_boundaries": truth_boundaries,
        "selling_points": selling_points,
        "target_audience": target_audience,
        "distribution_scenarios": distribution_scenarios,
        "brand_name": str(options.get("brand_name") or ""),
        "brand_stage": brand_stage,
        "brand_assets": {
            "slogan": str(options.get("slogan") or ""),
            "tone": str(options.get("brand_tone") or ""),
            "visual_codes": _as_list(options.get("visual_code")),
            "forbidden_claims": forbidden_claims,
        },
        "commercial_goal": commercial_goal,
        "platform": str(options.get("platform") or "douyin"),
        "aspect_ratio": str(options.get("aspect_ratio") or "9:16"),
        "duration_seconds": int(options.get("duration") or options.get("duration_seconds") or 15),
        "pain_points": pain_points,
        "usage_scenes": usage_scenes,
        "cta": cta,
        "category_profile": category_requirements,
        "claim_boundaries": {
            "allowed": _as_list(truth_boundaries.get("observed")),
            "requires_user_evidence": claim_guardrails,
            "forbidden": forbidden,
        },
        "constraints": constraints,
    }
    if features.get("category_conflict"):
        brief["category_conflict"] = features["category_conflict"]
    return brief
