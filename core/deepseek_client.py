"""DeepSeek chat completions client (OpenAI 兼容)。

通过 https://api.deepseek.com/chat/completions 调用 deepseek-v4-pro，
默认开启 thinking + high reasoning_effort，用于把分镜模版 + 产品特征
渲染成可直接粘贴到视频生成应用的完整提示词。

API key 从环境变量 DEEPSEEK_API_KEY 读取，绝不硬编码。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEEPSEEK_API_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-pro"


class DeepSeekError(RuntimeError):
    """DeepSeek 调用或解析异常。"""


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    api_key: str | None = None,
    thinking: bool = True,
    reasoning_effort: str = "high",
    timeout: float = 180.0,
) -> str:
    """调用 DeepSeek chat completions，返回 assistant 文本。

    Args:
        messages: [{role, content}, ...]，至少含 system + user。
        model: 模型名，默认 deepseek-v4-pro。
        api_key: DeepSeek API key，默认读环境变量 DEEPSEEK_API_KEY。
        thinking: 是否开启 thinking。
        reasoning_effort: 推理强度 low/medium/high。
        timeout: HTTP 超时秒数。
    """
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise DeepSeekError("DEEPSEEK_API_KEY not set; put it in .env")

    payload: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
    }
    if thinking:
        payload["thinking"] = {"type": "enabled"}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort

    req = urllib.request.Request(
        DEEPSEEK_API_ENDPOINT,
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
        raise DeepSeekError(f"DeepSeek HTTP {e.code}: {detail[:500]}") from e

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise DeepSeekError(
            "cannot parse DeepSeek response: "
            + json.dumps(body, ensure_ascii=False)[:500]
        ) from e
