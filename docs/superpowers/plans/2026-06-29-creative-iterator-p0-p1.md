# Creative Iterator (P0 + P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the linear "image → features → template → prompt" pipeline into a low-cost creative iterator that generates 8 creative candidates, scores them, shortlists, and recommends the single one most worth spending a 小云雀/Seedance video credit on — without removing the original fast path.

**Architecture:** Insert `brief → creative_search → creative_scoring → shortlist → render_decision → output_package` between feature extraction and the final prompt. Every step writes a debuggable JSON artifact to `data/<stem>.*.json`. All new modules live under `core/`, reuse the existing DeepSeek client, and add **zero** external dependencies (stdlib only). `brief` is rule-based (deterministic); `creative_search`/`creative_scoring`/`render_decision`/`output_package` call DeepSeek and parse JSON defensively; `shortlist` is pure rule-based logic (the P1 core value). `storyboard_simulator` is included as a minimal real module invoked only via `--storyboard` (P2 will enhance it; default off to keep decision mode cheap).

**Tech Stack:** Python 3.9 stdlib (`urllib`, `json`, `re`, `argparse`, `pathlib`, `unittest`), existing ARK Doubao + DeepSeek clients.

**Scope (P0 + P1 only — per user):** brief, creative_search, creative_scoring, shortlist, render_decision, output_package, minimal storyboard_simulator, CLI `--mode {fast,explore,decision}`, all intermediate JSON + `.txt` + `.report.md`, smoke tests, README. **Deferred:** P2 storyboard polish, P3 report polish, P4 hotspot search / brand memory / feedback loop / web UI / auto-upload.

---

## Data Structure Contracts (canonical — all tasks must match these field names)

### creative_brief
```json
{
  "product_name": "", "category": "", "sub_category": "", "dense_caption": "",
  "selling_points": [], "target_audience": "", "distribution_scenarios": [],
  "brand_name": "",
  "brand_stage": "unknown|awareness|conversion|retargeting",
  "brand_assets": {"slogan": "", "tone": "", "visual_codes": [], "forbidden_claims": []},
  "commercial_goal": "brand_film|creative_ad|direct_response|social_post",
  "platform": "douyin|xiaohongshu|video_account|tiktok|youtube",
  "aspect_ratio": "9:16|16:9|1:1", "duration_seconds": 15,
  "constraints": {"must_show_product_by_second": 3, "must_have_cta": false,
                  "avoid_face_generation": false, "avoid_complex_hand_motion": false}
}
```

### creative_candidate
```json
{
  "candidate_id": "C001",
  "creative_route": "", "one_sentence_idea": "", "hook": "",
  "target_emotion": "", "audience_insight": "", "product_truth": "",
  "visual_metaphor": "", "narrative_spine": "",
  "shot_plan": [
    {"shot_id": "S01", "time_range": "0-3s",
     "purpose": "hook|product_reveal|proof|emotional_peak|brand_lock",
     "visual": "", "camera": "", "lighting": "", "sound": "",
     "copy_or_voiceover": "", "product_visibility": "none|partial|clear|hero"}
  ],
  "seedance_prompt_risk": {"risk_level": "low|medium|high", "risk_reasons": []}
}
```

### creative_score
```json
{
  "candidate_id": "C001",
  "scores": {
    "first_3_seconds_hook": 0, "product_clarity": 0, "brand_fit": 0,
    "audience_relevance": 0, "visual_memorability": 0, "platform_fit": 0,
    "seedance_feasibility": 0, "generation_risk_control": 0,
    "commercial_intent": 0, "overall": 0
  },
  "strengths": [], "weaknesses": [], "revision_suggestions": [],
  "render_recommendation": "reject|revise|shortlist|render"
}
```

### SCORE_WEIGHTS (lives in `core/creative_scoring.py`)
```
first_3_seconds_hook 0.15, product_clarity 0.15, brand_fit 0.10,
audience_relevance 0.10, visual_memorability 0.15, platform_fit 0.10,
seedance_feasibility 0.15, generation_risk_control 0.05, commercial_intent 0.05
```
`overall` is computed in code (weighted avg, 0–100, rounded to int), NOT by the LLM.

### shortlist item (output of `select_shortlist`)
```json
{
  "candidate_id": "C001",
  "candidate": {creative_candidate},
  "score": {creative_score},
  "overall": 0,
  "eligible_for_render": true,
  "ineligible_reasons": []
}
```

### render_decision
```json
{
  "recommended_candidate_id": "C001" , "should_render": true, "confidence": 0,
  "reason": "", "expected_failure_modes": [],
  "pre_render_checklist": [],
  "if_first_render_fails": {"likely_causes": [], "recommended_fix": "", "do_not_retry_if": []}
}
```

### output_package
```json
{
  "xiaoyunque_prompt": "", "summary": "",
  "creative_brief": {}, "selected_candidate": {}, "score": {},
  "storyboard_simulation": null, "render_decision": {},
  "manual_upload_notes": []
}
```

---

## File Structure

**Create:**
- `core/json_utils.py` — DeepSeek JSON call + defensive parse (shared by all LLM modules)
- `core/brief.py` — rule-based `build_creative_brief`
- `core/creative_search.py` — `generate_creative_candidates` (LLM, 8 candidates)
- `core/creative_scoring.py` — `score_creative_candidate` / `score_creative_candidates` (LLM + weighted overall)
- `core/shortlist.py` — `select_shortlist` (pure rules, P1 core)
- `core/storyboard_simulator.py` — `generate_storyboard_simulation` (minimal, LLM, opt-in)
- `core/render_decision.py` — `make_render_decision` (rule pick + LLM reasoning)
- `core/output_package.py` — `build_final_prompt_package` + `build_report_md`
- `prompts/generate_creative_candidates.txt`
- `prompts/score_creative_candidate.txt`
- `prompts/generate_storyboard_simulator.txt`
- `prompts/make_render_decision.txt`
- `prompts/build_final_prompt.txt`
- `schemas/creative_brief.schema.json`
- `schemas/creative_candidate.schema.json`
- `schemas/creative_score.schema.json`
- `schemas/storyboard_simulation.schema.json`
- `schemas/render_decision.schema.json`
- `tests/__init__.py` (empty)
- `tests/test_json_utils.py`
- `tests/test_brief.py`
- `tests/test_creative_search.py`
- `tests/test_creative_scoring.py`
- `tests/test_shortlist.py`
- `tests/test_storyboard_simulator.py`
- `tests/test_render_decision.py`
- `tests/test_output_package.py`
- `tests/test_cli.py`

**Modify:**
- `main.py` — add `--mode` + new flags, wire new pipeline, write all artifacts
- `README.md` — document new workflow, modes, files

---

## Task 1: JSON utils + schemas + test scaffold

**Files:**
- Create: `core/json_utils.py`, `tests/__init__.py`, `tests/test_json_utils.py`
- Create: `schemas/creative_brief.schema.json`, `schemas/creative_candidate.schema.json`, `schemas/creative_score.schema.json`, `schemas/storyboard_simulation.schema.json`, `schemas/render_decision.schema.json`

- [ ] **Step 1: Write the failing test for json_utils**

Create `tests/__init__.py` (empty file).

Create `tests/test_json_utils.py`:
```python
from __future__ import annotations
import unittest
from unittest.mock import patch

from core.json_utils import (
    JSONParseError,
    parse_json_array,
    parse_json_object,
    chat_json_array,
    chat_json_object,
)


class TestParseJsonObject(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

    def test_fenced_object(self):
        self.assertEqual(parse_json_object('```json\n{"a": 2}\n```'), {"a": 2})

    def test_prose_around_object(self):
        text = 'here is the result:\n{"x": "y", "z": [1,2]}\nthanks'
        self.assertEqual(parse_json_object(text), {"x": "y", "z": [1, 2]})

    def test_missing_object_raises(self):
        with self.assertRaises(JSONParseError):
            parse_json_object("no json here")

    def test_array_rejected_for_object(self):
        with self.assertRaises(JSONParseError):
            parse_json_object("[1, 2, 3]")


class TestParseJsonArray(unittest.TestCase):
    def test_plain_array(self):
        self.assertEqual(parse_json_array('[{"a": 1}, {"b": 2}]'), [{"a": 1}, {"b": 2}])

    def test_fenced_array(self):
        self.assertEqual(parse_json_array('```\n[1, 2, 3]\n```'), [1, 2, 3])

    def test_missing_array_raises(self):
        with self.assertRaises(JSONParseError):
            parse_json_array("no array")


class TestChatJson(unittest.TestCase):
    @patch("core.json_utils.chat", return_value='{"k": "v"}')
    def test_chat_json_object(self, _mock):
        self.assertEqual(chat_json_object([{"role": "user", "content": "x"}]), {"k": "v"})

    @patch("core.json_utils.chat", return_value='[{"id": 1}]')
    def test_chat_json_array(self, _mock):
        self.assertEqual(chat_json_array([{"role": "user", "content": "x"}]), [{"id": 1}])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_json_utils -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.json_utils'`

- [ ] **Step 3: Implement json_utils**

