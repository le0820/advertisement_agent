"""品牌种子入库管道 (三期广告脚本)。

数据源: 结构化 JSON 品牌画像文件，每个品牌为一个对象。
分类体系: 京东/淘宝/申万行业合并 → 20 个一级类目，每个类目下扩充二级子类。
所有品牌名均为虚构，不引用任何市场已有品牌，确保零侵权风险。

业务链路:
  商品图片 → 视觉分类(确定 category + sub_category) → 匹配分镜模版 → 填充品牌画像 → 渲染广告脚本

JSON 字段说明 (数组 or 单对象):
  [{
    "brand_name":       "都市夜行者",            # 虚构品牌名
    "brand_category":   "运动户外",              # 一级类目 (20选1)
    "sub_category":     "智能跑鞋",              # 二级类目/产品子类型 (可选)
    "target_audience":  "22-35岁都市夜跑爱好者", # 目标人群画像
    "tone_style":       ["科技感","赛博朋克"],    # 广告调性
    "aspect_ratio":     "9:16",                  # 画幅比例 9:16/16:9/1:1
    "total_duration":   15.0,                    # 建议广告时长(秒)
    "product_type":     "智能缓震跑鞋",          # 具体产品
    "product_description": "足底传感器…",        # 产品功能描述
    "key_message":      "在夜色里跑出自己的节奏", # 核心广告语/slogan
    "visual_setting":   "霓虹街道,湿滑路面",     # 视觉场景
    "visual_mood":      "前沿、动感、未来感",    # 视觉情绪
    "brand_personality":["科技玩家","独立"],     # 品牌人格
    "use_case":         "夜跑训练,马拉松备赛",   # 使用场景
    "seasons":          ["全年"],                # 适用季节
    "color_palette":    ["深蓝","荧光绿","黑色"]  # 配色方案
  }]

入库产出:
  - seeds (seed_type='brand'): raw_content 存完整品牌画像 JSON
  - tags 字段: 品牌,{category},{tone_style},{personality}
  - 不产出 decision_points / seed_characters (品牌种子是画像级素材，非叙事级)

幂等: seed_id = "brand_{md5(name|category)[:10]}" 稳定哈希，重复运行 UPDATE。

下游对接:
  - 分镜模版匹配 → upstream_data/scripts/storyboard_templates.json
  - 脚本生成器   → upstream_data/scripts/storyboard_generator.py
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ..db.seed_db import SeedRecord
from .base import BaseIngestor


def _read_text_auto(file_path: Path) -> str:
    import codecs
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            with codecs.open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(file_path, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def _brand_seed_id(brand_name: str, brand_category: str) -> str:
    raw = f"{brand_name}|{brand_category}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]
    return f"brand_{digest}"


class BrandIngestor(BaseIngestor):
    name = "ingest_brands"
    seed_type = "brand"

    def _iter_records(self, source_path: Path) -> Iterator[dict[str, Any]]:
        text = _read_text_auto(source_path).strip()
        if not text:
            return
        data = json.loads(text)
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            brand_name = (item.get("brand_name") or "").strip()
            if not brand_name:
                continue
            yield item

    def _record_to_seed(
        self, record: dict[str, Any], index: int
    ) -> tuple[SeedRecord, list[Any], list[Any]]:
        brand_name = (record.get("brand_name") or "").strip()
        brand_category = (record.get("brand_category") or "").strip()
        sub_category = (record.get("sub_category") or "").strip()

        seed_id = _brand_seed_id(brand_name, brand_category)

        tone_style = record.get("tone_style", [])
        tone_style_str = ",".join(tone_style) if isinstance(tone_style, list) else str(tone_style)

        brand_personality = record.get("brand_personality", [])
        personality_str = ",".join(brand_personality) if isinstance(brand_personality, list) else str(brand_personality)

        visual_mood = (record.get("visual_mood") or "").strip()

        raw_content = json.dumps(record, ensure_ascii=False)

        tag_parts = ["品牌", brand_category]
        if sub_category:
            tag_parts.append(sub_category)
        tag_parts.append(tone_style_str)
        tag_parts.append(personality_str)

        seed = SeedRecord(
            seed_id=seed_id,
            seed_type="brand",
            title=brand_name,
            raw_content=raw_content,
            mood=visual_mood,
            tags=",".join(tag_parts),
        )
        return seed, [], []


def ingest(source_path: str | Path, *, db_path: str | Path | None = None) -> dict[str, Any]:
    """CLI 直调入口，返回 IngestResult.to_dict()。"""
    ingestor = BrandIngestor(db_path=db_path)
    return ingestor.ingest(source_path).to_dict()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest brand seeds into seed_db.")
    parser.add_argument("source", help="Brand JSON file (array of brand profiles)")
    parser.add_argument("--db", default=None, help="seed_db.sqlite path override")
    args = parser.parse_args()
    result = ingest(args.source, db_path=args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
