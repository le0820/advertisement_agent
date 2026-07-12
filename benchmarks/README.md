# advertisement_agent Benchmarks

This directory contains a lightweight EdgeBench-style MVP benchmark pack for
the creative video workflow. It is intentionally small: no Docker, no external
model calls, and no network access are required for the included judges.

## Run

```bash
python benchmarks/run_bench.py --task all
python benchmarks/run_bench.py --task ad_score_hard_gates --json
```

Each task has:

- `task.json`: task contract and SForge-compatible metadata.
- `judge/eval.py`: hidden judge logic that prints a structured JSON result.

The judges evaluate the current repository as the submission by default. Pass a
different checkout or artifact directory with `--submission PATH`.

## MVP Tasks

- `ad_score_hard_gates`: fashion scoring hard gates for worn display, occasion,
  silhouette, and render recommendation downgrade.
- `ad_shortlist_selection`: shortlist ordering where render-eligible candidates
  beat higher-scoring but unsafe candidates.
- `ad_brand_film_spec_contract`: downstream `brand-film-spec` prompt/package
  contract for Xiaoyunque/Seedance.
- `ad_forbidden_claim_compliance`: forbidden-claim propagation through the brief
  and creative prompt surface.

The output schema follows SForge's `structured_json` convention: `valid`,
`score`, `pass_rate`, `summary`, `details`, and `metrics`.
