# Final consolidated fix wave

Base: 899f4ce. Owner: code-puppy-bdeb0f. Completed. Fix commit: `cddfe9b`; refreshed captures and this report are in the subsequent documentation/evidence commit.

## Plan
- [x] Reproduce seven P2 findings and modal routing / timeout P3 with focused failing regressions.
- [x] Repair fingerprint/version identity, delayed operations, authoritative decision refresh and Undo focus.
- [x] Correct completion headline and exact question locations without mutating stored evidence.
- [x] Repair mobile focus geometry, shared loading/errors, About routing; verify Escape.
- [x] Run focused and full nonlive suites before committing; record exact results.
- [x] Commit logical fixes, regenerate changed captures only under review/after, update honest delivery evidence.

Constraints: isolated synthetic fixtures/temp DB only; no live AI/external services/real DB/delegation/push/worktree. Original screenshots and existing untracked manual QA left untouched. Toast expiry remains six seconds. Listing projection cost stays a bounded local pilot risk, not shared-service acceptance.

## Reproduction and fixes

The complete final-review.md was read first, then browser QA, ledger and delivery/board specs. No production edits preceded the initial regressions. Early test harness mistakes (missing fingerprints/decisions, wrong import/Playwright argument) were corrected before using their failures as reproduction evidence.

| Finding | Before-change reproduction / root cause | Fix and regression evidence |
| --- | --- | --- |
| P2 Undo identity | Keep final finding, remove two earlier entries via detail replacement, Undo: unhandled error/no restored notification. Removed target fails too. | Writes resolve fingerprint + version at the final boundary. No numeric index in Undo records. Moved out-of-range, moved in-range and removed-target tests assert no neighboring write; preview choices reconciled by fingerprint. |
| P2 dishonest headline | Real enrichment of sample with all picks, keeps, mixed or carried choices said no must-fixes found. | Separate total from open counts. Handled copy explicitly says changes/kept risks are not verified fixes. Same headline asserted in downloaded HTML; stale/reopened remain open, original scorecard and input unchanged. Zero-findings contract retained separately. |
| P2 stale Overview | Disposable server: keep one must-fix, return Overview; headline never changes until timeout. | Successful writes/restores fetch authoritative version detail and publish it to chapters. No browser scoring algorithm. Stale GET cannot erase newer revision; visible retry warning on refresh failure. |
| P2 mobile focus | Tab/Shift+Tab at 390x844: signal-link center covered by action bar, with normal/reduced motion and enlarged text. | ResizeObserver measures wrapped/safe-area bar height; scroll padding/margins plus focus clearance. Real Tab/Shift+Tab geometry and hit-testing pass in all four modes. |
| P2 Undo focus | Keyboard keep -> auto-advance -> focus Undo -> Enter left BODY focused. | Restore selects current fingerprint's panel and focuses single heading/group row; failed restores and toast dismissal have live destinations. Six-second expiry unchanged. Keyboard continue -> Share checked. |
| P2 exact locations | Actual engine group of 3 questions on one screen rendered Q1–Q3 and first topic for every row. | Question-specific captured label and text, canonical Screen number, shared Improve/Share helper. Test includes info question and researcher label; copied Share and download agree. |
| P2 default-route status | Missing/network/failed/queued links exposed status only in hidden Improve. Metadata failure after completed detail also reproduced separately. | Shared shell status, visible recovery navigation, app metadata error uses shared status; failed recheck retains completed review. |
| P3 About routing | Hash/programmatic/Forward changed underlying section while modal stayed open. | Real chapter changes close dialog without stealing router heading focus. Same chapter is not closed. Escape passed three deterministic baseline cycles and remains native. |
| P3 finite timeout | NaN/+inf reached mkdir/server before validation; nonpositive cases rejected already. | math.isfinite and positive before output creation; nan, inf, -inf, zero, negative CLI tests. |

Pending batches capture a projection revision as well as fingerprints and decision revisions. A source replacement stops remaining writes/copy/advance even if a later GET returns the old shape. Delayed-write and delayed-clipboard coverage passes. A clipboard request already started cannot be recalled: the message explicitly says to check its contents instead of falsely claiming nothing copied.

## Exact verification commands and results

All commands ran in `/Users/o0o02dn/Documents/adminAI/survey-coach`.

Initial red commands (before fixes):
- `.venv/bin/python -m pytest tests/test_final_projection.py tests/test_final_fixes_ui.py -q --tb=short` — 25 failed, 4 passed; includes initial harness defects explicitly excluded above (`final-red.log`).
- `.venv/bin/python -m pytest tests/test_final_projection.py tests/test_final_locations_ui.py tests/test_final_fixes_ui.py::test_decision_refresh_overview_matches_authoritative_api -q --tb=short` — 8 failed, 5 passed after headline/API harness repair; grouped fingerprint setup corrected next (`final-red-projections.log`).
- `.venv/bin/python -m pytest tests/test_final_locations_ui.py -q --tb=short` — 1 failed on actual Q1–Q3 vs Q1 · Screen 2 mismatch (`final-red-locations.log`).

Final focused command:
```sh
.venv/bin/python -m pytest tests/test_final_projection.py tests/test_final_fixes_ui.py tests/test_final_locations_ui.py tests/test_final_races_ui.py tests/test_improve_ui.py tests/test_improve_safety_ui.py tests/test_signals.py tests/test_enrich_contract.py tests/test_capture_screens.py tests/test_copy_deck.py tests/test_design_tokens.py -q --tb=short
```
**141 passed, 1 warning in 28.98s** (`final-focused.log`). Includes capture-runner process cleanup, PNG decoding and protected-original hash comparisons.

Final full command, green before fix commit:
```sh
.venv/bin/python -m pytest -m 'not live' -q
```
**1051 passed, 1 deselected, 1 warning in 194.50s** (`final-full.log`). Warning is existing Starlette/httpx deprecation. Earlier full run was 7 failed / 1036 passed; stale headline expectations were corrected and a newer-revision refresh regression was fixed, not suppressed (`final-full-initial.log`).

After `cddfe9b`:
```sh
.venv/bin/python scripts/capture_screens.py
.venv/bin/python scripts/capture_screens.py --reduced-motion --output review/after/reduced-motion
```
Both exited 0; 12 normal and 12 reduced-motion PNGs refreshed with SHA-256 manifests, zero page errors/external request attempts, no horizontal overflow, owned server stopped and temp DB removed. Logs: `review/after/capture.log`, `review/after/reduced-motion-capture.log`. Manifests explicitly retain NOT inspected; these are capture/DOM checks, not visual sign-off. No protected-original image modified. Production diff whitespace check passed. Staged raw failure logs contain three pytest-generated trailing-whitespace lines; retained verbatim as evidence rather than edited.

## Remaining risks and acceptance boundaries
- Home listing still performs full per-survey/prior-version projection without pagination: bounded single-user local pilot only. Shared-service scale needs shared lightweight authoritative projection, pagination and budget tests.
- Human five-second comprehension, complete visual inspection, all paragraph lengths, five-person pilot/SUS metrics remain unaccepted. Automated geometry/keyboard evidence is not a fabricated human sign-off.
- Hosting/auth/authorization/tenant isolation, approved data handling and RedJade egress/Chromium remain Part C; no associate-wide deployment approval.
- On a failed post-save detail refresh the decision remains saved and an explicit reload warning is visible; no fabricated fresh counts. Clipboard content already handed to the platform cannot be canceled.
- Existing completed-partial Home card “Checking…” copy remains the separately documented P3 product-copy follow-up; no change to readiness policy in this fix wave.
