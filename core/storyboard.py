"""分镜模版检索 + 提示词组装。

工作流:
  产品图 → extract_features(多模态) → match_template(类目)
        → build_prompt(caption, template) → 分镜提示词
        → 人工上传小云雀生成广告视频
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TEMPLATES_PATH = (
    Path(__file__).resolve().parent.parent / "templates" / "storyboard_templates.json"
)


def _load_templates() -> dict[str, list[dict[str, Any]]]:
    with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def match_template(
    category: str,
    sub_category: str | None = None,
) -> dict[str, Any] | None:
    """根据类目检索分镜模版。未匹配返回 None。

    Args:
        category: 一级类目，如 "珠宝饰品" / "消费电子" / "汽车出行"。
        sub_category: 二级类目，不传或未命中则返回该类目第一个模版。
    """
    cat_templates = _load_templates().get(category, [])
    if not cat_templates:
        return None
    if sub_category:
        for t in cat_templates:
            if t.get("sub_category") == sub_category:
                return t
    return cat_templates[0]


def build_prompt(dense_caption: str, template: dict[str, Any]) -> str:
    """组装分镜提示词 (system + scenes + rules + dense_caption)。

    Args:
        dense_caption: 多模态模型根据产品实拍图输出的详细描述。
        template: match_template() 返回的模版 dict。
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
        parts.append(guide)

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
    """列出所有一级类目及其二级子类。"""
    templates = _load_templates()
    return {
        cat: [t.get("sub_category", "") for t in items]
        for cat, items in templates.items()
    }
