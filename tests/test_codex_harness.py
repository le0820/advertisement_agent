from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.codex_harness import (
    build_codex_run_context,
    load_codex_harness,
    normalize_image_inputs,
    write_codex_run_context,
)


class TestCodexHarness(unittest.TestCase):
    def test_loads_harness_with_codex_as_owner(self):
        harness = load_codex_harness()

        self.assertEqual(harness["harness_id"], "codex_brand_film_spec")
        self.assertEqual(harness["owner_agent"]["id"], "codex")
        self.assertEqual(
            harness["model_policy"]["external_llm_vlm_runtime"],
            "disabled_by_default",
        )
        self.assertIn("video_generation_port", harness)

    def test_normalizes_multiple_images(self):
        images = normalize_image_inputs("hero.jpg", ["side.jpg", "macro.jpg"])

        self.assertEqual(images[0]["role"], "primary_product")
        self.assertEqual(images[0]["source"], "hero.jpg")
        self.assertEqual(images[1]["role"], "alternate_angle")
        self.assertEqual(images[2]["order"], 3)

    def test_build_context_has_stage_and_artifact_contracts(self):
        context = build_codex_run_context(
            "hero.jpg",
            reference_images=["macro.jpg"],
            user_options={
                "platform": "douyin",
                "aspect_ratio": "9:16",
                "duration": 15,
                "commercial_goal": "brand_film",
                "slogan": "",
            },
            output_stem="data/hero",
        )

        self.assertEqual(context["owner_agent"]["id"], "codex")
        self.assertIn("feature_extraction", context["stage_order"])
        self.assertIn("brand_film_spec", context["stage_order"])
        self.assertEqual(len(context["image_inputs"]), 2)
        self.assertEqual(context["user_options"]["commercial_goal"], "brand_film")
        self.assertEqual(context["user_options"]["duration_seconds"], 15)
        self.assertNotIn("duration", context["user_options"])
        self.assertNotIn("slogan", context["user_options"])
        paths = [row["path"] for row in context["expected_artifacts"]]
        self.assertIn("data/hero.brand-film-spec.md", paths)
        self.assertEqual(
            context["video_generation_port"]["default_adapter"],
            "manual_seedance_upload",
        )

    def test_writes_context(self):
        context = build_codex_run_context("hero.jpg", output_stem="hero")
        with tempfile.TemporaryDirectory() as d:
            out = write_codex_run_context(context, Path(d) / "hero.codex-run.json")

            self.assertTrue(out.exists())
            self.assertIn("codex_brand_film_spec", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
