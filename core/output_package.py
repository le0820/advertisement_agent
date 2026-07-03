"""组装最终上传给小云雀视频生成 agent 的品牌片规格书 + 决策报告。

输出 brand_film_spec (markdown, 上传给小云雀视频生成 agent) + 完整 package dict + report.md。
严格约束产品外观来自 dense_caption, 对敏感类目加入产品真实性约束。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deepseek_client import chat

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "build_brand_film_spec.txt"
)

_SENSITIVE_CATEGORIES = {"珠宝饰品", "服装鞋包", "高定礼服", "美妆", "医美"}


def _sensitive_constraints(brief: dict[str, Any]) -> str:
    cat = brief.get("category", "")
    constraints = brief.get("constraints", {})
    person_policy = constraints.get("person_policy") or {}
    parts: list[str] = []
    if cat in _SENSITIVE_CATEGORIES:
        parts.append("本品类易过度美化, 必须保持产品真实材质/颜色/工艺, 不得美化失真")
    if person_policy.get("model_required") and not person_policy.get("face_allowed", True):
        framing = "、".join(person_policy.get("allowed_body_framing", []))
        parts.append(
            "避免生成真实人脸, 但必须允许不露脸模特/身体局部展示; "
            f"可用取景: {framing}; 不要把避免人脸理解为禁止人物"
        )
    elif person_policy.get("model_required") and person_policy.get("face_allowed", True):
        parts.append("允许完整人物、全身穿着效果和自然人脸; 视觉重点必须放在服装版型、动态和场合")
    elif constraints.get("avoid_face_generation"):
        parts.append("避免生成真实人脸, 优先用产品/手部/人台/背影")
    if not person_policy.get("hands_allowed", True):
        parts.append("避免出现手部")
    elif constraints.get("avoid_complex_hand_motion"):
        parts.append("避免复杂手部动作")
    return "；".join(parts) if parts else "无额外约束"


def _storyboard_block(storyboard_simulation: dict[str, Any] | None) -> str:
    if not storyboard_simulation:
        return "（未启用关键帧预演）"
    return json.dumps(storyboard_simulation, ensure_ascii=False, indent=2)


def _build_brand_film_spec(
    brief: dict[str, Any], candidate: dict[str, Any],
    score: dict[str, Any], decision: dict[str, Any],
    storyboard_simulation: dict[str, Any] | None,
    template: dict[str, Any] | None, model: str | None, api_key: str | None,
) -> str:
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        candidate_json=json.dumps(candidate, ensure_ascii=False, indent=2),
        score_json=json.dumps(score, ensure_ascii=False, indent=2),
        decision_json=json.dumps(decision, ensure_ascii=False, indent=2),
        storyboard_block=_storyboard_block(storyboard_simulation),
        product_name=brief.get("product_name", "未命名产品"),
        dense_caption=brief.get("dense_caption", ""),
        must_show_second=brief.get("constraints", {}).get("must_show_product_by_second", 3),
        sensitive_constraints=_sensitive_constraints(brief),
    )
    return chat(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )


def _manual_upload_notes(brief: dict[str, Any], decision: dict[str, Any]) -> list[str]:
    person_policy = brief.get("constraints", {}).get("person_policy") or {}
    notes = [
        f"画幅选 {brief.get('aspect_ratio', '9:16')}, 时长 {brief.get('duration_seconds', 15)} 秒",
        "上传前对照 pre_render_checklist 逐条确认产品外观与 dense_caption 一致",
    ]
    if person_policy.get("model_required") and not person_policy.get("face_allowed", True):
        notes.append("如生成真人脸失败, 改用脖子以下/背影/侧影模特, 保留穿着效果")
    elif person_policy.get("model_required") and person_policy.get("face_allowed", True):
        notes.append("服装类可使用完整人物和自然人脸, 但上传前确认服装版型、垂坠和场合仍是画面重点")
    elif brief.get("constraints", {}).get("avoid_face_generation"):
        notes.append("如小云雀生成真人脸失败, 改用产品特写/人台/背影")
    notes.extend(decision.get("pre_render_checklist", []))
    return notes


def _summary(brief: dict[str, Any], candidate: dict[str, Any],
             score: dict[str, Any], decision: dict[str, Any]) -> str:
    overall = score.get("scores", {}).get("overall", 0)
    return (
        f"推荐 {candidate.get('candidate_id')} ({candidate.get('creative_route', '')}), "
        f"overall={overall}, should_render={decision.get('should_render')}, "
        f"confidence={decision.get('confidence')}。"
        f"创意: {candidate.get('one_sentence_idea', '')}"
    )


def build_final_spec_package(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    score: dict[str, Any],
    storyboard_simulation: dict[str, Any] | None,
    render_decision: dict[str, Any],
    template: dict[str, Any] | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """组装最终规格书包。

    Args:
        brief: creative_brief。
        candidate: 选中的 creative_candidate。
        score: 该候选的 creative_score。
        storyboard_simulation: 关键帧预演 (可为 None)。
        render_decision: make_render_decision() 返回值。
        template: match_template() 返回的模版 (可选)。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        output_package dict (见 plan 数据结构契约)。
    """
    brand_film_spec = _build_brand_film_spec(
        brief, candidate, score, render_decision, storyboard_simulation,
        template, model, api_key
    )
    return {
        "brand_film_spec": brand_film_spec,
        "summary": _summary(brief, candidate, score, render_decision),
        "creative_brief": brief,
        "selected_candidate": candidate,
        "score": score,
        "storyboard_simulation": storyboard_simulation,
        "render_decision": render_decision,
        "manual_upload_notes": _manual_upload_notes(brief, render_decision),
    }


def build_final_prompt_package(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    score: dict[str, Any],
    storyboard_simulation: dict[str, Any] | None,
    render_decision: dict[str, Any],
    template: dict[str, Any] | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible wrapper for callers using the old prompt-package name."""
    return build_final_spec_package(
        brief, candidate, score, storyboard_simulation, render_decision,
        template, model, api_key
    )