Create `core/json_utils.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_json_utils -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Create schema documentation files**

Create `schemas/creative_brief.schema.json`:
```json
{
  "$comment": "创意 brief 文档契约 (P0 仅作文档，不做强校验)。",
  "type": "object",
  "required": ["product_name", "category", "dense_caption", "selling_points",
               "target_audience", "commercial_goal", "platform", "aspect_ratio",
               "duration_seconds", "constraints"],
  "properties": {
    "product_name": {"type": "string"},
    "category": {"type": "string"},
    "sub_category": {"type": "string"},
    "dense_caption": {"type": "string"},
    "selling_points": {"type": "array", "items": {"type": "string"}},
    "target_audience": {"type": "string"},
    "distribution_scenarios": {"type": "array", "items": {"type": "string"}},
    "brand_name": {"type": "string"},
    "brand_stage": {"enum": ["unknown", "awareness", "conversion", "retargeting"]},
    "brand_assets": {"type": "object"},
    "commercial_goal": {"enum": ["brand_film", "creative_ad", "direct_response", "social_post"]},
    "platform": {"enum": ["douyin", "xiaohongshu", "video_account", "tiktok", "youtube"]},
    "aspect_ratio": {"enum": ["9:16", "16:9", "1:1"]},
    "duration_seconds": {"type": "integer"},
    "constraints": {"type": "object"}
  }
}
```

Create `schemas/creative_candidate.schema.json`:
```json
{
  "$comment": "创意候选文档契约。",
  "type": "object",
  "required": ["candidate_id", "creative_route", "one_sentence_idea", "hook",
               "shot_plan", "seedance_prompt_risk"],
  "properties": {
    "candidate_id": {"type": "string"},
    "creative_route": {"type": "string"},
    "one_sentence_idea": {"type": "string"},
    "hook": {"type": "string"},
    "target_emotion": {"type": "string"},
    "audience_insight": {"type": "string"},
    "product_truth": {"type": "string"},
    "visual_metaphor": {"type": "string"},
    "narrative_spine": {"type": "string"},
    "shot_plan": {"type": "array", "items": {"type": "object"}},
    "seedance_prompt_risk": {
      "type": "object",
      "required": ["risk_level", "risk_reasons"],
      "properties": {
        "risk_level": {"enum": ["low", "medium", "high"]},
        "risk_reasons": {"type": "array", "items": {"type": "string"}}
      }
    }
  }
}
```

Create `schemas/creative_score.schema.json`:
```json
{
  "$comment": "创意评分文档契约。overall 由代码加权计算，非 LLM 给出。",
  "type": "object",
  "required": ["candidate_id", "scores", "render_recommendation"],
  "properties": {
    "candidate_id": {"type": "string"},
    "scores": {
      "type": "object",
      "required": ["first_3_seconds_hook", "product_clarity", "brand_fit",
                   "audience_relevance", "visual_memorability", "platform_fit",
                   "seedance_feasibility", "generation_risk_control",
                   "commercial_intent", "overall"]
    },
    "strengths": {"type": "array", "items": {"type": "string"}},
    "weaknesses": {"type": "array", "items": {"type": "string"}},
    "revision_suggestions": {"type": "array", "items": {"type": "string"}},
    "render_recommendation": {"enum": ["reject", "revise", "shortlist", "render"]}
  }
}
```

Create `schemas/storyboard_simulation.schema.json`:
```json
{
  "$comment": "关键帧预演文档契约 (P2 增强目标，P0 仅最小实现)。",
  "type": "object",
  "required": ["candidate_id", "keyframes", "storyboard_review"],
  "properties": {
    "candidate_id": {"type": "string"},
    "keyframes": {"type": "array", "items": {"type": "object"}},
    "storyboard_review": {"type": "object"}
  }
}
```

Create `schemas/render_decision.schema.json`:
```json
{
  "$comment": "是否值得消耗一次视频积分的决策文档契约。",
  "type": "object",
  "required": ["recommended_candidate_id", "should_render", "reason",
               "pre_render_checklist", "if_first_render_fails"],
  "properties": {
    "recommended_candidate_id": {"type": ["string", "null"]},
    "should_render": {"type": "boolean"},
    "confidence": {"type": "integer"},
    "reason": {"type": "string"},
    "expected_failure_modes": {"type": "array", "items": {"type": "string"}},
    "pre_render_checklist": {"type": "array", "items": {"type": "string"}},
    "if_first_render_fails": {"type": "object"}
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add core/json_utils.py tests/__init__.py tests/test_json_utils.py schemas/
git commit -m "Add JSON utils + schema docs for creative iterator"
```

---

## Task 2: creative_brief (rule-based)

**Files:**
- Create: `core/brief.py`, `tests/test_brief.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_brief.py`:
```python
from __future__ import annotations
import unittest

from core.brief import build_creative_brief


def _features():
    return {
        "category": "珠宝饰品", "sub_category": "情侣对戒",
        "product_name": "错金浪纹对戒",
        "selling_points": ["独特浪纹设计", "蓝宝石主石"],
        "target_audience": "22-35岁情侣",
        "dense_caption": "宽版银白金属戒，错金浪纹，蓝宝石主石。",
        "distribution_scenarios": ["douyin", "tiktok", "youtube"],
    }


class TestBuildCreativeBrief(unittest.TestCase):
    def test_defaults_from_features(self):
        b = build_creative_brief(_features())
        self.assertEqual(b["product_name"], "错金浪纹对戒")
        self.assertEqual(b["category"], "珠宝饰品")
        self.assertEqual(b["selling_points"], ["独特浪纹设计", "蓝宝石主石"])
        self.assertEqual(b["platform"], "douyin")
        self.assertEqual(b["aspect_ratio"], "9:16")
        self.assertEqual(b["duration_seconds"], 15)
        self.assertEqual(b["commercial_goal"], "creative_ad")
        self.assertEqual(b["brand_stage"], "awareness")
        self.assertEqual(b["constraints"]["must_show_product_by_second"], 3)
        self.assertFalse(b["brand_assets"]["slogan"])

    def test_user_options_override(self):
        b = build_creative_brief(_features(), {
            "platform": "xiaohongshu", "aspect_ratio": "16:9",
            "duration": 30, "commercial_goal": "brand_film",
            "slogan": "每一针一线", "brand_name": "青雀",
        })
        self.assertEqual(b["platform"], "xiaohongshu")
        self.assertEqual(b["aspect_ratio"], "16:9")
        self.assertEqual(b["duration_seconds"], 30)
        self.assertEqual(b["commercial_goal"], "brand_film")
        self.assertEqual(b["brand_stage"], "awareness")
        self.assertEqual(b["brand_assets"]["slogan"], "每一针一线")
        self.assertEqual(b["brand_name"], "青雀")

    def test_sensitive_category_avoids_face(self):
        f = _features()
        b = build_creative_brief(f, {"commercial_goal": "brand_film"})
        self.assertTrue(b["constraints"]["avoid_face_generation"])

    def test_selling_points_string_coerced(self):
        f = _features()
        f["selling_points"] = "单一卖点"
        b = build_creative_brief(f)
        self.assertEqual(b["selling_points"], ["单一卖点"])

    def test_missing_distribution_defaults(self):
        f = _features()
        f.pop("distribution_scenarios")
        b = build_creative_brief(f)
        self.assertEqual(b["distribution_scenarios"], ["douyin", "tiktok", "youtube"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_brief -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.brief'`

- [ ] **Step 3: Implement brief.py**

Create `core/brief.py`:
```python
"""产品特征 → 广告创意 brief。

把 extract_features 的输出升级为结构化创意 brief：补充品牌阶段、商业目标、
平台、画幅、时长、约束等，供 creative_search / scoring 使用。
P0 为规则填充，不调用 LLM（保持低成本与确定性）。
"""

from __future__ import annotations

from typing import Any

_BRAND_STAGE_BY_GOAL = {
    "brand_film": "awareness",
    "creative_ad": "awareness",
    "direct_response": "conversion",
    "social_post": "retargeting",
}

_DEFAULT_DISTRIBUTION = ["douyin", "tiktok", "youtube"]

# 容易"过度美化"的类目，需要产品真实性约束 + 规避人脸生成
_SENSITIVE_CATEGORIES = {"珠宝饰品", "高定礼服", "美妆", "医美"}


def build_creative_brief(
    features: dict[str, Any],
    user_options: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """从产品特征派生广告创意 brief。

    Args:
        features: extract_features() 返回的特征 dict。
        user_options: CLI 可选项 (platform/aspect_ratio/duration/
            commercial_goal/slogan/brand_name/brand_stage/avoid_face/
            avoid_hand/must_have_cta)。未提供则用合理默认值，不捏造品牌资产。
        model: 预留参数，P0 不调用 LLM。

    Returns:
        creative_brief dict (见 schemas/creative_brief.schema.json)。
    """
    opts = user_options or {}
    sp = features.get("selling_points", [])
    if not isinstance(sp, list):
        sp = [str(sp)]
    scenarios = features.get("distribution_scenarios") or list(_DEFAULT_DISTRIBUTION)

    commercial_goal = opts.get("commercial_goal") or "creative_ad"
    brand_stage = opts.get("brand_stage") or _BRAND_STAGE_BY_GOAL.get(
        commercial_goal, "awareness"
    )
    category = features.get("category", "")
    sensitive = category in _SENSITIVE_CATEGORIES

    avoid_face = opts.get("avoid_face")
    if avoid_face is None:
        avoid_face = sensitive or commercial_goal == "brand_film"
    avoid_hand = opts.get("avoid_hand")
    if avoid_hand is None:
        avoid_hand = False

    return {
        "product_name": features.get("product_name", ""),
        "category": category,
        "sub_category": features.get("sub_category", "") or "",
        "dense_caption": features.get("dense_caption", ""),
        "selling_points": sp,
        "target_audience": features.get("target_audience", ""),
        "distribution_scenarios": scenarios,
        "brand_name": opts.get("brand_name", ""),
        "brand_stage": brand_stage,
        "brand_assets": {
            "slogan": opts.get("slogan", ""),
            "tone": "",
            "visual_codes": [],
            "forbidden_claims": [],
        },
        "commercial_goal": commercial_goal,
        "platform": opts.get("platform") or "douyin",
        "aspect_ratio": opts.get("aspect_ratio") or "9:16",
        "duration_seconds": int(opts.get("duration") or 15),
        "constraints": {
            "must_show_product_by_second": 3,
            "must_have_cta": bool(opts.get("must_have_cta", False)),
            "avoid_face_generation": bool(avoid_face),
            "avoid_complex_hand_motion": bool(avoid_hand),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_brief -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add core/brief.py tests/test_brief.py
git commit -m "Add rule-based creative brief builder"
```

---

## Task 3: creative_search (8 LLM candidates)

**Files:**
- Create: `prompts/generate_creative_candidates.txt`, `core/creative_search.py`, `tests/test_creative_search.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_creative_search.py`:
```python
from __future__ import annotations
import unittest
from unittest.mock import patch

from core.creative_search import generate_creative_candidates


_FAKE_LLM_OUTPUT = """
[
  {
    "creative_route": "品牌大片",
    "one_sentence_idea": "金线生长成铠甲",
    "hook": "微距绣针穿刺",
    "target_emotion": "震撼",
    "audience_insight": "渴望仪式感",
    "product_truth": "手工刺绣",
    "visual_metaphor": "金线蔓延",
    "narrative_spine": "针→线→纹→龙",
    "shot_plan": [{"shot_id": "S01", "time_range": "0-3s", "purpose": "hook",
                   "visual": "微距针穿刺", "camera": "慢推", "lighting": "侧逆光",
                   "sound": "落针声", "copy_or_voiceover": "",
                   "product_visibility": "partial"}],
    "seedance_prompt_risk": {"risk_level": "medium", "risk_reasons": ["手部细节"]}
  },
  {
    "creative_route": "产品感官特写",
    "one_sentence_idea": "材质舞蹈",
    "hook": "亮片闪烁",
    "target_emotion": "惊艳",
    "audience_insight": "看重工艺",
    "product_truth": "重工钉珠",
    "visual_metaphor": "亮片如星",
    "narrative_spine": "暗→光→绽放",
    "shot_plan": [],
    "seedance_prompt_risk": {"risk_level": "low", "risk_reasons": []}
  }
]
"""


class TestGenerateCreativeCandidates(unittest.TestCase):
    @patch("core.creative_search.chat_json_array",
           return_value=[c for c in __import__("json").loads(_FAKE_LLM_OUTPUT)])
    def test_generates_and_assigns_ids(self, _mock):
        brief = {"product_name": "礼服", "dense_caption": "刺绣礼服"}
        cands = generate_creative_candidates(brief, num_candidates=2)
        self.assertEqual(len(cands), 2)
        self.assertEqual(cands[0]["candidate_id"], "C001")
        self.assertEqual(cands[1]["candidate_id"], "C002")
        self.assertEqual(cands[0]["creative_route"], "品牌大片")
        self.assertIn("shot_plan", cands[0])
        self.assertIn("seedance_prompt_risk", cands[0])

    def test_missing_fields_filled(self):
        from core.creative_search import _normalize_candidate
        c = _normalize_candidate({"creative_route": "X"}, 1)
        self.assertEqual(c["candidate_id"], "C001")
        self.assertEqual(c["hook"], "")
        self.assertEqual(c["shot_plan"], [])
        self.assertEqual(c["seedance_prompt_risk"]["risk_level"], "medium")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_creative_search -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.creative_search'`

- [ ] **Step 3: Create the prompt template**

Create `prompts/generate_creative_candidates.txt`:
```text
你是资深广告创意总监。根据产品 brief 生成 {num_candidates} 个差异化的广告创意候选。

【产品 brief】
{brief_json}

【分镜模版参考 (可选)】
{template_block}

【创意路线 (每个候选必须选不同路线，覆盖尽量多种)】
- 品牌大片：奢侈品工艺神话，材质转化视觉诗
- 创意广告/剧情植入：用一段剧情自然带出产品
- 产品感官特写：纯材质/光影/微距感官大片
- 使用场景种草：真实使用场景里的产品高光
- 反差/幽默短片：出人意料的反差或幽默钩子
- 工艺/品质证明：把工艺过程可视化作为证据
- 节日/仪式感：绑定节日或人生仪式时刻
- 社交身份表达：用产品表达某种身份与态度

【每个候选输出字段】
- creative_route: 上面 8 种之一
- one_sentence_idea: 一句话创意
- hook: 前 3 秒具体钩子(画面+声音)
- target_emotion: 目标情绪
- audience_insight: 人群洞察(为什么在意)
- product_truth: 产品真实可见的特点
- visual_metaphor: 让卖点可视化的视觉隐喻
- narrative_spine: 整条片的叙事脊柱(运动/转场/升级)
- shot_plan: 3-6 个镜头, 每个含 shot_id/time_range/purpose/
  visual/camera/lighting/sound/copy_or_voiceover/product_visibility
  (purpose ∈ hook|product_reveal|proof|emotional_peak|brand_lock;
   product_visibility ∈ none|partial|clear|hero)
- seedance_prompt_risk: {{risk_level: low|medium|high, risk_reasons:[]}}
  重点排查: 复杂手部动作/多人交互/细小文字logo/真实人脸一致性/
  产品外观漂移/镜头过多/动作过复杂

【硬性要求】
- 产品外观必须严格依据 dense_caption, 不得改颜色/材质/结构
- 每个候选 shot_plan 的镜头总时长落在 brief.duration_seconds 附近
- 前 3 秒必须有强 hook, 产品在 must_show_product_by_second 秒前出现
- 输出纯 JSON 数组, 不要 markdown 代码块, 不要解释, 不要包在外层对象里
```

- [ ] **Step 4: Implement creative_search.py**

Create `core/creative_search.py`:
```python
"""creative_brief → 多个差异化创意候选 (LLM, JSON 数组)。

生成 num_candidates 个不同 creative_route 的结构化候选，供 scoring 评分。
候选不是最终 prompt；代码负责分配 candidate_id 并补齐缺失字段。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import chat_json_array

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "generate_creative_candidates.txt"
)

_REQUIRED_FIELDS = (
    "creative_route", "one_sentence_idea", "hook", "target_emotion",
    "audience_insight", "product_truth", "visual_metaphor", "narrative_spine",
    "shot_plan", "seedance_prompt_risk",
)


def _normalize_candidate(raw: dict[str, Any], index: int) -> dict[str, Any]:
    """补齐缺失字段并分配 candidate_id (C001, C002, ...)。"""
    cand: dict[str, Any] = {"candidate_id": f"C{index:03d}"}
    for f in _REQUIRED_FIELDS:
        cand[f] = raw.get(f, "" if f != "shot_plan" else [])
    if not isinstance(cand["shot_plan"], list):
        cand["shot_plan"] = []
    risk = cand.get("seedance_prompt_risk") or {}
    if not isinstance(risk, dict):
        risk = {}
    cand["seedance_prompt_risk"] = {
        "risk_level": risk.get("risk_level", "medium"),
        "risk_reasons": risk.get("risk_reasons", []) if isinstance(risk.get("risk_reasons"), list) else [],
    }
    if cand["seedance_prompt_risk"]["risk_level"] not in ("low", "medium", "high"):
        cand["seedance_prompt_risk"]["risk_level"] = "medium"
    return cand


def _template_block(template: dict[str, Any] | None) -> str:
    if not template:
        return "（无）"
    return (
        f"模版: {template.get('template_name', '')} ({template.get('template_id', '')})\n"
        f"调性: {template.get('system', '')}"
    )


def generate_creative_candidates(
    brief: dict[str, Any],
    template: dict[str, Any] | None = None,
    *,
    num_candidates: int = 8,
    model: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """生成 num_candidates 个差异化创意候选。

    Args:
        brief: build_creative_brief() 返回的 brief。
        template: match_template() 返回的模版 (可选, 作风格参考)。
        num_candidates: 候选数量, 默认 8。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        creative_candidate dict 列表 (见 schemas/creative_candidate.schema.json)。
    """
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        num_candidates=num_candidates,
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        template_block=_template_block(template),
    )
    raw_list = chat_json_array(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )
    candidates = []
    for i, raw in enumerate(raw_list, 1):
        if not isinstance(raw, dict):
            continue
        candidates.append(_normalize_candidate(raw, i))
    return candidates
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_creative_search -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add prompts/generate_creative_candidates.txt core/creative_search.py tests/test_creative_search.py
git commit -m "Add creative search (8 LLM candidates)"
```

---

## Task 4: creative_scoring (LLM + weighted overall)

**Files:**
- Create: `prompts/score_creative_candidate.txt`, `core/creative_scoring.py`, `tests/test_creative_scoring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_creative_scoring.py`:
```python
from __future__ import annotations
import unittest
from unittest.mock import patch

from core.creative_scoring import (
    SCORE_WEIGHTS,
    score_creative_candidate,
    score_creative_candidates,
    compute_overall,
)


_FAKE_SCORE = {
    "candidate_id": "C001",
    "scores": {
        "first_3_seconds_hook": 90, "product_clarity": 80, "brand_fit": 70,
        "audience_relevance": 75, "visual_memorability": 85, "platform_fit": 80,
        "seedance_feasibility": 60, "generation_risk_control": 70,
        "commercial_intent": 75
    },
    "strengths": ["强hook"], "weaknesses": ["手部风险"],
    "revision_suggestions": ["简化手部"], "render_recommendation": "shortlist"
}


class TestComputeOverall(unittest.TestCase):
    def test_weighted_average(self):
        overall = compute_overall(_FAKE_SCORE["scores"])
        expected = round(
            90 * 0.15 + 80 * 0.15 + 70 * 0.10 + 75 * 0.10 + 85 * 0.15
            + 80 * 0.10 + 60 * 0.15 + 70 * 0.05 + 75 * 0.05
        )
        self.assertEqual(overall, expected)

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(SCORE_WEIGHTS.values()), 1.0, places=6)


class TestScoreCandidate(unittest.TestCase):
    @patch("core.creative_scoring.chat_json_object", return_value=dict(_FAKE_SCORE))
    def test_score_fills_overall(self, _mock):
        brief = {"product_name": "x"}
        cand = {"candidate_id": "C001", "creative_route": "品牌大片"}
        result = score_creative_candidate(brief, cand)
        self.assertEqual(result["candidate_id"], "C001")
        self.assertIn("overall", result["scores"])
        self.assertEqual(result["scores"]["overall"], compute_overall(_FAKE_SCORE["scores"]))
        self.assertEqual(result["render_recommendation"], "shortlist")

    @patch("core.creative_scoring.chat_json_object", return_value=dict(_FAKE_SCORE))
    def test_score_candidates_returns_list(self, _mock):
        brief = {"product_name": "x"}
        cands = [{"candidate_id": "C001"}, {"candidate_id": "C002"}]
        results = score_creative_candidates(brief, cands)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["candidate_id"], "C001")

    @patch("core.creative_scoring.chat_json_object",
           return_value={"candidate_id": "C001", "scores": {"first_3_seconds_hook": 50},
                         "render_recommendation": "reject"})
    def test_missing_score_dims_default_zero(self, _mock):
        result = score_creative_candidate({"x": 1}, {"candidate_id": "C001"})
        for dim in SCORE_WEIGHTS:
            self.assertIn(dim, result["scores"])
        self.assertEqual(result["scores"]["first_3_seconds_hook"], 50)
        self.assertEqual(result["scores"]["product_clarity"], 0)
        self.assertEqual(result["scores"]["overall"], round(50 * 0.15))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_creative_scoring -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.creative_scoring'`

- [ ] **Step 3: Create the prompt template**

Create `prompts/score_creative_candidate.txt`:
```text
你是广告创意评审 + 视频生成可行性专家。对下面这个创意候选打分 (0-100 整数)。

【创意 brief】
{brief_json}

【创意候选】
{candidate_json}

【评分维度 (每项 0-100)】
- first_3_seconds_hook: 前 3 秒钩子强度 (是否第一眼留住人)
- product_clarity: 产品是否足够早、足够清楚出现
- brand_fit: 是否契合品牌调性/slogan
- audience_relevance: 是否契合目标人群动机
- visual_memorability: 画面记忆点 (一眼能复述的画面)
- platform_fit: 是否契合 {platform} 平台节奏与画幅
- seedance_feasibility: 视频模型生成的可行性 (避免复杂手部/多人/细小文字/真实人脸/外观漂移)
- generation_risk_control: 高风险元素是否被规避
- commercial_intent: 商业目标(品牌认知/种草/转化/复购)是否达成

【其它字段】
- strengths: 2-4 条
- weaknesses: 2-4 条
- revision_suggestions: 可执行的修改建议
- render_recommendation: reject|revise|shortlist|render
  (reject=不值生成; revise=需大改; shortlist=可入围但非首选; render=值得直接生成)

【硬性要求】
- 不要输出 overall (由系统加权计算)
- 判断 seedance_feasibility 时必须考虑: 复杂手部动作/多人交互/细小文字logo/
  真实人脸一致性/产品外观漂移/镜头过多/动作过复杂
- 产品外观必须与 dense_caption 一致, 否则 product_clarity 扣分
- 输出纯 JSON 对象, 不要 markdown, 不要解释
```

- [ ] **Step 4: Implement creative_scoring.py**

Create `core/creative_scoring.py`:
```python
"""创意候选 → 结构化评分 (LLM + 代码加权 overall)。

评分维度 9 项由 LLM 给出 (0-100)，overall 由代码按固定权重加权平均，
render_recommendation 由 LLM 给出。避免 LLM 主观推荐代替结构化打分。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import chat_json_object

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "score_creative_candidate.txt"
)

SCORE_WEIGHTS: dict[str, float] = {
    "first_3_seconds_hook": 0.15,
    "product_clarity": 0.15,
    "brand_fit": 0.10,
    "audience_relevance": 0.10,
    "visual_memorability": 0.15,
    "platform_fit": 0.10,
    "seedance_feasibility": 0.15,
    "generation_risk_control": 0.05,
    "commercial_intent": 0.05,
}

_SCORE_DIMS = tuple(SCORE_WEIGHTS.keys())


def compute_overall(scores: dict[str, Any]) -> int:
    """按 SCORE_WEIGHTS 加权平均, 结果四舍五入为整数 (0-100)。"""
    total = 0.0
    for dim, weight in SCORE_WEIGHTS.items():
        try:
            total += float(scores.get(dim, 0)) * weight
        except (TypeError, ValueError):
            total += 0.0
    return round(total)


def _normalize_score(raw: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    raw_scores = raw.get("scores") or {}
    if not isinstance(raw_scores, dict):
        raw_scores = {}
    scores: dict[str, Any] = {}
    for dim in _SCORE_DIMS:
        try:
            val = int(raw_scores.get(dim, 0))
        except (TypeError, ValueError):
            val = 0
        scores[dim] = max(0, min(100, val))
    scores["overall"] = compute_overall(scores)

    rec = raw.get("render_recommendation", "revise")
    if rec not in ("reject", "revise", "shortlist", "render"):
        rec = "revise"

    def _str_list(key: str) -> list[str]:
        v = raw.get(key, [])
        return [str(x) for x in v] if isinstance(v, list) else []

    return {
        "candidate_id": candidate_id,
        "scores": scores,
        "strengths": _str_list("strengths"),
        "weaknesses": _str_list("weaknesses"),
        "revision_suggestions": _str_list("revision_suggestions"),
        "render_recommendation": rec,
    }


def score_creative_candidate(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """对单个候选打分。

    Args:
        brief: creative_brief。
        candidate: creative_candidate。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        creative_score dict (见 schemas/creative_score.schema.json)。
    """
    candidate_id = candidate.get("candidate_id", "")
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        candidate_json=json.dumps(candidate, ensure_ascii=False, indent=2),
        platform=brief.get("platform", "douyin"),
    )
    raw = chat_json_object(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )
    return _normalize_score(raw, candidate_id)


def score_creative_candidates(
    brief: dict[str, Any],
    candidates: list[dict[str, Any]],
    model: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """对多个候选依次打分。"""
    return [
        score_creative_candidate(brief, c, model=model, api_key=api_key)
        for c in candidates
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_creative_scoring -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add prompts/score_creative_candidate.txt core/creative_scoring.py tests/test_creative_scoring.py
git commit -m "Add creative scoring with weighted overall"
```

---

## Task 5: shortlist (P1 core — pure rules, TDD)

**Files:**
- Create: `core/shortlist.py`, `tests/test_shortlist.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_shortlist.py`:
```python
from __future__ import annotations
import unittest

from core.shortlist import select_shortlist


def _cand(cid, route="X"):
    return {"candidate_id": cid, "creative_route": route, "shot_plan": [],
            "seedance_prompt_risk": {"risk_level": "low", "risk_reasons": []}}


def _score(cid, overall, feasibility=80, clarity=80, rec="shortlist"):
    return {
        "candidate_id": cid,
        "scores": {
            "first_3_seconds_hook": overall, "product_clarity": clarity,
            "brand_fit": overall, "audience_relevance": overall,
            "visual_memorability": overall, "platform_fit": overall,
            "seedance_feasibility": feasibility,
            "generation_risk_control": overall, "commercial_intent": overall,
            "overall": overall,
        },
        "strengths": [], "weaknesses": [], "revision_suggestions": [],
        "render_recommendation": rec,
    }


class TestSelectShortlist(unittest.TestCase):
    def test_sorted_by_overall_desc(self):
        cands = [_cand("C001"), _cand("C002"), _cand("C003")]
        scores = [_score("C001", 70), _score("C002", 90), _score("C003", 80)]
        sl = select_shortlist(cands, scores, top_k=3, min_overall=0)
        self.assertEqual([s["candidate_id"] for s in sl], ["C002", "C003", "C001"])

    def test_min_overall_filter(self):
        cands = [_cand("C001"), _cand("C002")]
        scores = [_score("C001", 60), _score("C002", 90)]
        sl = select_shortlist(cands, scores, top_k=3, min_overall=80)
        self.assertEqual(len(sl), 1)
        self.assertEqual(sl[0]["candidate_id"], "C002")

    def test_low_feasibility_marks_ineligible(self):
        cands = [_cand("C001")]
        scores = [_score("C001", 95, feasibility=50)]
        sl = select_shortlist(cands, scores, top_k=3, min_feasibility=75)
        self.assertEqual(len(sl), 1)
        self.assertFalse(sl[0]["eligible_for_render"])
        self.assertTrue(sl[0]["ineligible_reasons"])

    def test_low_product_clarity_blocks_render(self):
        cands = [_cand("C001")]
        scores = [_score("C001", 95, clarity=60)]
        sl = select_shortlist(cands, scores, top_k=3)
        self.assertFalse(sl[0]["eligible_for_render"])
        self.assertIn(any("product_clarity" in r or "产品" in r for r in sl[0]["ineligible_reasons"]),
                      True)

    def test_top_k_limit(self):
        cands = [_cand(f"C00{i}") for i in range(1, 5)]
        scores = [_score(f"C00{i}", 90 - i) for i in range(1, 5)]
        sl = select_shortlist(cands, scores, top_k=2)
        self.assertEqual(len(sl), 2)
        self.assertEqual(sl[0]["candidate_id"], "C001")

    def test_eligible_when_all_good(self):
        cands = [_cand("C001")]
        scores = [_score("C001", 90, feasibility=85, clarity=85, rec="render")]
        sl = select_shortlist(cands, scores, top_k=3)
        self.assertTrue(sl[0]["eligible_for_render"])
        self.assertEqual(sl[0]["ineligible_reasons"], [])
        self.assertEqual(sl[0]["overall"], 90)

    def test_candidate_score_pairing_by_id(self):
        cands = [_cand("C001"), _cand("C002")]
        scores = [_score("C002", 90), _score("C001", 70)]
        sl = select_shortlist(cands, scores, top_k=3)
        self.assertEqual(sl[0]["candidate_id"], "C002")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_shortlist -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.shortlist'`

- [ ] **Step 3: Implement shortlist.py**

Create `core/shortlist.py`:
```python
"""评分 → shortlist (纯规则, P1 核心价值)。

让系统能拒绝低质量创意，而不是永远生成一个最终 prompt。
规则:
  1. 按 overall 降序排序。
  2. 低于 min_overall 的候选不进入 shortlist。
  3. seedance_feasibility < min_feasibility 的候选可入围但标记 ineligible_for_render。
  4. product_clarity < 70 的候选默认不能进入 render (ineligible)。
  5. 取 top_k 个，每个附加 score summary + 资格判定。
"""

from __future__ import annotations

from typing import Any

_PRODUCT_CLARITY_FLOOR = 70


def select_shortlist(
    candidates: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    *,
    top_k: int = 3,
    min_overall: int = 80,
    min_feasibility: int = 75,
) -> list[dict[str, Any]]:
    """从候选+评分中选出 shortlist。

    Args:
        candidates: creative_candidate 列表。
        scores: creative_score 列表 (与 candidates 按 candidate_id 配对)。
        top_k: 最多保留多少个。
        min_overall: 进入 shortlist 的 overall 门槛。
        min_feasibility: 进入 render 的 seedance_feasibility 门槛。

    Returns:
        shortlist item 列表 (见 plan 数据结构契约), 按 overall 降序。
    """
    score_by_id = {s.get("candidate_id"): s for s in scores}
    cand_by_id = {c.get("candidate_id"): c for c in candidates}

    rows: list[dict[str, Any]] = []
    for sid, score in score_by_id.items():
        cand = cand_by_id.get(sid)
        if cand is None:
            continue
        overall = int(score.get("scores", {}).get("overall", 0))
        if overall < min_overall:
            continue
        rows.append({
            "candidate_id": sid,
            "candidate": cand,
            "score": score,
            "overall": overall,
            "eligible_for_render": True,
            "ineligible_reasons": [],
        })

    rows.sort(key=lambda r: r["overall"], reverse=True)
    rows = rows[:top_k]

    for row in rows:
        sc = row["score"].get("scores", {})
        reasons: list[str] = []
        feasibility = int(sc.get("seedance_feasibility", 0))
        if feasibility < min_feasibility:
            reasons.append(
                f"seedance_feasibility={feasibility} 低于 {min_feasibility}, 生成失败风险高"
            )
        clarity = int(sc.get("product_clarity", 0))
        if clarity < _PRODUCT_CLARITY_FLOOR:
            reasons.append(
                f"product_clarity={clarity} 低于 {_PRODUCT_CLARITY_FLOOR}, 产品不够清楚"
            )
        if row["score"].get("render_recommendation") == "reject":
            reasons.append("LLM render_recommendation=reject")
        if reasons:
            row["eligible_for_render"] = False
            row["ineligible_reasons"] = reasons

    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_shortlist -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add core/shortlist.py tests/test_shortlist.py
git commit -m "Add shortlist with render-eligibility rejection rules"
```

---

## Task 6: storyboard_simulator (minimal, opt-in)

**Files:**
- Create: `prompts/generate_storyboard_simulator.txt`, `core/storyboard_simulator.py`, `tests/test_storyboard_simulator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_storyboard_simulator.py`:
```python
from __future__ import annotations
import unittest
from unittest.mock import patch

from core.storyboard_simulator import generate_storyboard_simulation


_FAKE = {
    "candidate_id": "C001",
    "keyframes": [
        {"keyframe_id": "KF01", "time": "0s", "frame_purpose": "hook",
         "image_prompt_cn": "微距针穿刺", "image_prompt_en": "macro needle",
         "negative_prompt": "no text", "continuity_notes": "暖金光",
         "product_fidelity_notes": "银白金属"}
    ],
    "storyboard_review": {
        "visual_consistency_risk": "low", "product_fidelity_risk": "low",
        "model_difficulty": "medium", "recommendation": "acceptable"
    }
}


class TestStoryboardSimulator(unittest.TestCase):
    @patch("core.storyboard_simulator.chat_json_object", return_value=dict(_FAKE))
    def test_generates_keyframes(self, _mock):
        brief = {"dense_caption": "戒指", "product_name": "对戒"}
        cand = {"candidate_id": "C001", "creative_route": "品牌大片",
                "shot_plan": [{"shot_id": "S01", "time_range": "0-3s"}]}
        sim = generate_storyboard_simulation(brief, cand)
        self.assertEqual(sim["candidate_id"], "C001")
        self.assertEqual(len(sim["keyframes"]), 1)
        self.assertEqual(sim["keyframes"][0]["keyframe_id"], "KF01")
        self.assertEqual(sim["storyboard_review"]["recommendation"], "acceptable")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_storyboard_simulator -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.storyboard_simulator'`

- [ ] **Step 3: Create the prompt template**

Create `prompts/generate_storyboard_simulator.txt`:
```text
你是分镜关键帧预演师。为下面这个创意候选生成 3-5 个关键帧 prompt,
供用户在用图片模型预演后再决定是否消耗视频积分。

【brief】
{brief_json}

【创意候选】
{candidate_json}

【每个关键帧字段】
- keyframe_id: KF01, KF02, ...
- time: 如 "0s", "3s"
- frame_purpose: hook|product_reveal|proof|emotional_peak|brand_lock
- image_prompt_cn: 中文关键帧 prompt (构图/景别/光线/材质/产品外观)
- image_prompt_en: 英文关键帧 prompt
- negative_prompt: 负面约束 (多余文字/水印/错误logo/变形手部)
- continuity_notes: 与前后帧的连续性说明
- product_fidelity_notes: 产品外观保真要点 (严格依据 dense_caption)

【storyboard_review 字段】
- visual_consistency_risk: 关键帧之间视觉一致性风险
- product_fidelity_risk: 产品外观漂移风险
- model_difficulty: 图片模型生成难度 low|medium|high
- recommendation: revise|acceptable|strong

【硬性要求】
- 产品颜色/材质/结构严格依据 dense_caption, 不得臆造
- 对不适合图片预演的镜头 (如复杂运动) 在 continuity_notes 给 warning
- 输出纯 JSON 对象, 不要 markdown, 不要解释
```

- [ ] **Step 4: Implement storyboard_simulator.py**

Create `core/storyboard_simulator.py`:
```python
"""为 shortlist 候选生成关键帧 prompt (最小实现, P2 增强)。

不调用图片模型，只输出可复制给图片生成模型的关键帧 prompt。
默认在 decision 模式下不调用 (低成本), 仅 --storyboard 时启用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import chat_json_object

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "generate_storyboard_simulator.txt"
)


def _normalize(raw: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    keyframes = raw.get("keyframes") or []
    if not isinstance(keyframes, list):
        keyframes = []
    review = raw.get("storyboard_review") or {}
    if not isinstance(review, dict):
        review = {}
    review.setdefault("visual_consistency_risk", "")
    review.setdefault("product_fidelity_risk", "")
    review.setdefault("model_difficulty", "medium")
    review.setdefault("recommendation", "acceptable")
    return {
        "candidate_id": candidate_id,
        "keyframes": keyframes,
        "storyboard_review": review,
    }


def generate_storyboard_simulation(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """为单个候选生成关键帧级 storyboard prompt。

    Args:
        brief: creative_brief。
        candidate: creative_candidate (通常来自 shortlist)。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        storyboard_simulation dict (见 schemas/storyboard_simulation.schema.json)。
    """
    candidate_id = candidate.get("candidate_id", "")
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        candidate_json=json.dumps(candidate, ensure_ascii=False, indent=2),
    )
    raw = chat_json_object(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )
    return _normalize(raw, candidate_id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_storyboard_simulator -v`
Expected: PASS (1 test)

- [ ] **Step 6: Commit**

```bash
git add prompts/generate_storyboard_simulator.txt core/storyboard_simulator.py tests/test_storyboard_simulator.py
git commit -m "Add minimal storyboard simulator (opt-in)"
```

---

## Task 7: render_decision (rule pick + LLM reasoning)

**Files:**
- Create: `prompts/make_render_decision.txt`, `core/render_decision.py`, `tests/test_render_decision.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_render_decision.py`:
```python
from __future__ import annotations
import unittest
from unittest.mock import patch

from core.render_decision import make_render_decision, pick_top_eligible


def _sl(cid, overall, eligible=True):
    return {
        "candidate_id": cid,
        "candidate": {"candidate_id": cid, "creative_route": "X", "shot_plan": []},
        "score": {"candidate_id": cid, "scores": {"overall": overall, "seedance_feasibility": 80},
                  "render_recommendation": "render"},
        "overall": overall,
        "eligible_for_render": eligible,
        "ineligible_reasons": [] if eligible else ["x"],
    }


class TestPickTopEligible(unittest.TestCase):
    def test_picks_highest_eligible(self):
        sl = [_sl("C001", 80, False), _sl("C002", 90, True), _sl("C003", 85, True)]
        self.assertEqual(pick_top_eligible(sl), "C002")

    def test_none_eligible_returns_none(self):
        sl = [_sl("C001", 90, False)]
        self.assertIsNone(pick_top_eligible(sl))

    def test_empty_returns_none(self):
        self.assertIsNone(pick_top_eligible([]))


class TestMakeRenderDecision(unittest.TestCase):
    @patch("core.render_decision.chat_json_object")
    def test_should_render_true(self, mock_chat):
        mock_chat.return_value = {
            "recommended_candidate_id": "C002",
            "should_render": True, "confidence": 85,
            "reason": "强hook且可行", "expected_failure_modes": ["手部"],
            "pre_render_checklist": ["确认产品颜色"],
            "if_first_render_fails": {"likely_causes": ["手部畸形"],
                                       "recommended_fix": "简化手部",
                                       "do_not_retry_if": ["产品颜色错"]}
        }
        brief = {"product_name": "x"}
        sl = [_sl("C001", 80), _sl("C002", 90)]
        dec = make_render_decision(brief, sl, [])
        self.assertTrue(dec["should_render"])
        self.assertEqual(dec["recommended_candidate_id"], "C002")
        self.assertEqual(dec["confidence"], 85)
        self.assertIn("确认产品颜色", dec["pre_render_checklist"])

    @patch("core.render_decision.chat_json_object")
    def test_no_eligible_forces_should_render_false(self, mock_chat):
        mock_chat.return_value = {
            "recommended_candidate_id": "C001", "should_render": True,
            "confidence": 50, "reason": "", "expected_failure_modes": [],
            "pre_render_checklist": [],
            "if_first_render_fails": {"likely_causes": [], "recommended_fix": "", "do_not_retry_if": []}
        }
        sl = [_sl("C001", 90, eligible=False)]
        dec = make_render_decision({"x": 1}, sl, [])
        self.assertFalse(dec["should_render"])
        self.assertIsNone(dec["recommended_candidate_id"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_render_decision -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.render_decision'`

- [ ] **Step 3: Create the prompt template**

Create `prompts/make_render_decision.txt`:
```text
你是视频积分预算决策者。从下面的 shortlist 中选 1 个最值得消耗一次小云雀/Seedance
视频生成额度的候选。如果没有一个值得, 必须明确 should_render=false。

【brief】
{brief_json}

【shortlist (含评分摘要)】
{shortlist_json}

【关键帧预演 (可选)】
{storyboard_block}

【输出字段】
- recommended_candidate_id: 选中的 candidate_id (无则 null)
- should_render: bool
- confidence: 0-100
- reason: 为什么这一版最值得花积分 (或为什么不值得)
- expected_failure_modes: 这版可能失败的方式 (2-4 条)
- pre_render_checklist: 上传小云雀前需人工确认的检查项 (3-6 条)
- if_first_render_fails: {likely_causes:[], recommended_fix:str, do_not_retry_if:[]}
  (do_not_retry_if = 出现这些情况就别重试, 直接换候选)

【判断依据】
- 优先 overall 高且 eligible_for_render=true 的候选
- 必须考虑视频模型生成可行性, 不要推荐高风险候选浪费积分
- 产品外观必须可依据 dense_caption 稳定复现
- 输出纯 JSON 对象, 不要 markdown, 不要解释
```

- [ ] **Step 4: Implement render_decision.py**

Create `core/render_decision.py`:
```python
"""shortlist → render_decision (规则选 + LLM 推理)。

规则层: 从 eligible_for_render 候选中选 overall 最高者;
若没有 eligible 候选, should_render=false 且 recommended_candidate_id=null。
LLM 层: 生成 reason / 失败模式 / 上传前检查项 / 首轮失败修正建议。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json_utils import chat_json_object

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "make_render_decision.txt"
)


def pick_top_eligible(shortlisted: list[dict[str, Any]]) -> str | None:
    """从 shortlist 中选 overall 最高的 eligible 候选; 无则 None。"""
    eligible = [r for r in shortlisted if r.get("eligible_for_render")]
    if not eligible:
        return None
    eligible.sort(key=lambda r: int(r.get("overall", 0)), reverse=True)
    return eligible[0].get("candidate_id")


def _storyboard_block(simulations: list[dict[str, Any]]) -> str:
    if not simulations:
        return "（未启用关键帧预演）"
    return json.dumps(simulations, ensure_ascii=False, indent=2)


def _normalize(raw: dict[str, Any], fallback_id: str | None,
               force_skip: bool, shortlisted: list[dict[str, Any]]) -> dict[str, Any]:
    fail = raw.get("if_first_render_fails") or {}
    if not isinstance(fail, dict):
        fail = {}

    def _str_list(key):
        v = raw.get(key, [])
        return [str(x) for x in v] if isinstance(v, list) else []

    def _fail_list(key):
        v = fail.get(key, [])
        return [str(x) for x in v] if isinstance(v, list) else []

    should_render = bool(raw.get("should_render", False)) and not force_skip
    recommended = None if force_skip else (raw.get("recommended_candidate_id") or fallback_id)

    return {
        "recommended_candidate_id": recommended,
        "should_render": should_render,
        "confidence": _clamp_int(raw.get("confidence", 0), 0, 100),
        "reason": str(raw.get("reason", "")),
        "expected_failure_modes": _str_list("expected_failure_modes"),
        "pre_render_checklist": _str_list("pre_render_checklist"),
        "if_first_render_fails": {
            "likely_causes": _fail_list("likely_causes"),
            "recommended_fix": str(fail.get("recommended_fix", "")),
            "do_not_retry_if": _fail_list("do_not_retry_if"),
        },
    }


def _clamp_int(v: Any, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def make_render_decision(
    brief: dict[str, Any],
    shortlisted: list[dict[str, Any]],
    storyboard_simulations: list[dict[str, Any]] | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """决定哪一版值得消耗一次视频积分。

    Args:
        brief: creative_brief。
        shortlisted: select_shortlist() 的返回值。
        storyboard_simulations: 关键帧预演结果 (可选, 可为空列表)。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        render_decision dict (见 schemas/render_decision.schema.json)。
    """
    sims = storyboard_simulations or []
    fallback_id = pick_top_eligible(shortlisted)
    force_skip = fallback_id is None

    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        shortlist_json=json.dumps(shortlisted, ensure_ascii=False, indent=2),
        storyboard_block=_storyboard_block(sims),
    )
    raw = chat_json_object(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )
    return _normalize(raw, fallback_id, force_skip, shortlisted)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_render_decision -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add prompts/make_render_decision.txt core/render_decision.py tests/test_render_decision.py
git commit -m "Add render decision (rule pick + LLM reasoning)"
```

---

## Task 8: output_package (final 小云雀 prompt + report.md)

**Files:**
- Create: `prompts/build_final_prompt.txt`, `core/output_package.py`, `tests/test_output_package.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_output_package.py`:
```python
from __future__ import annotations
import unittest
from unittest.mock import patch

from core.output_package import build_final_prompt_package, build_report_md


_BRIEF = {
    "product_name": "错金浪纹对戒", "category": "珠宝饰品",
    "dense_caption": "宽版银白金属戒, 错金浪纹, 蓝宝石主石。",
    "selling_points": ["独特浪纹", "蓝宝石主石"], "target_audience": "22-35岁情侣",
    "brand_name": "", "brand_assets": {"slogan": "错金浪纹，见证唯一"},
    "commercial_goal": "creative_ad", "platform": "douyin",
    "aspect_ratio": "9:16", "duration_seconds": 15,
    "constraints": {"must_show_product_by_second": 3, "must_have_cta": False,
                    "avoid_face_generation": True, "avoid_complex_hand_motion": False},
}
_CAND = {"candidate_id": "C001", "creative_route": "品牌大片", "hook": "微距针穿刺",
         "one_sentence_idea": "金线生长成铠甲", "narrative_spine": "针→线→纹→龙",
         "shot_plan": [{"shot_id": "S01", "time_range": "0-3s", "purpose": "hook",
                        "visual": "微距", "camera": "慢推", "lighting": "侧逆光",
                        "sound": "落针声", "copy_or_voiceover": "",
                        "product_visibility": "partial"}]}
_SCORE = {"candidate_id": "C001", "scores": {"overall": 88},
          "render_recommendation": "render", "strengths": ["强hook"], "weaknesses": []}
_DECISION = {"recommended_candidate_id": "C001", "should_render": True, "confidence": 85,
             "reason": "强hook且可行", "expected_failure_modes": ["手部畸形"],
             "pre_render_checklist": ["确认产品颜色"],
             "if_first_render_fails": {"likely_causes": ["手部"], "recommended_fix": "简化手部",
                                       "do_not_retry_if": ["颜色错"]}}


class TestBuildFinalPromptPackage(unittest.TestCase):
    @patch("core.output_package.chat", return_value="【小云雀提示词成品】...")
    def test_package_has_prompt_and_summary(self, _mock):
        pkg = build_final_prompt_package(_BRIEF, _CAND, _SCORE, None, _DECISION)
        self.assertIn("小云雀提示词成品", pkg["xiaoyunque_prompt"])
        self.assertTrue(pkg["summary"])
        self.assertEqual(pkg["selected_candidate"]["candidate_id"], "C001")
        self.assertIsNone(pkg["storyboard_simulation"])
        self.assertEqual(pkg["render_decision"]["recommended_candidate_id"], "C001")
        self.assertIsInstance(pkg["manual_upload_notes"], list)

    @patch("core.output_package.chat", return_value="成品")
    def test_report_answers_required_questions(self, _mock):
        pkg = build_final_prompt_package(_BRIEF, _CAND, _SCORE, None, _DECISION)
        # build_report_md needs a candidates/scores summary context
        report = build_report_md(pkg, all_candidates_count=8,
                                 rejected=[{"candidate_id": "C002",
                                            "render_recommendation": "reject",
                                            "scores": {"overall": 40}}],
                                 shortlisted=[{"candidate_id": "C001", "overall": 88,
                                               "eligible_for_render": True,
                                               "ineligible_reasons": []}])
        self.assertIn("8", report)
        self.assertIn("C001", report)
        self.assertIn("C002", report)
        self.assertIn("确认产品颜色", report)
        self.assertIn("简化手部", report)
        self.assertIn("强hook且可行", report)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_output_package -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.output_package'`

- [ ] **Step 3: Create the prompt template**

Create `prompts/build_final_prompt.txt`:
```text
你是小云雀/Seedance 视频提示词工程师。把下面的创意方案渲染成一段可直接粘贴到
小云雀的完整分镜提示词 (纯文本, 不要 markdown)。

【创意 brief】
{brief_json}

【选中的创意候选】
{candidate_json}

【评分摘要】
{score_json}

【渲染决策】
{decision_json}

【输出要求 — 蒸馏自小云雀营销 skill trace】
1. 保留小云雀常用字段: 商品名称 / 卖点 / 目标人群 / 传播场景
2. 明确: 视频比例({aspect_ratio}) / 时长({duration}秒) / 风格 / 角色 / 镜头 / 声音 / 文案
3. 镜头列表: 每镜头写 编号 | 时长 | 景别 | 画面描述 | 运镜 | 光线 | 产品展示方式
4. 产品外观严格依据 dense_caption, 不得改颜色/材质/结构:
   {dense_caption}
5. 前 3 秒必须有强 hook, 产品在 {must_show_second} 秒前出现
6. {sensitive_constraints}
7. 负面约束: 不要生成多余文字、水印、错误 logo、变形手部、产品外观漂移
8. 输出纯文本分镜脚本, 不要 markdown 代码块, 不要额外解释
```

- [ ] **Step 4: Implement output_package.py**

Create `core/output_package.py`:
```python
"""组装最终可粘贴到小云雀的 prompt + 决策报告。

输出 xiaoyunque_prompt (纯文本, 直接粘贴) + 完整 package dict + report.md。
严格约束产品外观来自 dense_caption, 对敏感类目加入产品真实性约束。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deepseek_client import chat

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "build_final_prompt.txt"
)

_SENSITIVE_CATEGORIES = {"珠宝饰品", "高定礼服", "美妆", "医美"}


def _sensitive_constraints(brief: dict[str, Any]) -> str:
    cat = brief.get("category", "")
    parts: list[str] = []
    if cat in _SENSITIVE_CATEGORIES:
        parts.append("本品类易过度美化, 必须保持产品真实材质/颜色/工艺, 不得美化失真")
    if brief.get("constraints", {}).get("avoid_face_generation"):
        parts.append("避免生成真实人脸, 优先用产品/手部/人台/背影")
    if brief.get("constraints", {}).get("avoid_complex_hand_motion"):
        parts.append("避免复杂手部动作")
    return "；".join(parts) if parts else "无额外约束"


def _build_xiaoyunque_prompt(
    brief: dict[str, Any], candidate: dict[str, Any],
    score: dict[str, Any], decision: dict[str, Any],
    template: dict[str, Any] | None, model: str | None, api_key: str | None,
) -> str:
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
        candidate_json=json.dumps(candidate, ensure_ascii=False, indent=2),
        score_json=json.dumps(score, ensure_ascii=False, indent=2),
        decision_json=json.dumps(decision, ensure_ascii=False, indent=2),
        aspect_ratio=brief.get("aspect_ratio", "9:16"),
        duration=brief.get("duration_seconds", 15),
        dense_caption=brief.get("dense_caption", ""),
        must_show_second=brief.get("constraints", {}).get("must_show_product_by_second", 3),
        sensitive_constraints=_sensitive_constraints(brief),
    )
    return chat(
        [{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
    )


def _manual_upload_notes(brief: dict[str, Any], decision: dict[str, Any]) -> list[str]:
    notes = [
        f"画幅选 {brief.get('aspect_ratio', '9:16')}, 时长 {brief.get('duration_seconds', 15)} 秒",
        "上传前对照 pre_render_checklist 逐条确认产品外观与 dense_caption 一致",
    ]
    if brief.get("constraints", {}).get("avoid_face_generation"):
        notes.append("如小云雀生成真人脸失败, 改用产品特写/人台/背影")
    notes.extend(decision.get("pre_render_checklist", []))
    return notes


def _summary(brief: dict[str, Any], candidate: dict[str, Any],
             score: dict[str, Any], decision: dict[str, Any]) -> str:
    overall = score.get("scores", {}).get("overall", 0)
    return (
        f"推荐 {candidate.get('candidate_id')} ({candidate.get('creative_route', '')}), "
        f"overall={overall}, should_render={decision.get('should_render')}, "
        f"confidence={decision.get('confidence')}。"
        f"创意: {candidate.get('one_sentence_idea', '')}"
    )


def build_final_prompt_package(
    brief: dict[str, Any],
    candidate: dict[str, Any],
    score: dict[str, Any],
    storyboard_simulation: dict[str, Any] | None,
    render_decision: dict[str, Any],
    template: dict[str, Any] | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """组装最终 prompt 包。

    Args:
        brief: creative_brief。
        candidate: 选中的 creative_candidate。
        score: 该候选的 creative_score。
        storyboard_simulation: 关键帧预演 (可为 None)。
        render_decision: make_render_decision() 返回值。
        template: match_template() 返回的模版 (可选)。
        model: DeepSeek 模型名覆盖。
        api_key: DeepSeek API key 覆盖。

    Returns:
        output_package dict (见 plan 数据结构契约)。
    """
    xiaoyunque_prompt = _build_xiaoyunque_prompt(
        brief, candidate, score, render_decision, template, model, api_key
    )
    return {
        "xiaoyunque_prompt": xiaoyunque_prompt,
        "summary": _summary(brief, candidate, score, render_decision),
        "creative_brief": brief,
        "selected_candidate": candidate,
        "score": score,
        "storyboard_simulation": storyboard_simulation,
        "render_decision": render_decision,
        "manual_upload_notes": _manual_upload_notes(brief, render_decision),
    }


def build_report_md(
    package: dict[str, Any],
    *,
    all_candidates_count: int,
    rejected: list[dict[str, Any]],
    shortlisted: list[dict[str, Any]],
) -> str:
    """生成给用户看的决策报告 (markdown)。

    必须回答: 候选数 / 淘汰原因 / shortlist / 最终推荐 / 为什么值得花积分 /
    上传前检查 / 首轮失败怎么改。
    """
    dec = package.get("render_decision", {})
    cand = package.get("selected_candidate", {})
    score = package.get("score", {})
    lines: list[str] = []
    lines.append(f"# 创意决策报告")
    lines.append("")
    lines.append(f"## 概览")
    lines.append(f"- 生成创意候选数: {all_candidates_count}")
    lines.append(f"- 进入 shortlist: {len(shortlisted)} 个")
    lines.append(f"- 被淘汰: {len(rejected)} 个")
    lines.append(f"- 最终推荐: {dec.get('recommended_candidate_id')} "
                 f"(should_render={dec.get('should_render')}, "
                 f"confidence={dec.get('confidence')})")
    lines.append("")

    lines.append("## 被淘汰的候选及原因")
    if rejected:
        for r in rejected:
            cid = r.get("candidate_id", "?")
            rec = r.get("render_recommendation", "")
            overall = r.get("scores", {}).get("overall", 0)
            lines.append(f"- {cid}: overall={overall}, recommendation={rec}")
    else:
        lines.append("- (无)")
    lines.append("")

    lines.append("## Shortlist")
    for s in shortlisted:
        cid = s.get("candidate_id", "?")
        overall = s.get("overall", 0)
        eligible = s.get("eligible_for_render")
        reasons = s.get("ineligible_reasons", [])
        flag = "✓ 可生成" if eligible else f"✗ 暂不生成 ({'; '.join(reasons)})"
        lines.append(f"- {cid}: overall={overall} — {flag}")
    lines.append("")

    lines.append("## 为什么这一版最值得花一次视频积分")
    lines.append(dec.get("reason", "(未给出理由)"))
    lines.append("")

    lines.append("## 上传前检查清单")
    for item in dec.get("pre_render_checklist", []):
        lines.append(f"- [ ] {item}")
    lines.append("")

    lines.append("## 预期失败模式")
    for fm in dec.get("expected_failure_modes", []):
        lines.append(f"- {fm}")
    lines.append("")

    fail = dec.get("if_first_render_fails", {})
    lines.append("## 如果第一次视频失败，优先怎么改")
    lines.append(f"可能原因: {', '.join(fail.get('likely_causes', [])) or '(未列出)'}")
    lines.append(f"建议修改: {fail.get('recommended_fix', '(未给出)')}")
    lines.append(f"出现以下情况不要重试 (直接换候选): "
                 f"{', '.join(fail.get('do_not_retry_if', [])) or '(未列出)'}")
    lines.append("")

    lines.append("## 选中候选评分摘要")
    lines.append(f"- candidate_id: {cand.get('candidate_id')}")
    lines.append(f"- creative_route: {cand.get('creative_route')}")
    lines.append(f"- overall: {score.get('scores', {}).get('overall', 0)}")
    lines.append(f"- render_recommendation: {score.get('render_recommendation')}")
    lines.append("")

    lines.append("## 最终提示词")
    lines.append("见同名 `.txt` 文件，可直接粘贴到小云雀。")
    return "\n".join(lines)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_output_package -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add prompts/build_final_prompt.txt core/output_package.py tests/test_output_package.py
git commit -m "Add final prompt package + decision report builder"
```

---

## Task 9: CLI integration (main.py — modes + all artifacts)

**Files:**
- Modify: `main.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI test**

Create `tests/test_cli.py`:
```python
from __future__ import annotations
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import main


def _features():
    return {"category": "珠宝饰品", "sub_category": "情侣对戒",
            "product_name": "对戒", "selling_points": ["浪纹"],
            "target_audience": "情侣", "dense_caption": "银白金属戒",
            "distribution_scenarios": ["douyin"]}


def _cand(cid):
    return {"candidate_id": cid, "creative_route": "品牌大片", "hook": "h",
            "one_sentence_idea": "idea", "narrative_spine": "s", "shot_plan": [],
            "seedance_prompt_risk": {"risk_level": "low", "risk_reasons": []}}


def _score(cid, overall=88):
    return {"candidate_id": cid,
            "scores": {"first_3_seconds_hook": 90, "product_clarity": 85,
                       "brand_fit": 80, "audience_relevance": 80,
                       "visual_memorability": 85, "platform_fit": 80,
                       "seedance_feasibility": 82, "generation_risk_control": 80,
                       "commercial_intent": 80, "overall": overall},
            "strengths": [], "weaknesses": [], "revision_suggestions": [],
            "render_recommendation": "render"}


class TestCliFastMode(unittest.TestCase):
    @patch("core.generate_prompt.generate_final_prompt", return_value="FAST PROMPT")
    @patch("core.storyboard.match_template", return_value={"template_id": "t", "template_name": "n"})
    @patch("core.extract_features.extract_features", return_value=_features())
    def test_fast_mode_writes_txt_and_features(self, _f, _t, _p):
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "ring.jpg")
            open(img, "w").close()
            out = os.path.join(d, "out.txt")
            rc = main.main(["--mode", "fast", img, "-o", out])
            self.assertEqual(rc, 0)
            self.assertEqual(open(out).read(), "FAST PROMPT")
            self.assertTrue(os.path.exists(out.replace(".txt", ".features.json")))


class TestCliDecisionMode(unittest.TestCase):
    @patch("core.output_package.chat", return_value="FINAL XIAOYUNQUE PROMPT")
    @patch("core.render_decision.chat_json_object")
    @patch("core.creative_scoring.chat_json_object")
    @patch("core.creative_search.chat_json_array")
    @patch("core.storyboard.match_template", return_value={"template_id": "t", "template_name": "n"})
    @patch("core.extract_features.extract_features", return_value=_features())
    def test_decision_mode_writes_all_artifacts(self, _f, _t, mock_search, mock_score,
                                                mock_decision, _chat):
        mock_search.return_value = [_cand("C001")]
        mock_score.return_value = _score("C001")
        mock_decision.return_value = {
            "recommended_candidate_id": "C001", "should_render": True,
            "confidence": 85, "reason": "值得", "expected_failure_modes": ["手部"],
            "pre_render_checklist": ["确认颜色"],
            "if_first_render_fails": {"likely_causes": ["手部"], "recommended_fix": "简化",
                                       "do_not_retry_if": ["颜色错"]}}
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "ring.jpg")
            open(img, "w").close()
            out = os.path.join(d, "out.txt")
            rc = main.main(["--mode", "decision", img, "-o", out,
                            "--num-candidates", "1", "--top-k", "1", "--min-score", "80"])
            self.assertEqual(rc, 0)
            stem = out[:-4]
            for suffix in [".features.json", ".brief.json", ".candidates.json",
                           ".scores.json", ".shortlist.json", ".decision.json",
                           ".package.json", ".txt", ".report.md"]:
                self.assertTrue(os.path.exists(stem + suffix), f"missing {suffix}")
            self.assertIn("FINAL XIAOYUNQUE PROMPT", open(out).read())
            pkg = json.loads(open(stem + ".package.json").read())
            self.assertEqual(pkg["selected_candidate"]["candidate_id"], "C001")


class TestCliExploreMode(unittest.TestCase):
    @patch("core.creative_scoring.chat_json_object")
    @patch("core.creative_search.chat_json_array")
    @patch("core.storyboard.match_template", return_value={"template_id": "t", "template_name": "n"})
    @patch("core.extract_features.extract_features", return_value=_features())
    def test_explore_mode_skips_final_prompt(self, _f, _t, mock_search, mock_score):
        mock_search.return_value = [_cand("C001")]
        mock_score.return_value = _score("C001")
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "ring.jpg")
            open(img, "w").close()
            out = os.path.join(d, "out.txt")
            rc = main.main(["--mode", "explore", img, "-o", out,
                            "--num-candidates", "1", "--top-k", "1"])
            self.assertEqual(rc, 0)
            stem = out[:-4]
            for suffix in [".features.json", ".brief.json", ".candidates.json",
                           ".scores.json", ".shortlist.json"]:
                self.assertTrue(os.path.exists(stem + suffix), f"missing {suffix}")
            self.assertFalse(os.path.exists(stem + ".decision.json"))
            self.assertFalse(os.path.exists(stem + ".package.json"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL (`main` does not accept `--mode` / `error: unrecognized arguments`)

- [ ] **Step 3: Rewrite main.py to add modes + wiring**

Replace the entire contents of `main.py` with:
```python
"""广告分镜提示词生成 CLI。

模式:
  fast     (默认) 原流程: 提取特征 → 模版匹配 → 生成一个最终 prompt
  explore  生成多创意候选 → 评分 → shortlist (不生成最终小云雀 prompt)
  decision 完整流程: explore → render_decision → 最终 prompt + 决策报告

输出 (data/<stem>.* 或 -o 指定路径的同名族):
  .features.json .brief.json .candidates.json .scores.json .shortlist.json
  .storyboard.json(可选) .decision.json .package.json .txt .report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from core.creative_scoring import score_creative_candidates
from core.creative_search import generate_creative_candidates
from core.deepseek_client import DeepSeekError
from core.extract_features import extract_features
from core.generate_prompt import generate_final_prompt
from core.brief import build_creative_brief
from core.llm_client import LLMError
from core.output_package import build_final_prompt_package, build_report_md
from core.render_decision import make_render_decision
from core.shortlist import select_shortlist
from core.storyboard import list_categories, match_template
from core.storyboard_simulator import generate_storyboard_simulation


def _load_env() -> None:
    """从 .env 加载环境变量 (不覆盖已存在的)。"""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _stem_path(image: str, override: str | None) -> Path:
    """推导输出文件族的主路径 (无扩展名)。"""
    if override:
        return Path(override).with_suffix("")
    if image.startswith("http://") or image.startswith("https://"):
        name = Path(urlparse(image).path).name
    else:
        name = Path(image).name
    stem = Path(name).stem or "output"
    return Path("data") / stem


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _user_options(args) -> dict:
    return {
        "platform": args.platform, "aspect_ratio": args.aspect_ratio,
        "duration": args.duration, "commercial_goal": args.commercial_goal,
        "slogan": args.slogan or "", "brand_name": args.brand_name or "",
    }


def _run_fast(args, features, stem: Path, ark_model, deepseek_model) -> int:
    """原流程: 特征 → 模版 → 一个最终 prompt。"""
    print("[2/3] 匹配分镜模版")
    template = match_template(features.get("category", ""), features.get("sub_category") or None)
    if not template:
        print(f"未匹配到模版: category={features.get('category')}", file=sys.stderr)
        return 1
    print(f"  → {template.get('template_name')} ({template.get('template_id')})")
    print("[3/3] 生成完整分镜提示词 (DeepSeek)")
    try:
        prompt = generate_final_prompt(features, template, model=deepseek_model)
    except DeepSeekError as e:
        print(f"提示词生成失败: {e}", file=sys.stderr)
        return 1
    txt_path = stem.with_suffix(".txt")
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(prompt, encoding="utf-8")
    _write_json(stem.with_suffix(".features.json"), features)
    print(f"\n分镜提示词已写入: {txt_path}")
    print(f"产品特征已写入: {stem.with_suffix('.features.json')}")
    return 0


def _run_explore(args, features, stem: Path, ark_model, deepseek_model) -> tuple[list, list, list, dict | None]:
    """explore: brief → candidates → scores → shortlist (+ 可选 storyboard)。"""
    opts = _user_options(args)
    print("[2/6] 构建创意 brief")
    brief = build_creative_brief(features, opts)
    _write_json(stem.with_suffix(".brief.json"), brief)

    print("[3/6] 匹配分镜模版 + 生成创意候选")
    template = match_template(features.get("category", ""), features.get("sub_category") or None)
    candidates = generate_creative_candidates(
        brief, template, num_candidates=args.num_candidates, model=deepseek_model
    )
    _write_json(stem.with_suffix(".candidates.json"), candidates)
    print(f"  → 生成 {len(candidates)} 个候选")

    print("[4/6] 评分")
    scores = score_creative_candidates(brief, candidates, model=deepseek_model)
    _write_json(stem.with_suffix(".scores.json"), scores)

    print("[5/6] shortlist")
    shortlisted = select_shortlist(
        candidates, scores, top_k=args.top_k, min_overall=args.min_score
    )
    _write_json(stem.with_suffix(".shortlist.json"), shortlisted)
    print(f"  → shortlist {len(shortlisted)} 个")

    sims = []
    if args.storyboard and shortlisted:
        print("[5.5/6] 关键帧预演 (storyboard)")
        for row in shortlisted:
            try:
                sim = generate_storyboard_simulation(brief, row["candidate"], model=deepseek_model)
                sims.append(sim)
            except DeepSeekError as e:
                print(f"  storyboard 失败 {row['candidate_id']}: {e}", file=sys.stderr)
        if sims:
            _write_json(stem.with_suffix(".storyboard.json"), sims)
    return candidates, scores, shortlisted, (sims if sims else None)


def _run_decision(args, features, stem: Path, ark_model, deepseek_model) -> int:
    """decision: explore → render_decision → output_package。"""
    candidates, scores, shortlisted, sims = _run_explore(
        args, features, stem, ark_model, deepseek_model
    )
    opts = _user_options(args)
    brief = build_creative_brief(features, opts)

    print("[6/6] render_decision + 最终 prompt")
    decision = make_render_decision(brief, shortlisted, sims or [], model=deepseek_model)
    _write_json(stem.with_suffix(".decision.json"), decision)

    if not decision.get("should_render"):
        print(f"\n⚠ 没有候选值得消耗视频积分: {decision.get('reason')}", file=sys.stderr)
        report = build_report_md(
            {"selected_candidate": {}, "score": {}, "render_decision": decision},
            all_candidates_count=len(candidates),
            rejected=[s for s in scores if s.get("render_recommendation") in ("reject", "revise")],
            shortlisted=shortlisted,
        )
        stem.with_suffix(".report.md").write_text(report, encoding="utf-8")
        return 0

    rec_id = decision.get("recommended_candidate_id")
    cand_by_id = {c.get("candidate_id"): c for c in candidates}
    score_by_id = {s.get("candidate_id"): s for s in scores}
    selected = cand_by_id.get(rec_id, shortlisted[0]["candidate"] if shortlisted else {})
    selected_score = score_by_id.get(rec_id, {})
    selected_sim = None
    if sims:
        selected_sim = next((s for s in sims if s.get("candidate_id") == rec_id), None)

    package = build_final_prompt_package(
        brief, selected, selected_score, selected_sim, decision,
        model=deepseek_model,
    )
    _write_json(stem.with_suffix(".package.json"), package)
    stem.with_suffix(".txt").write_text(package["xiaoyunque_prompt"], encoding="utf-8")

    rejected = [s for s in scores if s.get("render_recommendation") in ("reject", "revise")]
    report = build_report_md(
        package, all_candidates_count=len(candidates),
        rejected=rejected, shortlisted=shortlisted,
    )
    stem.with_suffix(".report.md").write_text(report, encoding="utf-8")

    print(f"\n最终提示词: {stem.with_suffix('.txt')}")
    print(f"决策报告: {stem.with_suffix('.report.md')}")
    print(f"完整包: {stem.with_suffix('.package.json')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="产品图 → 分镜提示词 (供小云雀人工测试)"
    )
    parser.add_argument("image", nargs="?", help="产品样例图本地路径或 URL")
    parser.add_argument("-o", "--output", default=None,
                        help="输出路径覆盖 (默认 data/<图片名>.txt)")
    parser.add_argument("--list-categories", action="store_true",
                        help="列出可用类目体系后退出")
    parser.add_argument("--mode", choices=["fast", "explore", "decision"], default="fast",
                        help="fast=原流程; explore=候选+评分+shortlist; "
                             "decision=完整流程+最终推荐 (推荐)")
    parser.add_argument("--num-candidates", type=int, default=8, help="创意候选数量")
    parser.add_argument("--top-k", type=int, default=3, help="shortlist 上限")
    parser.add_argument("--min-score", type=int, default=80, help="shortlist overall 门槛")
    parser.add_argument("--platform", default="douyin",
                        choices=["douyin", "xiaohongshu", "video_account", "tiktok", "youtube"])
    parser.add_argument("--aspect-ratio", default="9:16", choices=["9:16", "16:9", "1:1"])
    parser.add_argument("--duration", type=int, default=15, help="视频时长秒数")
    parser.add_argument("--commercial-goal", default="creative_ad",
                        choices=["brand_film", "creative_ad", "direct_response", "social_post"])
    parser.add_argument("--slogan", default=None, help="品牌 slogan (留空不捏造)")
    parser.add_argument("--brand-name", default=None, help="品牌名 (留空不捏造)")
    parser.add_argument("--storyboard", action="store_true",
                        help="启用关键帧预演 (默认关闭省成本, P2 将增强)")
    parser.add_argument("--ark-model", default=None, help="ARK Doubao 模型名覆盖")
    parser.add_argument("--deepseek-model", default=None, help="DeepSeek 模型名覆盖")
    args = parser.parse_args(argv)

    _load_env()

    if args.list_categories:
        for cat, subs in list_categories().items():
            print(f"{cat}: {'、'.join(subs)}")
        return 0

    if not args.image:
        parser.error("image is required (unless --list-categories)")

    print(f"[1/6] 提取产品特征 (Doubao 多模态): {args.image}")
    try:
        features = extract_features(args.image, model=args.ark_model)
    except LLMError as e:
        print(f"特征提取失败: {e}", file=sys.stderr)
        return 1
    print(f"  → 商品名称={features.get('product_name')} category={features.get('category')}")

    stem = _stem_path(args.image, args.output)

    if args.mode == "fast":
        return _run_fast(args, features, stem, args.ark_model, args.deepseek_model)
    if args.mode == "explore":
        _run_explore(args, features, stem, args.ark_model, args.deepseek_model)
        return 0
    return _run_decision(args, features, stem, args.ark_model, args.deepseek_model)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: PASS (3 tests: fast, decision, explore)

- [ ] **Step 5: Run full test suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "Add --mode fast/explore/decision CLI with full artifact output"
```

---

## Task 10: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README to describe new workflow**

Replace the entire contents of `README.md` with:
```markdown
# advertise_agent

产品样例图 → 低成本创意迭代器。在消耗小云雀/Seedance 视频积分之前，先用 LLM
生成多个创意候选、结构化评分、筛选 shortlist，最终只把**最值得生成的一版**交给
小云雀——提高每一次视频积分的命中率，而不是生成更多视频。

## 数据流

```
产品样例图
 ─► Doubao 提取特征
 ─► 创意 brief (规则)
 ─► 创意搜索 (8 个差异化候选, DeepSeek)
 ─► 结构化评分 (9 维 + 加权 overall)
 ─► shortlist (规则筛选, 可拒绝低质量创意)
 ─► (可选) 关键帧预演 storyboard
 ─► render_decision (是否值得花一次视频积分)
 ─► 最终 prompt 包 + 决策报告
 ─► (人工) 上传小云雀
```

## 模式

```bash
# fast (默认, 原流程): 一个最终 prompt
python main.py product.jpg --mode fast

# explore: 8 候选 → 评分 → shortlist, 不生成最终 prompt
python main.py product.jpg --mode explore

# decision (推荐): 完整流程, 只推荐 1 个最值得花积分的方案
python main.py product.jpg --mode decision \
  --num-candidates 8 --top-k 3 \
  --platform douyin --aspect-ratio 9:16 --duration 15
```

原命令保持兼容: `python main.py product.jpg` 与 `--list-categories` 行为不变。

## 配置

复制 `.env.example` 为 `.env`，填入两个 key：
```
ARK_API_KEY=your-ark-key        # 火山方舟 Doubao 多模态 (特征提取)
DEEPSEEK_API_KEY=your-deepseek  # DeepSeek (创意/评分/决策/prompt)
```

## 输出 (data/<图片名>.*)

| 文件 | 说明 |
|------|------|
| `.features.json` | 产品特征 (Doubao) |
| `.brief.json` | 创意 brief |
| `.candidates.json` | N 个创意候选 |
| `.scores.json` | 每候选 9 维评分 + overall |
| `.shortlist.json` | 入围候选 + render 资格 |
| `.storyboard.json` | 关键帧预演 (`--storyboard` 启用, 默认关闭) |
| `.decision.json` | 是否值得花积分 + 失败修正建议 |
| `.package.json` | 完整机器可读包 |
| `.txt` | 可直接粘贴到小云雀的最终 prompt |
| `.report.md` | 决策报告 (候选排序/淘汰原因/推荐理由/上传检查) |

## 常用参数

```
--mode {fast,explore,decision}   默认 fast, 推荐 decision
--num-candidates 8               创意候选数
--top-k 3                        shortlist 上限
--min-score 80                   shortlist overall 门槛
--platform douyin                douyin|xiaohongshu|video_account|tiktok|youtube
--aspect-ratio 9:16              9:16|16:9|1:1
--duration 15                    视频时长秒
--commercial-goal creative_ad    brand_film|creative_ad|direct_response|social_post
--slogan "" --brand-name ""      品牌资产 (留空不捏造)
--storyboard                     启用关键帧预演 (默认关闭省成本)
```

## 结构

```
main.py                      CLI 入口 (fast/explore/decision)
core/
  llm_client.py              ARK Doubao 多模态 client
  extract_features.py        图 → 特征 JSON
  storyboard.py              模版匹配 + scaffold
  deepseek_client.py         DeepSeek chat client
  generate_prompt.py         fast 模式最终 prompt
  json_utils.py              DeepSeek JSON 调用 + 容错解析
  brief.py                   特征 → 创意 brief (规则)
  creative_search.py         brief → N 个候选 (LLM)
  creative_scoring.py        候选 → 9 维评分 + overall
  shortlist.py               评分 → shortlist (规则, P1 核心)
  storyboard_simulator.py    候选 → 关键帧 prompt (最小实现)
  render_decision.py         shortlist → 是否花积分 (规则+LLM)
  output_package.py          最终 prompt + 决策报告
templates/  prompts/  schemas/  tests/  data/
```

零外部依赖，仅用 Python 标准库。测试: `python -m unittest discover -s tests -v`
```

- [ ] **Step 2: Verify README renders / no broken paths**

Run: `ls core/ prompts/ schemas/ tests/`
Expected: all referenced directories/files exist.

- [ ] **Step 3: Run full test suite one more time**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Update README for creative iterator workflow"
```

---

## Self-Review

**Spec coverage check (P0 + P1 scope):**
- 总体架构 8 步扩展: brief ✓ (T2), creative_search ✓ (T3), creative_scoring ✓ (T4), shortlist ✓ (T5), storyboard_simulator ✓ (T6, minimal/opt-in), render_decision ✓ (T7), final_prompt_package ✓ (T8) — covered.
- 兼容性 (原 CLI 用法 + `--mode`): ✓ T9, default `fast` preserves original.
- 新增目录/文件: core/* ✓, prompts/* ✓, schemas/* ✓, data/ outputs ✓ (gitignored, fine).
- 核心数据结构 5 个: all defined as contracts + normalized in code ✓.
- 模块签名: all match spec (`build_creative_brief`, `generate_creative_candidates`, `score_creative_candidate(s)`, `select_shortlist`, `generate_storyboard_simulation`, `make_render_decision`, `build_final_prompt_package`) ✓.
- 评分维度 + 权重: exact match ✓ (T4).
- shortlist 规则 (overall 排序 / feasibility 降级 / product_clarity<70 / top_k): ✓ (T5).
- CLI 参数 (`--mode`, `--num-candidates`, `--top-k`, `--min-score`, `--platform`, `--aspect-ratio`, `--duration`, `--commercial-goal`, `--slogan`, `--brand-name`, `--no-storyboard`): all present ✓ (T9).
- 输出文件族: all 10 artifacts ✓ (T9 decision test asserts all exist).
- report.md 必答 6 问: ✓ (T8 `build_report_md` answers 候选数/淘汰/shortlist/推荐/理由/检查/失败修正).
- .txt 可直接粘贴: ✓ (T8 prompt + T9 test asserts content).
- 思维链路 distillation: creative_search prompt covers 产品真相/用户动机/场景张力/视觉隐喻/hook/叙事脊柱/产品露出/生成可行性/商业目标 ✓; render_decision covers 积分预算 ✓.
- 不要做 8 条: 不接小云雀 ✓, 不爬虫 ✓, 不承诺 ROI ✓, 不塞 main.py ✓ (split into 7 modules), 不删 fast path ✓, 不引入框架 ✓, 保留 JSON 中间产物 ✓, LLM 输出可解析 (json_utils 容错) ✓.
- 代码风格: stdlib only ✓, docstrings ✓, `ensure_ascii=False, indent=2` ✓ (`_write_json`), JSON 解析失败处理 ✓ (`JSONParseError`), 轻量测试 ✓ (9 test files), README 更新 ✓ (T10).

**Placeholder scan:** no TBD/TODO; every code step has complete code.

**Type consistency check:** `candidate_id` string `C001` format consistent across creative_search→scoring→shortlist→render_decision→output_package ✓. `scores` dict key names identical in scoring/shortlist/output_package (`overall`, `seedance_feasibility`, `product_clarity`) ✓. `render_recommendation` enum `reject|revise|shortlist|render` consistent in scoring + shortlist ✓. `eligible_for_render`/`ineligible_reasons` consistent shortlist→render_decision ✓. `recommended_candidate_id` consistent render_decision→output_package→report ✓.

**Deferred (P2–P4, intentionally out of scope):** storyboard quality polish, report polish, hotspot search, brand memory, feedback loop, web UI, auto-upload. Decision mode skips storyboard by default (opt-in via `--storyboard`); P2 will deepen storyboard prompts and may flip default on.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-29-creative-iterator-p0-p1.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
