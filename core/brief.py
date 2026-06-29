"""产品特征 → 广告创意 brief。

把 extract_features 的输出升级为结构化创意 brief：补充品牌阶段、商业目标、
平台、画幅、时长、约束等，供 creative_search / scoring 使用。
P0 为规则填充，不调用 LLM（保持低成本与确定性）。
"""

from __future__ import annotations

from typing import Any

_BRAND_STAGE_BY_GOAL = {
    "brand_film": "awareness",
    "creative_ad": "awareness",
    "direct_response": "conversion",
    "social_post": "retargeting",
}

_DEFAULT_DISTRIBUTION = ["douyin", "tiktok", "youtube"]

# 容易"过度美化"的类目，需要产品真实性约束 + 规避人脸生成
_SENSITIVE_CATEGORIES = {"珠宝饰品", "高定礼服", "美妆", "医美"}


def build_creative_brief(
    features: dict[str, Any],
    user_options: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """从产品特征派生广告创意 brief。

    Args:
        features: extract_features() 返回的特征 dict。
        user_options: CLI 可选项 (platform/aspect_ratio/duration/
            commercial_goal/slogan/brand_name/brand_stage/avoid_face/
            avoid_hand/must_have_cta)。未提供则用合理默认值，不捏造品牌资产。
        model: 预留参数，P0 不调用 LLM。

    Returns:
        creative_brief dict (见 schemas/creative_brief.schema.json)。
    """
    opts = user_options or {}
    sp = features.get("selling_points", [])
    if not isinstance(sp, list):
        sp = [str(sp)]
    scenarios = features.get("distribution_scenarios") or list(_DEFAULT_DISTRIBUTION)

    commercial_goal = opts.get("commercial_goal") or "creative_ad"
    brand_stage = opts.get("brand_stage") or _BRAND_STAGE_BY_GOAL.get(
        commercial_goal, "awareness"
    )
    category = features.get("category", "")
    sensitive = category in _SENSITIVE_CATEGORIES

    avoid_face = opts.get("avoid_face")
    if avoid_face is None:
        avoid_face = sensitive or commercial_goal == "brand_film"
    avoid_hand = opts.get("avoid_hand")
    if avoid_hand is None:
        avoid_hand = False

    return {
        "product_name": features.get("product_name", ""),
        "category": category,
        "sub_category": features.get("sub_category", "") or "",
        "dense_caption": features.get("dense_caption", ""),
        "selling_points": sp,
        "target_audience": features.get("target_audience", ""),
        "distribution_scenarios": scenarios,
        "brand_name": opts.get("brand_name", ""),
        "brand_stage": brand_stage,
        "brand_assets": {
            "slogan": opts.get("slogan", ""),
            "tone": "",
            "visual_codes": [],
            "forbidden_claims": [],
        },
        "commercial_goal": commercial_goal,
        "platform": opts.get("platform") or "douyin",
        "aspect_ratio": opts.get("aspect_ratio") or "9:16",
        "duration_seconds": int(opts.get("duration") or 15),
        "constraints": {
            "must_show_product_by_second": 3,
            "must_have_cta": bool(opts.get("must_have_cta", False)),
            "avoid_face_generation": bool(avoid_face),
            "avoid_complex_hand_motion": bool(avoid_hand),
        },
    }
