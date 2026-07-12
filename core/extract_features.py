"""Legacy API adapter for the v2 product-understanding artifact.

The Codex harness reads images directly. This module remains for compatibility
with the old external VLM mode and normalizes its response into the same v2
contract used by Codex.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .category_profiles import build_taxonomy, list_category_taxonomy
from .llm_client import LLMError, chat_with_image


_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_features.txt"


def _load_categories_block() -> str:
    lines = []
    for category, subcategories in list_category_taxonomy().items():
        lines.append(f"- {category}：{'、'.join(subcategories)}")
    return "\n".join(lines)


def _build_prompt() -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{categories_block}", _load_categories_block())


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMError(f"no JSON object in LLM output: {text[:300]}")
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"invalid JSON from LLM: {exc}; raw={text[:300]}") from exc
    if not isinstance(value, dict):
        raise LLMError("product understanding output must be an object")
    return value


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    text = str(value).strip()
    return [text] if text else []


def _normalize_product_understanding(
    raw: dict[str, Any],
    image: str | Path,
) -> dict[str, Any]:
    identity = raw.get("product_identity") if isinstance(raw.get("product_identity"), dict) else {}
    product_name = str(raw.get("product_name") or identity.get("product_name") or "")
    dense_caption = str(raw.get("dense_caption") or "")
    incoming_taxonomy = raw.get("taxonomy") if isinstance(raw.get("taxonomy"), dict) else {}
    raw_category = str(incoming_taxonomy.get("primary_category") or raw.get("category") or "")
    raw_subcategory = str(incoming_taxonomy.get("subcategory") or raw.get("sub_category") or "")
    taxonomy = build_taxonomy(
        raw_category,
        raw_subcategory,
        text=f"{product_name} {dense_caption}",
        status=incoming_taxonomy.get("subcategory_status"),
        confidence=incoming_taxonomy.get("subcategory_confidence"),
        evidence=_as_list(incoming_taxonomy.get("subcategory_evidence")),
        extension=incoming_taxonomy.get("subcategory_extension")
        if isinstance(incoming_taxonomy.get("subcategory_extension"), dict)
        else None,
    )

    hypotheses = raw.get("commercial_hypotheses")
    if not isinstance(hypotheses, dict):
        hypotheses = {}
    selling_points = _as_list(raw.get("selling_points") or hypotheses.get("selling_points"))
    target_audiences = _as_list(hypotheses.get("target_audiences"))
    if not target_audiences:
        target_audiences = _as_list(raw.get("target_audience"))

    visual_facts = raw.get("visual_facts") if isinstance(raw.get("visual_facts"), dict) else {}
    normalized_visual_facts = {
        key: _as_list(visual_facts.get(key))
        for key in (
            "product_form",
            "colors",
            "visible_material_appearance",
            "packaging",
            "visible_details",
            "usage_cues",
        )
    }
    truth = raw.get("truth_boundaries") if isinstance(raw.get("truth_boundaries"), dict) else {}
    truth_boundaries = {
        key: _as_list(truth.get(key))
        for key in ("observed", "inferred", "unknown", "forbidden_inferences")
    }
    source_images = raw.get("source_images") if isinstance(raw.get("source_images"), list) else []
    if not source_images:
        source_images = [{
            "source_id": "IMG01",
            "role": "primary_product",
            "source": str(image),
            "observations": list(truth_boundaries["observed"]),
        }]

    result = {
        "schema_version": "2.0",
        "source_images": source_images,
        "product_identity": {
            "product_name": product_name,
            "visible_brand_text": _as_list(identity.get("visible_brand_text")),
            "visible_product_text": _as_list(identity.get("visible_product_text")),
            "variant_or_set": str(identity.get("variant_or_set") or ""),
        },
        "taxonomy": taxonomy,
        "visual_facts": normalized_visual_facts,
        "commercial_hypotheses": {
            "selling_points": selling_points,
            "target_audiences": target_audiences,
            "usage_scenes": _as_list(hypotheses.get("usage_scenes")),
            "consumer_tensions": _as_list(hypotheses.get("consumer_tensions")),
        },
        "truth_boundaries": truth_boundaries,
        "dense_caption": dense_caption,
        # Flattened aliases keep the old API path and older scripts functional.
        "category": taxonomy["primary_category"],
        "sub_category": taxonomy["subcategory"],
        "product_name": product_name,
        "selling_points": selling_points,
        "target_audience": target_audiences[0] if target_audiences else "",
        "distribution_scenarios": ["douyin", "tiktok", "youtube"],
    }
    if raw_category and raw_category != result["category"]:
        result["category_conflict"] = {
            "original_category": raw_category,
            "corrected_category": result["category"],
            "reason": "legacy or unsupported category normalized into the three-category profile registry",
            "matched_keywords": taxonomy.get("subcategory_evidence", []),
        }
    return result


def extract_features(
    image: str | Path,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    prompt = _build_prompt()
    text = chat_with_image(image, prompt, model=model, api_key=api_key)
    return _normalize_product_understanding(_parse_json(text), image)
