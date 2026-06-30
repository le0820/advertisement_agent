"""火山方舟 ARK Doubao client。

特征提取 (chat_with_image): chat/completions 端点 + 多模态 (image+text)。
评分裁判 (chat_text):       responses 端点 + 纯文本。
DeepSeek 调用: 见 deepseek_client.py。

API key 从环境变量 ARK_API_KEY 读取，绝不硬编码。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path

ARK_RESPONSES_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/responses"
ARK_CHAT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# 特征提取 (chat/completions 多模态)
DEFAULT_MODEL = "doubao-seed-2-0-lite-260428"
# 评分裁判 (responses 纯文本)
ARK_SCORE_DEFAULT_MODEL = "doubao-seed-2-1-turbo-260628"


class LLMError(RuntimeError):
    """LLM 调用或解析异常。"""


def _load_image_as_data_url(image: str | Path) -> str:
    """本地图片转 base64 data URL；http(s) URL 原样返回。"""
    image = str(image)
    if image.startswith("http://") or image.startswith("https://"):
        return image
    path = Path(image)
    if not path.exists():
        raise LLMError(f"image not found: {path}")
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_text(resp: dict) -> str:
    """从 ARK responses 返回体中提取文本，兼容多种结构。"""
    for item in resp.get("output", []) or []:
        if item.get("type") == "message" or item.get("role") == "assistant":
            for block in item.get("content", []) or []:
                text = block.get("text") or ""
                if text:
                    return text
    if resp.get("output_text"):
        return resp["output_text"]
    raise LLMError(
        "cannot parse LLM response: "
        + json.dumps(resp, ensure_ascii=False)[:500]
    )


def chat_with_image(
    image: str | Path,
    prompt: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 180.0,
) -> str:
    """发送图片+文本到 ARK chat/completions 端点，返回模型文本输出。

    Args:
        image: 本地图片路径或 http(s) URL。
        prompt: 文本指令。
        model: ARK 模型名，默认 doubao-seed-2-0-lite-260428。
        api_key: ARK API key，默认读环境变量 ARK_API_KEY。
        timeout: HTTP 超时秒数。
    """
    key = api_key or os.environ.get("ARK_API_KEY")
    if not key:
        raise LLMError("ARK_API_KEY not set; put it in .env or env var")

    image_url = _load_image_as_data_url(image)
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        ARK_CHAT_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise LLMError(f"ARK API HTTP {e.code}: {detail[:500]}") from e

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(
            "cannot parse ARK chat response: "
            + json.dumps(body, ensure_ascii=False)[:500]
        ) from e


def chat_text(
    prompt: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 600.0,
) -> str:
    """发送纯文本到 ARK responses 端点 (裁判模型)，返回模型文本输出。

    Args:
        prompt: 文本指令。
        model: ARK 模型名，默认 doubao-seed-2-1-turbo-260628。
        api_key: ARK API key，默认读环境变量 ARK_API_KEY。
        timeout: HTTP 超时秒数。
    """
    key = api_key or os.environ.get("ARK_API_KEY")
    if not key:
        raise LLMError("ARK_API_KEY not set; put it in .env or env var")

    payload = {
        "model": model or ARK_SCORE_DEFAULT_MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        ARK_RESPONSES_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise LLMError(f"ARK API HTTP {e.code}: {detail[:500]}") from e
    return _extract_text(body)