def build_report_md(
    package: dict[str, Any],
    *,
    all_candidates_count: int,
    rejected: list[dict[str, Any]],
    shortlisted: list[dict[str, Any]],
) -> str:
    """生成给用户看的决策报告 (markdown)。

    必须回答: 候选数 / 淘汰原因 / shortlist / 最终推荐 / 为什么值得花积分 /
    上传前检查 / 首轮失败怎么改。
    """
    dec = package.get("render_decision", {})
    cand = package.get("selected_candidate", {})
    score = package.get("score", {})
    lines: list[str] = []
    lines.append("# 创意决策报告")
    lines.append("")
    lines.append("## 概览")
    lines.append(f"- 生成创意候选数: {all_candidates_count}")
    lines.append(f"- 进入 shortlist: {len(shortlisted)} 个")
    lines.append(f"- 被淘汰: {len(rejected)} 个")
    lines.append(
        f"- 最终推荐: {dec.get('recommended_candidate_id')} "
        f"(should_render={dec.get('should_render')}, "
        f"confidence={dec.get('confidence')})"
    )
    lines.append("")

    lines.append("## 被淘汰的候选及原因")
    if rejected:
        for r in rejected:
            cid = r.get("candidate_id", "?")
            rec = r.get("render_recommendation", "")
            overall = r.get("scores", {}).get("overall", 0)
            lines.append(f"- {cid}: overall={overall}, recommendation={rec}")
    else:
        lines.append("- (无)")
    lines.append("")

    lines.append("## Shortlist")
    for s in shortlisted:
        cid = s.get("candidate_id", "?")
        overall = s.get("overall", 0)
        eligible = s.get("eligible_for_render")
        reasons = s.get("ineligible_reasons", [])
        flag = "✓ 可生成" if eligible else f"✗ 暂不生成 ({'; '.join(reasons)})"
        lines.append(f"- {cid}: overall={overall} — {flag}")
    lines.append("")

    lines.append("## 为什么这一版最值得花一次视频积分")
    lines.append(dec.get("reason", "(未给出理由)"))
    lines.append("")

    lines.append("## 上传前检查清单")
    for item in dec.get("pre_render_checklist", []):
        lines.append(f"- [ ] {item}")
    lines.append("")

    lines.append("## 预期失败模式")
    for fm in dec.get("expected_failure_modes", []):
        lines.append(f"- {fm}")
    lines.append("")

    fail = dec.get("if_first_render_fails", {})
    lines.append("## 如果第一次视频失败，优先怎么改")
    lines.append(f"可能原因: {', '.join(fail.get('likely_causes', [])) or '(未列出)'}")
    lines.append(f"建议修改: {fail.get('recommended_fix', '(未给出)')}")
    lines.append(
        f"出现以下情况不要重试 (直接换候选): "
        f"{', '.join(fail.get('do_not_retry_if', [])) or '(未列出)'}"
    )
    lines.append("")

    lines.append("## 选中候选评分摘要")
    lines.append(f"- candidate_id: {cand.get('candidate_id')}")
    lines.append(f"- creative_route: {cand.get('creative_route')}")
    lines.append(f"- overall: {score.get('scores', {}).get('overall', 0)}")
    lines.append(f"- render_recommendation: {score.get('render_recommendation')}")
    lines.append("")

    lines.append("## 最终上传规格书")
    lines.append("见同名 `.brand-film-spec.md` 文件，上传给小云雀视频生成 agent。")
    return "\n".join(lines)
