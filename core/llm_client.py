"""火山方舟 ARK Doubao 多模态 client (Responses API)。

通过 https://ark.cn-beijing.volces.com/api/v3/responses 调用 doubao-seed
多模态模型，支持图片 URL 和本地图片 (base64 data URL)。

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

ARK_API_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/responses"
DEFAULT_MODEL = "doubao-seed-2-0-lite-260428"


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
    timeout: float = 60.0,
) -> str:
    """发送图片+文本到 ARK 多模态模型，返回模型文本输出。

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
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_url},
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        ARK_API_ENDPOINT,
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
