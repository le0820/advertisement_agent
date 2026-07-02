"""广告分镜提示词生成 CLI。

模式:
  fast     (默认) 原流程: 提取特征 → 模版匹配 → 生成一个最终 prompt
  explore  生成多创意候选 → 评分 → shortlist (不生成最终小云雀 prompt)
  decision 完整流程: explore → render_decision → 最终 prompt + 决策报告

输出 (data/<stem>.* 或 -o 指定路径的同名族):
  .features.json .brief.json .candidates.json .scores.json .shortlist.json
  .storyboard.json(可选) .decision.json .package.json .txt .report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from core.brief import build_creative_brief
from core.creative_scoring import score_creative_candidates
from core.creative_search import generate_creative_candidates
from core.deepseek_client import DeepSeekError
from core.extract_features import extract_features
from core.generate_prompt import generate_final_prompt
from core.llm_client import LLMError
from core.output_package import build_final_prompt_package, build_report_md
from core.render_decision import make_render_decision
from core.shortlist import select_shortlist
from core.storyboard import list_categories, match_template
from core.storyboard_simulator import generate_storyboard_simulation


def _load_env() -> None:
    """从 .env 加载环境变量 (不覆盖已存在的)。"""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _stem_path(image: str, override: str | None) -> Path:
    """推导输出文件族的主路径 (无扩展名)。"""
    if override:
        return Path(override).with_suffix("")
    if image.startswith("http://") or image.startswith("https://"):
        name = Path(urlparse(image).path).name
    else:
        name = Path(image).name
    stem = Path(name).stem or "output"
    return Path("data") / stem


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _user_options(args) -> dict:
    return {
        "platform": args.platform, "aspect_ratio": args.aspect_ratio,
        "duration": args.duration, "commercial_goal": args.commercial_goal,
        "slogan": args.slogan or "", "brand_name": args.brand_name or "",
        # 人工商业输入 (GPT P4): 让创意围绕"为什么用户会买"
        "target_audience": getattr(args, "target_audience", None),
        "selling_point": getattr(args, "selling_point", None),
        "pain_point": getattr(args, "pain_point", None),
        "usage_scene": getattr(args, "usage_scene", None),
        "cta": getattr(args, "cta", None),
        "forbidden_claim": getattr(args, "forbidden_claim", None),
        "avoid_face": True if getattr(args, "avoid_face", False) else None,
    }


def _run_fast(args, features, stem: Path, ark_model, deepseek_model) -> int:
    """原流程: 特征 → 模版 → 一个最终 prompt。"""
    print("[2/3] 匹配分镜模版")
    template = match_template(features.get("category", ""), features.get("sub_category") or None)
    if not template:
        print(f"未匹配到模版: category={features.get('category')}", file=sys.stderr)
        return 1
    print(f"  → {template.get('template_name')} ({template.get('template_id')})")
    print("[3/3] 生成完整分镜提示词 (DeepSeek)")
    try:
        prompt = generate_final_prompt(features, template, model=deepseek_model)
    except DeepSeekError as e:
        print(f"提示词生成失败: {e}", file=sys.stderr)
        return 1
    txt_path = stem.with_suffix(".txt")
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(prompt, encoding="utf-8")
    print(f"\n分镜提示词已写入: {txt_path}")
    print(f"产品特征已写入: {stem.with_suffix('.features.json')}")
    return 0


def _run_explore(args, features, stem: Path, ark_model, deepseek_model, score_model):
    """explore: brief → candidates → scores → shortlist (+ 可选 storyboard)。

    Returns: (candidates, scores, shortlisted, sims_or_None)
    """
    opts = _user_options(args)
    print("[2/6] 构建创意 brief")
    brief = build_creative_brief(features, opts)
    _write_json(stem.with_suffix(".brief.json"), brief)

    print("[3/6] 匹配分镜模版 + 生成创意候选")
    template = match_template(features.get("category", ""), features.get("sub_category") or None)
    candidates = generate_creative_candidates(
        brief, template, num_candidates=args.num_candidates, model=deepseek_model
    )
    _write_json(stem.with_suffix(".candidates.json"), candidates)
    print(f"  → 生成 {len(candidates)} 个候选")

    print("[4/6] 评分" + (f" (ARK: {score_model})" if score_model else " (ARK)"))
    scores = score_creative_candidates(
        brief, candidates, model=deepseek_model, score_model=score_model
    )
    _write_json(stem.with_suffix(".scores.json"), scores)

    print("[5/6] shortlist")
    shortlisted = select_shortlist(
        candidates, scores, top_k=args.top_k, min_overall=args.min_score
    )
    _write_json(stem.with_suffix(".shortlist.json"), shortlisted)
    print(f"  → shortlist {len(shortlisted)} 个")

    sims = []
    if args.storyboard and shortlisted:
        print("[5.5/6] 关键帧预演 (storyboard)")
        for row in shortlisted:
            try:
                sim = generate_storyboard_simulation(brief, row["candidate"], model=deepseek_model)
                sims.append(sim)
            except DeepSeekError as e:
                print(f"  storyboard 失败 {row['candidate_id']}: {e}", file=sys.stderr)
        if sims:
            _write_json(stem.with_suffix(".storyboard.json"), sims)
    return candidates, scores, shortlisted, (sims if sims else None)


def _run_decision(args, features, stem: Path, ark_model, deepseek_model, score_model) -> int:
    """decision: explore → render_decision → output_package。"""
    candidates, scores, shortlisted, sims = _run_explore(
        args, features, stem, ark_model, deepseek_model, score_model
    )
    opts = _user_options(args)
    brief = build_creative_brief(features, opts)

    print("[6/6] render_decision + 最终 prompt")
    decision = make_render_decision(brief, shortlisted, sims or [], model=deepseek_model)
    _write_json(stem.with_suffix(".decision.json"), decision)

    if not decision.get("should_render"):
        print(f"\n⚠ 没有候选值得消耗视频积分: {decision.get('reason')}", file=sys.stderr)
        report = build_report_md(
            {"selected_candidate": {}, "score": {}, "render_decision": decision},
            all_candidates_count=len(candidates),
            rejected=[s for s in scores if s.get("render_recommendation") in ("reject", "revise")],
            shortlisted=shortlisted,
        )
        stem.with_suffix(".report.md").write_text(report, encoding="utf-8")
        return 0

    rec_id = decision.get("recommended_candidate_id")
    cand_by_id = {c.get("candidate_id"): c for c in candidates}
    score_by_id = {s.get("candidate_id"): s for s in scores}
    selected = cand_by_id.get(rec_id, shortlisted[0]["candidate"] if shortlisted else {})
    selected_score = score_by_id.get(rec_id, {})
    selected_sim = None
    if sims:
        selected_sim = next((s for s in sims if s.get("candidate_id") == rec_id), None)

    package = build_final_prompt_package(
        brief, selected, selected_score, selected_sim, decision,
        model=deepseek_model,
    )
    _write_json(stem.with_suffix(".package.json"), package)
    stem.with_suffix(".txt").write_text(package["xiaoyunque_prompt"], encoding="utf-8")

    rejected = [s for s in scores if s.get("render_recommendation") in ("reject", "revise")]
    report = build_report_md(
        package, all_candidates_count=len(candidates),
        rejected=rejected, shortlisted=shortlisted,
    )
    stem.with_suffix(".report.md").write_text(report, encoding="utf-8")

    print(f"\n最终提示词: {stem.with_suffix('.txt')}")
    print(f"决策报告: {stem.with_suffix('.report.md')}")
    print(f"完整包: {stem.with_suffix('.package.json')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="产品图 → 分镜提示词 (供小云雀人工测试)"
    )
    parser.add_argument("image", nargs="?", help="产品样例图本地路径或 URL")
    parser.add_argument("-o", "--output", default=None,
                        help="输出路径覆盖 (默认 data/<图片名>.txt)")
    parser.add_argument("--list-categories", action="store_true",
                        help="列出可用类目体系后退出")
    parser.add_argument("--mode", choices=["fast", "explore", "decision"], default="fast",
                        help="fast=原流程; explore=候选+评分+shortlist; "
                             "decision=完整流程+最终推荐 (推荐)")
    parser.add_argument("--num-candidates", type=int, default=8, help="创意候选数量")
    parser.add_argument("--top-k", type=int, default=3, help="shortlist 上限")
    parser.add_argument("--min-score", type=int, default=80, help="shortlist overall 门槛")
    parser.add_argument("--platform", default="douyin",
                        choices=["douyin", "xiaohongshu", "video_account", "tiktok", "youtube"])
    parser.add_argument("--aspect-ratio", default="9:16", choices=["9:16", "16:9", "1:1"])
    parser.add_argument("--duration", type=int, default=15, help="视频时长秒数")
    parser.add_argument("--commercial-goal", default="creative_ad",
                        choices=["brand_film", "creative_ad", "direct_response", "social_post"])
    parser.add_argument("--slogan", default=None, help="品牌 slogan (留空不捏造)")
    parser.add_argument("--brand-name", default=None, help="品牌名 (留空不捏造)")
    # 人工商业输入 (GPT P4)
    parser.add_argument("--target-audience", default=None, help="目标人群 (覆盖图像提取的)")
    parser.add_argument("--selling-point", default=None, action="append",
                        help="补充卖点 (可多次传)")
    parser.add_argument("--pain-point", default=None, action="append",
                        help="用户痛点 (可多次传)")
    parser.add_argument("--usage-scene", default=None, action="append",
                        help="使用场景 (可多次传)")
    parser.add_argument("--cta", default=None, help="行动号召文案")
    parser.add_argument("--forbidden-claim", default=None, action="append",
                        help="禁用 claim (可多次传, 如 最便宜/第一)")
    parser.add_argument("--avoid-face", action="store_true",
                        help="显式规避清晰真实人脸；服装类默认允许自然人脸和全身人物")
    parser.add_argument("--storyboard", action="store_true",
                        help="启用关键帧预演 (默认关闭省成本, P2 将增强)")
    parser.add_argument("--ark-model", default=None, help="ARK Doubao 模型名覆盖 (特征提取)")
    parser.add_argument("--deepseek-model", default=None, help="DeepSeek 模型名覆盖")
    parser.add_argument("--score-model", default=None, help="ARK 裁判模型名; 不设置则用默认 doubao-seed-2-0-lite-260428 (responses 接口)")
    args = parser.parse_args(argv)

    _load_env()

    if args.list_categories:
        for cat, subs in list_categories().items():
            print(f"{cat}: {'、'.join(subs)}")
        return 0

    if not args.image:
        parser.error("image is required (unless --list-categories)")

    print(f"[1/6] 提取产品特征 (Doubao 多模态): {args.image}")
    try:
        features = extract_features(args.image, model=args.ark_model)
    except LLMError as e:
        print(f"特征提取失败: {e}", file=sys.stderr)
        return 1
    print(f"  → 商品名称={features.get('product_name')} category={features.get('category')}")

    stem = _stem_path(args.image, args.output)
    _write_json(stem.with_suffix(".features.json"), features)

    if args.mode == "fast":
        return _run_fast(args, features, stem, args.ark_model, args.deepseek_model)
    if args.mode == "explore":
        _run_explore(args, features, stem, args.ark_model, args.deepseek_model, args.score_model)
        return 0
    return _run_decision(args, features, stem, args.ark_model, args.deepseek_model, args.score_model)


if __name__ == "__main__":
    sys.exit(main())
