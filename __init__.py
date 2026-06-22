"""上游数据源系统 (二期+三期).

负责上游数据源的采集、结构化入库、AI改写倍增和输出。
与现有 Stage1/2/3 pipeline 解耦，仅输出标准文件供下游消费。

二期: 常规剧本 (成语/古诗/神话/历史/戏曲/图像种子 → 小说 .txt)
三期: 广告脚本 (品牌画像种子 → 分镜脚本 JSONL)

参见:
  - docs/superpowers/specs/2026-06-16-upstream-data-source-system-design.md
  - 三期 广告脚本_品牌故事分镜头数据采购需求说明书.pdf
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.2.0"
