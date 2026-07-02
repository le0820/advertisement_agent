"""产品图片 → 特征提取。

调用多模态 LLM，按提取提示词模版输出 {category, sub_category, dense_caption}，
随后供 storyboard 模块匹配模版并生成分镜提示词。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .llm_client import LLMError, chat_with_image

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "extract_features.txt"
)
_TEMPLATES_PATH = (
    Path(__file__).resolve().parent.parent / "templates" / "storyboard_templates.json"
)

_FASHION_CATEGORY = "服装鞋包"
_JEWELRY_CATEGORY = "珠宝饰品"

_FASHION_KEYWORDS = (
    "西装", "西服", "礼服", "婚纱", "裙", "旗袍", "外套", "衬衫", "面料",
    "版型", "袖口", "肩线", "收腰", "高定", "高级定制", "成衣", "裤装",
    "大衣", "夹克", "连衣裙", "鞋履", "高跟鞋", "手袋", "箱包", "包袋",
    "刺绣礼服", "礼服西装", "钉珠", "金绣",
)
_JEWELRY_PRODUCT_KEYWORDS = (
    "戒指", "对戒", "钻戒", "戒托", "项链", "吊坠", "耳环", "耳饰",
    "手镯", "手链", "胸针", "珠宝", "首饰", "宝石", "钻石", "蓝宝石",
)
_FASHION_SUB_CATEGORY_RULES = (
    ("高定礼服", ("高定", "高级定制", "礼服西装", "重工刺绣", "刺绣礼服", "钉珠", "金绣")),
    ("婚礼礼服", ("婚纱", "婚礼", "新娘", "敬酒服", "拖尾")),
    ("晚宴礼服", ("晚宴", "舞会", "红毯", "宴会", "礼服")),
    ("男士西装", ("西装", "西服", "套装", "枪驳领", "戗驳领", "领口")),
    ("旗袍 / 中式礼服", ("旗袍", "中式礼服", "马面裙", "秀禾", "褂裙")),
    ("女装连衣裙", ("连衣裙", "女装", "裙")),
    ("鞋履", ("鞋履", "鞋", "靴", "高跟鞋", "运动鞋", "乐福鞋")),
    ("箱包", ("箱包", "手袋", "包袋", "托特", "背包", "手包")),
)


def _load_categories_block() -> str:
    """从 storyboard_templates.json 读取类目体系，拼成提示词用的文本块。"""
    with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
        templates = json.load(f)
    lines = []
    for cat, items in templates.items():
        if cat.startswith("_"):
            continue
        subs = [it.get("sub_category", "") for it in items if it.get("sub_category")]
        lines.append(f"- {cat}：{'、'.join(subs)}" if subs else f"- {cat}")
    return "\n".join(lines)


def _build_prompt() -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{categories_block}", _load_categories_block())


def _parse_json(text: str) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON 对象，容忍前后多余文本和代码块围栏。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise LLMError(f"no JSON object in LLM output: {text[:300]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON from LLM: {e}; raw={text[:300]}") from e


def _infer_fashion_sub_category(text: str) -> str:
    for sub_category, keywords in _FASHION_SUB_CATEGORY_RULES:
        if any(k in text for k in keywords):
            return sub_category
    return "高定礼服"


def _fashion_keywords_in(text: str) -> list[str]:
    return [k for k in _FASHION_KEYWORDS if k in text]


def _apply_category_guardrails(features: dict[str, Any]) -> None:
    """纠正服装商品被刺绣/宝石词误吸到珠宝类目的情况。"""
    product_name = str(features.get("product_name", ""))
    dense_caption = str(features.get("dense_caption", ""))
    sub_category = str(features.get("sub_category", ""))
    text = f"{product_name} {sub_category} {dense_caption}"
    fashion_hits = _fashion_keywords_in(text)
    if not fashion_hits:
        return

    product_name_has_fashion = bool(_fashion_keywords_in(product_name))
    product_name_has_jewelry = any(k in product_name for k in _JEWELRY_PRODUCT_KEYWORDS)
    category = str(features.get("category", ""))

    if category == _FASHION_CATEGORY:
        if not sub_category:
            features["sub_category"] = _infer_fashion_sub_category(text)
        return

    if category == _JEWELRY_CATEGORY and product_name_has_jewelry and not product_name_has_fashion:
        return

    if category == _JEWELRY_CATEGORY or product_name_has_fashion:
        features["category_conflict"] = {
            "original_category": category,
            "corrected_category": _FASHION_CATEGORY,
            "reason": "检测到服装/礼服/版型关键词，避免被刺绣、钉珠或金属光泽误归入珠宝饰品。",
            "matched_keywords": fashion_hits,
        }
        features["category"] = _FASHION_CATEGORY
        features["sub_category"] = _infer_fashion_sub_category(text)


def extract_features(
    image: str | Path,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """提取产品特征。

    Args:
        image: 本地图片路径或 http(s) URL。
        model: ARK 模型名覆盖。
        api_key: ARK API key 覆盖。

    Returns:
        {"category", "sub_category", "dense_caption"}
    """
    prompt = _build_prompt()
    text = chat_with_image(image, prompt, model=model, api_key=api_key)
    features = _parse_json(text)
    for key in ("category", "sub_category", "product_name", "target_audience", "dense_caption"):
        features.setdefault(key, "")
    features.setdefault("selling_points", [])
    if not isinstance(features.get("selling_points"), list):
        features["selling_points"] = [str(features["selling_points"])]
    _apply_category_guardrails(features)
    # 传播场景写死（小云雀营销 skill 要求字段，后续按平台扩展）
    features["distribution_scenarios"] = ["douyin", "tiktok", "youtube"]
    return features
