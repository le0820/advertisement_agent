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
        user_options: CLI 可选项。支持:
            - platform/aspect_ratio/duration/commercial_goal
            - slogan/brand_name/brand_stage/avoid_face/avoid_hand/must_have_cta
            - 人工商业输入 (GPT P4): target_audience/selling_point/pain_point/
              usage_scene/cta/forbidden_claim (字符串或列表, 覆盖/追加 features)
        model: 预留参数, P0 不调用 LLM。

    Returns:
        creative_brief dict (见 schemas/creative_brief.schema.json)。
    """
    opts = user_options or {}
    sp = features.get("selling_points", [])
    if not isinstance(sp, list):
        sp = [str(sp)]
    # 人工补充卖点 (追加, 不去重 — 让评分看到完整输入)
    extra_sp = _as_list(opts.get("selling_point"))
    if extra_sp:
        sp = sp + extra_sp
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

    # 人工商业输入覆盖 features
    target_audience = opts.get("target_audience") or features.get("target_audience", "")
    pain_points = _as_list(opts.get("pain_point"))
    usage_scenes = _as_list(opts.get("usage_scene"))
    cta = opts.get("cta") or ""
    forbidden = _as_list(opts.get("forbidden_claim"))

    return {
        "product_name": features.get("product_name", ""),
        "category": category,
        "sub_category": features.get("sub_category", "") or "",
        "dense_caption": features.get("dense_caption", ""),
        "selling_points": sp,
        "target_audience": target_audience,
        "distribution_scenarios": scenarios,
        "brand_name": opts.get("brand_name", ""),
        "brand_stage": brand_stage,
        "brand_assets": {
            "slogan": opts.get("slogan", ""),
            "tone": "",
            "visual_codes": [],
            "forbidden_claims": forbidden,
        },
        "commercial_goal": commercial_goal,
        "platform": opts.get("platform") or "douyin",
        "aspect_ratio": opts.get("aspect_ratio") or "9:16",
        "duration_seconds": int(opts.get("duration") or 15),
        # 人工商业输入 (GPT P4): 让 creative_search 围绕"为什么用户会买"而非仅图像外观
        "pain_points": pain_points,
        "usage_scenes": usage_scenes,
        "cta": cta,
        "constraints": {
            "must_show_product_by_second": 3,
            "must_have_cta": bool(opts.get("must_have_cta", False)) or bool(cta),
            "avoid_face_generation": bool(avoid_face),
            "avoid_complex_hand_motion": bool(avoid_hand),
        },
    }


def _as_list(v: Any) -> list[str]:
    """把 str/list/None 转成 list[str]。str 视为单元素。"""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    s = str(v).strip()
    return [s] if s else []
