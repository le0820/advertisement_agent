"""结合产品特征 + 分镜模版，调用 DeepSeek 生成可直接粘贴的完整分镜提示词。

工作流位置:
  extract_features(多模态) → match_template → build_prompt(scaffold)
    → generate_final_prompt(本模块, DeepSeek) → 可粘贴到视频生成应用的成品提示词
"""

from __future__ import annotations

from typing import Any

from .deepseek_client import DeepSeekError, chat
from .storyboard import build_prompt

_SYSTEM = (
    "你是资深广告分镜脚本撰写师。根据给定的产品营销信息与分镜模版指令，"
    "生成一段可以直接粘贴到视频生成应用中使用的完整分镜提示词。\n"
    "要求：\n"
    "- 严格依据产品 dense_caption 描述外观，禁止编造材质/颜色/纹理\n"
    "- 每个镜头给出具体画面描述、运镜轨迹、光线设计、产品展示方式\n"
    "- 自然融入商品名称、卖点、目标人群的营销意图\n"
    "- 输出纯文本分镜脚本，不要 markdown 代码块，不要额外解释"
)


def _build_user(features: dict[str, Any], template: dict[str, Any], scaffold: str) -> str:
    selling_points = features.get("selling_points", [])
    sp = "、".join(selling_points) if isinstance(selling_points, list) else str(selling_points)
    scenarios = features.get("distribution_scenarios", [])
    parts = [
        "## 产品营销信息",
        f"商品名称: {features.get('product_name', '') or '（待补充）'}",
        f"卖点: {sp or '（待补充）'}",
        f"目标人群: {features.get('target_audience', '') or '（待补充）'}",
        f"传播场景: {', '.join(scenarios) if scenarios else 'douyin, tiktok, youtube'}",
        f"匹配模版: {template.get('template_name', '')} ({template.get('template_id', '')})",
        "",
        "## 分镜模版指令 + 产品视觉描述 (dense_caption)",
        scaffold,
    ]
    return "\n".join(parts)


def generate_final_prompt(
    features: dict[str, Any],
    template: dict[str, Any],
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """生成可直接粘贴到视频生成应用的完整分镜提示词。

    Args:
        features: extract_features() 返回的特征 dict。
        template: match_template() 返回的模版 dict。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。
    """
    scaffold = build_prompt(features.get("dense_caption", ""), template)
    user = _build_user(features, template, scaffold)
    return chat(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        model=model,
        api_key=api_key,
    )
