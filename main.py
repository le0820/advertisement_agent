"""广告分镜提示词生成 CLI。

流程:
  python main.py <产品图路径|URL> [-o 输出文件]

  1. 多模态 LLM 提取产品特征 (category / sub_category / dense_caption)
  2. 按 category 匹配分镜模版
  3. 组装分镜提示词 → 打印 + 写文件 (供人工上传小云雀)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from core.extract_features import extract_features
from core.llm_client import LLMError
from core.storyboard import build_prompt, list_categories, match_template


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="产品图 → 分镜提示词 (供小云雀人工测试)"
    )
    parser.add_argument("image", nargs="?", help="产品样例图本地路径或 URL")
    parser.add_argument("-o", "--output", default=None, help="分镜提示词输出文件路径")
    parser.add_argument(
        "--list-categories", action="store_true", help="列出可用类目体系后退出"
    )
    parser.add_argument("--model", default=None, help="ARK 模型名覆盖")
    args = parser.parse_args(argv)

    _load_env()

    if args.list_categories:
        for cat, subs in list_categories().items():
            print(f"{cat}: {'、'.join(subs)}")
        return 0

    if not args.image:
        parser.error("image is required (unless --list-categories)")

    print(f"[1/3] 提取产品特征: {args.image}")
    try:
        features = extract_features(args.image, model=args.model)
    except LLMError as e:
        print(f"特征提取失败: {e}", file=sys.stderr)
        return 1
    print(f"  → category={features.get('category')} sub_category={features.get('sub_category')}")
    caption = features.get("dense_caption", "")
    print(f"  → dense_caption={caption[:80]}{'...' if len(caption) > 80 else ''}")

    print("[2/3] 匹配分镜模版")
    template = match_template(
        features.get("category", ""), features.get("sub_category") or None
    )
    if not template:
        print(
            f"未匹配到模版: category={features.get('category')}",
            file=sys.stderr,
        )
        return 1
    print(f"  → {template.get('template_name')} ({template.get('template_id')})")

    print("[3/3] 生成分镜提示词")
    prompt = build_prompt(features.get("dense_caption", ""), template)

    print("\n" + "=" * 60)
    print(prompt)
    print("=" * 60)

    if args.output:
        Path(args.output).write_text(prompt, encoding="utf-8")
        print(f"\n已写入: {args.output}")
        feat_path = Path(args.output).with_suffix(".features.json")
        feat_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"特征已写入: {feat_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
