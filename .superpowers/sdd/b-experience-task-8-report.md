# Part B Task 8 — Home

Base: `06f3551`. Required commit: `Redesign Home around one input and one promise`.

## Checklist
- [x] Read Task 8 brief first; activate living-design (existing vanilla exemption, no scaffold) and executing-plans.
- [x] Focused RED before implementation: 5 expected failures.
- [x] Implement Home, accessible data-handling dialog, supplied-signal cards and actual-job reading state.
- [x] Focused GREEN and full nonlive GREEN before commit.
- [x] Include report in required local commit; no push.

## Changes
- Exact honest hero and one essential test-link/AI/test-response notice; one primary Check survey button. Sample remains a secondary, network-free flow.
- Three former trust cards and pilot note moved into a labelled native modal dialog. Keyboard activation, Tab/Shift+Tab wrapping, Escape, explicit Close and focus return are tested. Hidden dialog is absent from the default accessibility view.
- Slim icon-bearing See / Improve / Share narrative replaces the steps grid. Example uses one-shot 360ms CSS strike/insertion animation; reduced motion disables animation and transitions.
- Whole-card links lead to `#overview`, contain one status pill, title fallback, six supplied signal symbols with a combined textual accessible label and Version/relative-time metadata. No checked-points copy or nested tab stops. Safe text nodes and encoded IDs preserve markup safety.
- List API reuses authoritative `Repository.detail` enrichment rather than a second projection algorithm. Supplies signals and existing job status; explicit conservative `ready_to_share` requires ready scorecard, zero must-fixes, six strong signals, no unchecked evidence, non-partial coverage and a completed job. Missing evidence does not become Ready. Missing signals render unknown, not green. Legacy summary fields remain API-compatible.
- Home reading phone uses captured image index and actual page count; zero captures says opening/queued, never invented screen 1 or percentage. Three steps advance only with actual checking/completed status. Failure never completes pending steps. Recheck preview behavior retained outside Home.
- Historical Share submit routing remains unchanged; only Home submit/sample/card routes explicitly add `#overview`.

## Verification / TDD evidence
All commands ran in `/Users/o0o02dn/Documents/adminAI/survey-coach`, using temporary SQLite/synthetic browser fixtures, no live database.

1. RED: `.venv/bin/python -m pytest tests/test_home_page.py -q --tb=short` — **5 failed**, missing signals, old hero/card contract, absent reading progress.
2. Initial implementation: **1 failed, 4 passed**, exposed native Shift+Tab focus escape; added explicit keyboard wrapping.
3. Focused copy integration: **1 failed, 23 passed**; the sole failure was the strict claims guard **XPASS**, proving the forbidden hero claim had actually been removed.
4. Removed the claims guard's xfail marker early (originally planned B10), necessarily now: strict XPASS fails the suite. Guard remains active, source coverage and safety assertions unchanged. B10 should not restore the marker.
5. Extended readiness/motion tests initially had an incorrect builder import; corrected to the existing survey builder. Focused GREEN: **26 passed**.
6. First full nonlive run: **2 failed, 972 passed, 1 deselected**. Both were historical Share URL expectations; narrowed the shared routing change to Home instead of weakening Share assertions.
7. Final focused: `.venv/bin/python -m pytest tests/test_home_page.py tests/test_share_ui.py tests/test_copy_guard.py tests/test_start_review_e2e.py tests/test_design_tokens.py tests/test_reader_progress.py -q --tb=short` — **35 passed, 1 warning in 10.23s**.
8. Final full: `.venv/bin/python -m pytest -m 'not live' -q --tb=short` — **974 passed, 1 deselected, 1 warning in 173.53s**. Warning is existing Starlette/httpx deprecation.
9. `git diff --check` clean; changed code files under 600 lines; CSS colours use existing tokens only.

## Boundaries / caveats
No delegation, scaffold, worktree, push, live database, external service request or protected original image changes. Existing untracked `review/` and `uglyhome.png` untouched. Other chapters are not redesigned. Automated Chromium desktop/mobile/keyboard/reduced-motion checks were run; no manual screenshot/visual-quality audit claimed.

Reusing full detail for each list item favors correctness/DRY in this local pilot; it adds per-survey projection work (including immediate prior-version comparison). A dedicated shared lightweight projection can be extracted if real list scale requires it; no speculative caching added. The brief's three allowed status labels mean incomplete zero-must-fix evidence remains Checking rather than falsely Ready, even when the saved job has ended; its six signal labels retain the actual checked/unknown evidence.

## B8 review follow-up — P2 stale capture state

Base: `66066f7`. Read `b8-review.md` and the B8 brief/report before changes.

- [x] Reproduce with a failing two-job Home regression before implementation.
- [x] Clear the captured phone image for every zero-capture render, before current-job caption/steps render.
- [x] Run targeted RED/GREEN and focused Home/reading/entry/claims checks.
- [x] Record P3 listing scaling as a minor, deferred local-pilot tradeoff; no repository/listing changes.

Root cause: the reused Home figure only updated its image when `pages_captured` was positive. A different queued/opening/failed job with zero captures retained the previous survey's image. The minimal fix restores the existing eye placeholder in the zero-capture branch. No synthetic capture image, invented screen number, backend change or extra job-identity state is needed: capture presence is rendered directly from each current job payload. Caption and completion steps continue to rebuild synchronously from that payload; non-Home rechecks remain unchanged.

Regression: `test_new_zero_capture_job_clears_previous_survey_preview` renders a captured failure (4 screens, checking step complete), then a different queued job, opening job and zero-capture failure. Each new state asserts no image/src/previous-survey reference, the eye placeholder, exact current-job caption and all three steps incomplete. A subsequent real capture uses the new job's `/preview/0` and only then says Reading screen 1.

Exact commands and results (working directory `/Users/o0o02dn/Documents/adminAI/survey-coach`):

1. RED: `.venv/bin/python -m pytest tests/test_home_page.py::test_new_zero_capture_job_clears_previous_survey_preview -q --tb=short` — **1 failed, 1 warning in 1.93s**. Expected failure: `tests/test_home_page.py:178`, `assert page.locator('#reading-preview img').count() == 0`, actual `1 == 0` on the new queued job.
2. GREEN, same command — **1 passed, 1 warning in 1.66s**.
3. Focused GREEN: `.venv/bin/python -m pytest tests/test_home_page.py tests/test_reader_progress.py tests/test_start_review_e2e.py tests/test_mvp_preview.py tests/test_copy_guard.py -q --tb=short` — **22 passed, 1 warning in 6.39s**.
4. Warning in each run: existing Starlette/httpx TestClient deprecation. `git diff --check` clean. No full-suite rerun claimed for this three-line fix.

P3 disposition: **minor / deferred for the local pilot**. Full `detail()` projection per unpaginated listing item still warrants a shared lightweight authoritative projection or bounded listing before scaling, with projection-budget and stored-evidence immutability assertions. No second signal algorithm, cache or unrelated expansion added here.

Boundaries: synthetic localhost browser routes and temporary SQLite only; no delegation, push, live database, external service call or protected original/image changes. Existing untracked `review/` and `uglyhome.png` untouched. Only `site/entry.js`, `tests/test_home_page.py` and this report are included in the fix commit.
