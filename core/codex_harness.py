"""Codex-controlled brand-film-spec harness.

This module intentionally does not call external LLM/VLM providers. It packages
the repository's prompts, templates, schemas, deterministic rules, and requested
image inputs into a run context that the Codex thread can execute as the model
hub.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .category_profiles import (
    REFERENCE_VIDEO_MANIFEST_PATH,
    list_category_taxonomy,
    load_category_profiles,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HARNESS_PATH = ROOT / "harness" / "codex_brand_film_spec.json"

_REQUIRED_TOP_LEVEL = (
    "harness_id",
    "version",
    "owner_agent",
    "model_policy",
    "category_framework",
    "input_contract",
    "stages",
    "artifacts",
    "video_generation_port",
)


def load_codex_harness(path: str | Path | None = None) -> dict[str, Any]:
    """Load and lightly validate the Codex harness definition."""
    harness_path = Path(path) if path is not None else DEFAULT_HARNESS_PATH
    with open(harness_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    missing = [key for key in _REQUIRED_TOP_LEVEL if key not in data]
    if missing:
        raise ValueError(f"invalid Codex harness, missing: {', '.join(missing)}")

    stages = data.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("invalid Codex harness, stages must be a non-empty list")
    stage_ids = [stage.get("id") for stage in stages if isinstance(stage, dict)]
    if len(stage_ids) != len(stages) or any(not sid for sid in stage_ids):
        raise ValueError("invalid Codex harness, every stage needs an id")
    if len(stage_ids) != len(set(stage_ids)):
        raise ValueError("invalid Codex harness, duplicate stage ids")

    framework = data.get("category_framework") or {}
    supported = framework.get("supported_primary_categories")
    taxonomy = list_category_taxonomy()
    if supported != list(taxonomy):
        raise ValueError("Codex harness category list does not match category profiles")
    load_category_profiles()

    schema_map = data.get("artifacts", {}).get("schema_map", {})
    for schema_ref in schema_map.values():
        schema_path = ROOT / str(schema_ref).removesuffix("[]")
        if not schema_path.exists():
            raise ValueError(f"Codex harness schema does not exist: {schema_ref}")
    return data


def normalize_image_inputs(
    primary_image: str | Path,
    reference_images: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> list[dict[str, Any]]:
    """Return a stable image manifest for Codex-owned visual inspection."""
    images: list[dict[str, Any]] = [
        {
            "source_id": "IMG01",
            "role": "primary_product",
            "source": str(primary_image),
            "order": 1,
        }
    ]
    for index, image in enumerate(reference_images or [], 2):
        images.append({
            "source_id": f"IMG{index:02d}",
            "role": "alternate_angle",
            "source": str(image),
            "order": index,
        })
    return images


def _stem_from_source(source: str | Path) -> str:
    source_s = str(source)
    if source_s.startswith(("http://", "https://")):
        name = Path(urlparse(source_s).path).name
    else:
        name = Path(source_s).name
    return Path(name).stem or "output"


def _clean_user_options(options: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in options.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        cleaned[key] = value
    if "duration" in cleaned and "duration_seconds" not in cleaned:
        cleaned["duration_seconds"] = cleaned.pop("duration")
    return cleaned


def _stage_contracts(harness: dict[str, Any]) -> list[dict[str, Any]]:
    contracts = []
    for stage in harness["stages"]:
        contract = {
            "id": stage["id"],
            "owner": stage.get("owner", ""),
            "inputs": stage.get("inputs", []),
            "outputs": stage.get("outputs", []),
        }
        if stage.get("artifact_suffix"):
            contract["artifact_suffix"] = stage["artifact_suffix"]
        if stage.get("artifact_suffixes"):
            contract["artifact_suffixes"] = stage["artifact_suffixes"]
        if stage.get("schema"):
            contract["schema"] = stage["schema"]
        contracts.append(contract)
    return contracts


def _expected_artifacts(output_stem: Path, harness: dict[str, Any]) -> list[dict[str, str]]:
    suffixes = harness.get("artifacts", {}).get("file_suffixes", [])
    return [
        {"suffix": suffix, "path": str(output_stem.with_suffix(suffix))}
        for suffix in suffixes
    ]


def build_codex_run_context(
    primary_image: str | Path,
    *,
    reference_images: list[str | Path] | tuple[str | Path, ...] | None = None,
    user_options: dict[str, Any] | None = None,
    output_stem: str | Path | None = None,
    harness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a machine-readable packet for the Codex branch workflow.

    The packet is not an API call request. It is an execution contract for the
    Codex thread: image inputs, user options, harness stages, output paths, and
    the pluggable video-generation boundary.
    """
    loaded = harness or load_codex_harness()
    stem = (
        Path(output_stem).with_suffix("")
        if output_stem is not None
        else Path("data") / _stem_from_source(primary_image)
    )
    options = _clean_user_options(user_options or {})
    profiles = load_category_profiles()
    with open(REFERENCE_VIDEO_MANIFEST_PATH, "r", encoding="utf-8") as handle:
        reference_manifest = json.load(handle)

    return {
        "run_type": "codex_thread_controlled_brand_film_spec",
        "harness_id": loaded["harness_id"],
        "harness_version": loaded["version"],
        "owner_agent": loaded["owner_agent"],
        "model_policy": loaded["model_policy"],
        "category_framework": loaded["category_framework"],
        "input_contract": loaded["input_contract"],
        "image_inputs": normalize_image_inputs(primary_image, reference_images),
        "user_options": options,
        "available_categories": list_category_taxonomy(),
        "category_profile_registry": {
            "framework_id": profiles["framework_id"],
            "version": profiles["version"],
            "path": loaded["category_framework"]["profiles"],
            "taxonomy_contract": profiles["taxonomy_contract"],
        },
        "reference_evidence": {
            "manifest_id": reference_manifest["manifest_id"],
            "version": reference_manifest["version"],
            "path": loaded["category_framework"]["reference_manifest"],
            "sample_count": len(reference_manifest["samples"]),
            "analysis_scope": reference_manifest["analysis_method"]["scope"],
        },
        "stage_order": [stage["id"] for stage in loaded["stages"]],
        "stage_contracts": _stage_contracts(loaded),
        "expected_artifacts": _expected_artifacts(stem, loaded),
        "artifact_schema_map": loaded["artifacts"].get("schema_map", {}),
        "video_generation_port": loaded["video_generation_port"],
        "operator_notes": [
            "Codex mode must not call ARK, DeepSeek, or any other external LLM/VLM client.",
            "Use the supplied product images as product-fact ground truth.",
            "Resolve only 美妆个护 / 食品饮料 / 服饰配件 as primary categories.",
            "Preserve subcategory_status and subcategory_extension when no reserved subcategory fits.",
            "Use reference samples for proof order and pacing, never as copyable creative assets.",
            "The video renderer is replaceable and must not rewrite the accepted spec.",
        ],
    }


def write_codex_run_context(context: dict[str, Any], path: str | Path) -> Path:
    """Write a Codex run context JSON file and return its path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
