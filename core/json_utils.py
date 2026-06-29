"""DeepSeek JSON 调用 + 容错解析工具。

所有需要结构化输出的创意模块都通过本模块调用 DeepSeek 并解析 JSON，
统一处理代码块围栏、前后散文、非法 JSON 等异常。
"""

from __future__ import annotations

import json
import re
from typing import Any

from .deepseek_client import DeepSeekError, chat


class JSONParseError(DeepSeekError):
    """LLM 输出无法解析为期望的 JSON。"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text


def parse_json_object(text: str) -> dict[str, Any]:
    """从 LLM 文本中提取首个 JSON 对象。

    容忍 markdown 代码块围栏与前后多余散文；非 dict 抛 JSONParseError。
    """
    cleaned = _strip_fences(text)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        raise JSONParseError(f"no JSON object in LLM output: {cleaned[:300]}")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise JSONParseError(f"invalid JSON object: {e}; raw={cleaned[:300]}") from e
    if not isinstance(obj, dict):
        raise JSONParseError(f"expected JSON object, got {type(obj).__name__}")
    return obj


def parse_json_array(text: str) -> list[Any]:
    """从 LLM 文本中提取首个 JSON 数组。"""
    cleaned = _strip_fences(text)
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not m:
        raise JSONParseError(f"no JSON array in LLM output: {cleaned[:300]}")
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise JSONParseError(f"invalid JSON array: {e}; raw={cleaned[:300]}") from e
    if not isinstance(arr, list):
        raise JSONParseError(f"expected JSON array, got {type(arr).__name__}")
    return arr


def chat_json_object(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """调用 DeepSeek 并解析为 JSON 对象。"""
    text = chat(messages, model=model, api_key=api_key)
    return parse_json_object(text)


def chat_json_array(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> list[Any]:
    """调用 DeepSeek 并解析为 JSON 数组。"""
    text = chat(messages, model=model, api_key=api_key)
    return parse_json_array(text)
