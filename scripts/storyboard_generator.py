"""分镜脚本模版检索 + LLM prompt 组装。

工作流位置:
  产品实拍图 → 多模态 dense_caption → 本模块 match_template(类目) → build_prompt(caption, template)
  → LLM 生成分镜描述 → 产品图 + 分镜提示词 → 小云雀画布生成广告视频

用法:
  from upstream_data.scripts.storyboard_generator import match_template, build_prompt

  template = match_template("珠宝饰品", "求婚钻戒")
  prompt = build_prompt(dense_caption, template)
  # 把 prompt 发给 LLM，LLM 输出分镜脚本
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TEMPLATES_PATH = Path(__file__).resolve().parent / "storyboard_templates.json"


def _load_templates() -> dict[str, list[dict[str, Any]]]:
    with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def match_template(
    category: str,
    sub_category: str | None = None,
) -> dict[str, Any] | None:
    """根据类目检索分镜模版。

    Args:
        category: 一级类目，如 "珠宝饰品" / "消费电子" / "汽车出行"
        sub_category: 二级类目，如 "求婚钻戒" / "运动相机"。不传则返回该类目第一个模版。

    Returns:
        模版 dict，包含 system / scenes / rules 字段。未匹配返回 None。
    """
    templates = _load_templates()
    cat_templates = templates.get(category, [])
    if not cat_templates:
        return None

    if sub_category:
        for t in cat_templates:
            if t.get("sub_category") == sub_category:
                return t

    return cat_templates[0]


def build_prompt(
    dense_caption: str,
    template: dict[str, Any],
) -> str:
    """组装完整的 LLM prompt。

    将模版的 system 指令 + scenes 结构 + rules 规则 + dense_caption 拼成 LLM 可执行的 prompt。

    Args:
        dense_caption: 多模态模型根据产品实拍图输出的详细描述文本
        template: match_template() 返回的模版 dict

    Returns:
        可直接发给 LLM 的完整 prompt 字符串
    """
    system = template.get("system", "")
    scenes = template.get("scenes", [])
    rules = template.get("rules", [])
    template_name = template.get("template_name", "")

    parts = [system]

    if template_name:
        parts.append(f"\n广告风格参考: {template_name}")

    parts.append("\n## 产品信息 (dense_caption)")
    parts.append(dense_caption.strip())

    parts.append("\n## 分镜结构要求")
    for sc in scenes:
        scene_id = sc.get("scene", "?")
        name = sc.get("name", "")
        duration = sc.get("duration", 0)
        guide = sc.get("guide", "")
        parts.append(f"\n第{scene_id}场 [{name}] ({duration}秒)")
        parts.append(f"{guide}")

    if rules:
        parts.append("\n## 硬性规则")
        for i, rule in enumerate(rules, 1):
            parts.append(f"{i}. {rule}")

    parts.append("\n## 输出格式")
    parts.append(
        "按镜头编号输出，每镜头格式: "
        "编号 | 时长 | 景别 | 画面描述 | 运镜 | 光线 | 产品展示方式"
    )
    parts.append(
        "画面描述中融入产品在场景光影中的自然反光效果，"
        "产品外观严格依据dense_caption不得自编。"
    )

    return "\n".join(parts)


def list_categories() -> dict[str, list[str]]:
    """列出所有可用的一级类目及其二级子类。"""
    templates = _load_templates()
    result = {}
    for cat, tmpls in templates.items():
        result[cat] = [t.get("sub_category", "") for t in tmpls]
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python storyboard_generator.py list")
        print("  python storyboard_generator.py match <category> [sub_category]")
        print("  python storyboard_generator.py prompt <category> <sub_category> <caption_file>")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        cats = list_categories()
        print(json.dumps(cats, ensure_ascii=False, indent=2))

    elif cmd == "match":
        cat = sys.argv[2]
        sub = sys.argv[3] if len(sys.argv) > 3 else None
        t = match_template(cat, sub)
        if t:
            print(json.dumps({
                "template_id": t["template_id"],
                "template_name": t["template_name"],
                "category": t["category"],
                "sub_category": t["sub_category"],
                "duration": t["duration"],
                "scene_count": len(t["scenes"]),
            }, ensure_ascii=False, indent=2))
        else:
            print("未匹配到模版")

    elif cmd == "prompt":
        cat = sys.argv[2]
        sub = sys.argv[3]
        caption_file = sys.argv[4]
        t = match_template(cat, sub)
        if not t:
            print("未匹配到模版")
            sys.exit(1)
        with open(caption_file, "r", encoding="utf-8") as f:
            caption = f.read()
        prompt = build_prompt(caption, t)
        print(prompt)
