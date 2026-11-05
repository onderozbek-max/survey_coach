# Integration engine reconciliation

Owner: code-puppy-41d152

## Scope and investigation

- [x] Inspected the supplied full-suite failure log at `/var/folders/cy/m9q20js10t9bvtd05b9lk35w0000gp/T/shell_bg_5namxysd.log`, then reproduced owned failures with an explicit `pytest --lf` file subset (13 failures, 70 deselected).
- [x] Read each affected contract and traced B7 through reader-image check, review merge, scorecard, scope projection, and CLI. Read demo exporter and cache implementation before regenerating output.
- [x] Kept all image, reading-worker, authored UI assets, and other workers' integration tests untouched. The only site change is explicitly owned generated `site/data.js`.

## Root causes and decisions

1. **AI review tests (3 failures):** reader-only unloaded-image observations intentionally produce an unassessed B7 worth-improving finding. B7 must remain pending even with an all-clear text judge; it is not a second confirmed must-fix. Updated pending sets and strengthened assertions that B1 sorts first and B7 cannot be resolved by AI. Kept exact score/coverage arithmetic and code-evidence preservation assertions.
2. **Enrich scope (4 failures) and chapters disclosure (2 failures):** B7 `assessed=False` reduces applicable checked counts from 22/34 to 21/33. Total applicable count remains 48. Tests now also require B7 pending state and its title in unchecked/disclosure copy. Missing semantic blockers remain absent rather than fabricated passes.
3. **Judge ownership (1 failure):** pending launch checks can require non-AI verification: B5 calibration or B7 actual-image loading. Both remain outside AI ownership; B7 must carry unassessed worth-improving reader evidence.
4. **Review and CLI fixture expectations (2 failures):** the synthetic flawed fixture still needs work with citations, but has zero confirmed open blockers and pending B7. Updated expectations without removing substantive citation, provisional-state, or readability checks.
5. **Actual CLI bug discovered while tracing:** render subtracted unchecked points from an already earned-only score, showing negative earned points, and included N/A points in checked coverage. New regression failed before the fix; CLI now uses `card.score` and `card.checked_points` directly. Timing copy now labels uncalibrated estimated member completion, distinguishes crawl/load time, requests a timed pilot, and discloses uncertain paths.
6. **Recommendation-quality saved-history test (1 failure):** stale assertion required an unverified duration promise. Now requires no time rewrite for the uncalibrated snapshot and a timed-run recommendation. Existing invalid-decision reopening, template removal, stable fingerprint/evidence, idempotency, stored-history equality, and invalid-pick rejection assertions remain intact. Repository use is strictly `:memory:` synthetic test data.
7. **Copy guard (1 failure):** exact phrase `not a guarantee` is a disclaimer, not an outcome claim. Added regression first (observed fail), then allowed only the locally negated `guarantee` match. Same-line `will finish` and positive `guarantee` still fail; no blanket line or file exemption.
8. **Demo stale data (1 failure):** regenerated `site/data.js` from the two committed made-up fixtures and pinned human-reviewed historical AI answers, re-grounded through the current engine. Exporter normal mode uses CacheOnlyProvider (raises instead of networking); no `--ai-refresh`, live provider, actual DB, or user data. This is not a fresh AI assessment.

## Verification

Initial owned failure reproduction:

```sh
.venv/bin/python -m pytest --lf tests/test_ai_review.py tests/test_enrich_contract.py tests/test_judge_schemas.py tests/test_review.py tests/test_recommendation_quality.py tests/test_copy_guard.py tests/test_demo_export.py -q
```

Two new regressions (CLI score and disclaimer false positive) each failed for the intended reason before implementation.

Safe offline regeneration:

```sh
.venv/bin/python -m surveycoach.demo_export
```

Final explicit focused subset (not the full suite):

```sh
.venv/bin/python -m pytest --lf --last-failed-no-failures=all tests/test_ai_review.py tests/test_enrich_contract.py tests/test_judge_schemas.py tests/test_review.py tests/test_recommendation_quality.py tests/test_copy_guard.py tests/test_demo_export.py tests/test_chapters_ui.py -q
```

Result: **108 passed in 12.04s**, one existing Starlette/httpx deprecation warning. Earlier iterative `--lf` runs also passed 7 and then 2 selected failures; final command reran all tests in the explicit owned subset once no failures remained there. `git diff --check` passed.

No full-suite rerun, live calls, actual database changes, delegation, push, image-file edits, reading-worker edits, or authored UI changes. Parent owns workspace image assertion updates; another worker owns remaining UI integration failures. Commit uses `--only` owned paths and preserves staged progress and other workers' changes.
