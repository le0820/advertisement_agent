"""广告分镜提示词生成 CLI。

流程:
  python main.py <产品图路径|URL> [-o 输出文件]

  1. 多模态 LLM 提取产品特征 (Doubao: category/商品名称/卖点/目标人群/dense_caption)
  2. 按 category 匹配分镜模版
  3. DeepSeek 结合 caption + 模版生成可直接粘贴的完整分镜提示词
  4. 写出 .txt (成品提示词) + .features.json (含传播场景等 4 字段)

默认输出到 data/ 目录，文件名与输入图片同名 (换扩展名)：
  product.jpg → data/product.txt + data/product.features.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from core.deepseek_client import DeepSeekError
from core.extract_features import extract_features
from core.generate_prompt import generate_final_prompt
from core.llm_client import LLMError
from core.storyboard import list_categories, match_template


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


def _derive_output_path(image: str, override: str | None) -> Path:
    """根据输入图片名推导输出路径；override 非空时直接用。"""
    if override:
        return Path(override)
    if image.startswith("http://") or image.startswith("https://"):
        name = Path(urlparse(image).path).name
    else:
        name = Path(image).name
    stem = Path(name).stem or "output"
    return Path("data") / f"{stem}.txt"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="产品图 → 分镜提示词 (供小云雀人工测试)"
    )
    parser.add_argument("image", nargs="?", help="产品样例图本地路径或 URL")
    parser.add_argument(
        "-o", "--output", default=None, help="输出文件路径覆盖 (默认 data/<图片名>.txt)"
    )
    parser.add_argument(
        "--list-categories", action="store_true", help="列出可用类目体系后退出"
    )
    parser.add_argument("--ark-model", default=None, help="ARK Doubao 模型名覆盖")
    parser.add_argument("--deepseek-model", default=None, help="DeepSeek 模型名覆盖")
    args = parser.parse_args(argv)

    _load_env()

    if args.list_categories:
        for cat, subs in list_categories().items():
            print(f"{cat}: {'、'.join(subs)}")
        return 0

    if not args.image:
        parser.error("image is required (unless --list-categories)")

    print(f"[1/3] 提取产品特征 (Doubao 多模态): {args.image}")
    try:
        features = extract_features(args.image, model=args.ark_model)
    except LLMError as e:
        print(f"特征提取失败: {e}", file=sys.stderr)
        return 1
    print(f"  → 商品名称={features.get('product_name')}")
    print(f"  → category={features.get('category')} sub_category={features.get('sub_category')}")
    print(f"  → 目标人群={features.get('target_audience')}")
    print(f"  → 卖点={features.get('selling_points')}")
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

    print("[3/3] 生成完整分镜提示词 (DeepSeek)")
    try:
        prompt = generate_final_prompt(
            features, template, model=args.deepseek_model
        )
    except DeepSeekError as e:
        print(f"提示词生成失败: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 60)
    print(prompt)
    print("=" * 60)

    output_path = _derive_output_path(args.image, args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")
    print(f"\n分镜提示词已写入: {output_path}")

    feat_path = output_path.with_suffix(".features.json")
    feat_path.write_text(
        json.dumps(features, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"产品特征已写入: {feat_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
