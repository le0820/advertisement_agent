"""Three-category base-template lookup and legacy prompt assembly.

Taxonomy and subcategory requirements come from category profiles. Templates
provide only three pacing references and cannot override proof or claim rules.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .category_profiles import (
    build_category_requirements,
    build_taxonomy,
    list_category_taxonomy,
    normalize_primary_category,
    normalize_subcategory,
)

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
        category: 三大一级类目或可迁移的旧别名。
        sub_category: 预留子类或旧子类别名。
    """
    canonical_category = normalize_primary_category(category)
    canonical_subcategory = normalize_subcategory(canonical_category, sub_category)
    cat_templates = _load_templates().get(canonical_category, [])
    if not cat_templates:
        return None
    selected = None
    if canonical_subcategory:
        for t in cat_templates:
            if t.get("sub_category") == canonical_subcategory:
                selected = t
                break
    if selected is None:
        selected = cat_templates[0]

    result = copy.deepcopy(selected)
    taxonomy = build_taxonomy(canonical_category, canonical_subcategory)
    result["resolved_taxonomy"] = taxonomy
    result["category_profile"] = build_category_requirements({
        "taxonomy": taxonomy,
        "category": canonical_category,
        "sub_category": canonical_subcategory,
    })
    return result


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
    """List the profile registry, independent of template count."""
    return list_category_taxonomy()
