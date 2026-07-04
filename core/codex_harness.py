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

from .storyboard import list_categories

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HARNESS_PATH = ROOT / "harness" / "codex_brand_film_spec.json"

_REQUIRED_TOP_LEVEL = (
    "harness_id",
    "version",
    "owner_agent",
    "model_policy",
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
    return data


def normalize_image_inputs(
    primary_image: str | Path,
    reference_images: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> list[dict[str, Any]]:
    """Return a stable image manifest for Codex-owned visual inspection."""
    images: list[dict[str, Any]] = [
        {
            "role": "primary_product",
            "source": str(primary_image),
            "order": 1,
        }
    ]
    for index, image in enumerate(reference_images or [], 2):
        images.append({
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

    return {
        "run_type": "codex_thread_controlled_brand_film_spec",
        "harness_id": loaded["harness_id"],
        "harness_version": loaded["version"],
        "owner_agent": loaded["owner_agent"],
        "model_policy": loaded["model_policy"],
        "input_contract": loaded["input_contract"],
        "image_inputs": normalize_image_inputs(primary_image, reference_images),
        "user_options": options,
        "available_categories": list_categories(),
        "stage_order": [stage["id"] for stage in loaded["stages"]],
        "stage_contracts": _stage_contracts(loaded),
        "expected_artifacts": _expected_artifacts(stem, loaded),
        "video_generation_port": loaded["video_generation_port"],
        "operator_notes": [
            "Codex mode must not call ARK, DeepSeek, or any other external LLM/VLM client.",
            "Use the supplied product images as product-fact ground truth.",
            "Use prompts, templates, schemas, and deterministic rules as harness assets.",
            "The final video renderer is replaceable; only the brand-film-spec contract is stable.",
        ],
    }


def write_codex_run_context(context: dict[str, Any], path: str | Path) -> Path:
    """Write a Codex run context JSON file and return its path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
