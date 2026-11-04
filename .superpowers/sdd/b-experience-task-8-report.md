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
