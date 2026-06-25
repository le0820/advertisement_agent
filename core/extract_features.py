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
    for key in ("category", "sub_category", "dense_caption"):
        features.setdefault(key, "")
    return features
