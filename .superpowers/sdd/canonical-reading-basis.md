# Canonical reading basis integration

Owner: code-puppy-2da64b. Integrates preview consumer `b51036e`; backend/tests and generated synthetic data only.

## Completed

- [x] Read preview coordination contract and existing timing/enrichment/demo paths.
- [x] RED: new producer/cross-layer tests failed **12 / passed 1**, due to absent basis, missing canonical function, and real JS returning null for enriched pages.
- [x] Extracted `timing.reading_basis(page, constants)` from existing exact page-local overlap subtraction. Timing now sums these exact fields; there is no parallel producer algorithm or JS deduplication.
- [x] Basis exports `{seconds_per_word, fields:[{text, question_id?}]}`. Question/help/options/rows/scale labels stay independent question-scoped fields. Unmatched intro/raw prose stays page-scoped. Container overlap, exact copies, whole-line answer matching and legitimate extra occurrences retain existing conservative timing behavior.
- [x] `server.present.enrich` adds basis only to a detached serialized snapshot. It recomputes and replaces stale/injected basis every time. `Page`/`SurveySnapshot` models, stored capture schema, content/review hashes and AI cache identity are unchanged.
- [x] Demo export already uses `enrich`; every made-up fixture page therefore gets the same basis without a second exporter path.
- [x] Regenerated `site/data.js` through default offline cache-only exporter (no `--ai-refresh`). Output also incorporates the preceding backend audit's scoring/copy corrections; no manual data edits.
- [x] GREEN: **209 passed in 4.78s**, one existing Starlette/httpx warning. Named-path whitespace checks pass; changed production sources are 115/170 lines.

## Evidence covered

Eight control kinds (single/multi/dropdown/grid single/grid multi/rating/slider/ranking); actual structured fields fed back as redundant raw captures; timing reading-component parity; unique concept prose; overlap across intro/raw/question; legitimate extra raw occurrences; real model.js + energy.js scoped replacements including dropdown answers, grid rows and scale labels; nondefault rate; synthetic demo pages; no mutation; idempotency; stale basis replacement; hash/model exclusion. Unenriched legacy pages continue returning null in JS, not false zero.

```sh
.venv/bin/python -m surveycoach.demo_export
.venv/bin/python -m pytest tests/test_canonical_reading_basis.py tests/test_preview_reading_projection.py tests/test_timing.py tests/test_timing_welcome_fixes.py tests/test_root_cause_invariants.py tests/test_demo_export.py tests/test_enrich_contract.py tests/test_present.py tests/test_signals.py tests/test_demo_structured_suggestions.py tests/test_review_projection.py -q
```

## Boundaries / handoff

- Parent owns `app.js` available/unavailable formatter integration; no authored site JS or loading/CSS files edited.
- Basis measures captured reading only, not verified source edits, total completion savings, route completion or quality reassessment. Conservative flattened answer/prose handling is unchanged.
- Raw legacy captures without projection still have no basis; enrichment can derive current evidence when a valid capture is available. No legacy zero fabricated.
- No external/live calls, actual database access, new vendor responses, full suite, delegation or push. Existing tests use synthetic test-only repository state where needed. Unrelated staged progress and parent edits remain excluded from the named-path commit.
