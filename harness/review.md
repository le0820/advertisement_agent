# Harness Review: Codex Model Hub

## Current Design

The current project is valuable as a low-cost creative iterator, but its harness is not a single harness. The model routing is embedded across CLI code and modules:

- `core/llm_client.py` uses ARK/Doubao for image feature extraction and scoring.
- `core/deepseek_client.py` uses DeepSeek for creative candidates, render decisions, and final spec writing.
- `main.py` wires the model choices directly into the runtime flow.
- Prompts, schemas, templates, shortlist rules, and reports are useful project assets, but they are mixed with provider-specific execution.

This creates a fragmented creative authority: one model reads the product, another invents routes, another judges feasibility, and another writes the final `brand-film-spec`. For the Codex branch workflow, that is the wrong split. The user is already interacting with Codex and can send one or more product images directly into the thread, so Codex should be the model hub.

## Problems To Fix

- Product truth can drift between VLM extraction, creative writing, scoring, and final spec generation.
- Model-specific parameters leak into the user workflow (`--ark-model`, `--deepseek-model`, `--score-model`) even when the real desired interaction is "send images to Codex and get a spec."
- Video generation is treated as the next manual step rather than a clean adapter boundary.
- Optional previsualization exists as JSON prompts, but there is no harness-level place to plug in image generation assets.

## Assets To Preserve

- `templates/storyboard_templates.json` as category and creative-reference material.
- `prompts/*.txt` as stage instructions for Codex to read and apply.
- `schemas/*.json` as artifact contracts.
- `core/brief.py`, `core/creative_scoring.py`, and `core/shortlist.py` rules as deterministic guardrails.
- The artifact family: `.features.json`, `.brief.json`, `.candidates.json`, `.scores.json`, `.shortlist.json`, `.decision.json`, `.package.json`, `.brand-film-spec.md`, `.report.md`.

## Target Design

The Codex branch should use this split:

```
user product image(s)
  -> Codex model hub
  -> repository prompts/templates/schemas/rules as harness assets
  -> brand-film-spec + package + report
  -> pluggable video renderer adapter
```

Codex owns all semantic model work:

- image understanding
- product fact extraction
- creative candidate generation
- scoring judgment
- render decision
- final spec writing
- optional imagegen keyframe probes

The repository owns only stable contracts and deterministic helpers:

- schema shape
- category/template references
- score-weight definition
- shortlist eligibility rules
- artifact naming
- renderer adapter boundary

## Codex-Compatible Harness

The new source of truth is `harness/codex_brand_film_spec.json`.

`python main.py product.jpg --mode codex` does not run a provider model. It writes a `.codex-run.json` context packet that tells Codex which images, options, stages, categories, artifacts, and video-render port apply. In the normal desktop workflow, the user can skip the CLI packet and simply send images in the Codex thread; Codex should still follow the same harness.

## Video Generation Boundary

The costly video generation step is now a port:

- input: `.brand-film-spec.md`, `.package.json`, optional keyframe assets
- default adapter: manual Seedance upload
- future adapters: Seedance API, Kling, Runway, Veo, or another video agent

Renderers should not rewrite creative direction. They execute the accepted spec and return outputs or failure telemetry. Retry and replacement decisions come back to Codex through the same `render_decision` logic.
