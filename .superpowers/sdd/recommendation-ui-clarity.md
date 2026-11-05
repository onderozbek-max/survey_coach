# Recommendation UI clarity

Owner: code-puppy-b04710

## Completed
- [x] Action-only findings show their actual explanation prominently as **Recommended action**, without a fake rewrite or duplicate explanation in Details.
- [x] Screen inspection scopes across all plan categories, question IDs, `also_affects`, and `absorbed_by` references.
- [x] Empty states distinguish checks-run/no findings, filtered/category views, saved decisions, and empty categories. No “All 0 must-fixes handled”. Unqueued findings prevent an all-handled claim.
- [x] Compact effort navigation retains visible Low / Building / High estimated-load legend and height/color summary on mobile and desktop. Full heuristic / selected-outline explanation is in native keyboard-accessible Effort guide disclosure.
- [x] Synthetic keyboard Enter navigation, focus restoration, selected outline, minimum target sizes, and no document horizontal overflow checked at 320 / 390 / 1280px.

## TDD evidence
Initial focused run: 10 intended missing-feature failures plus one fixture setup error. Corrected the fixture error (question-ID behavior already worked). Implemented after observing intended red assertions. Additional unqueued-finding test failed correctly before adding the guard.

Final command:
```
.venv/bin/python -m pytest tests/test_recommendation_ui_clarity.py tests/test_queue_position.py tests/test_improve_ui.py tests/test_overview_ui.py tests/test_issue_loop_ui.py tests/test_improve_navigation_ui.py -q --tb=short --show-capture=no
```
**60 passed**. Includes 13 new clarity tests. No full suite, external calls, live review reads, or push. Files remain below 600 lines.

## Layout regression follow-up (supersedes earlier caveat)
Read `ui-parent-note.md` and `compact-layout-regression.md`. Parent explicitly requested running both temporary-fixture DB phone-first tests; no actual review DB/data accessed.

Inspected and preserved the uncommitted CSS specificity/spacing fixes and existing disclosure-test changes. Added default-visible legend expectations: all three viewport cases failed red while the legend was inside collapsed help. Moved only detailed explanation into help, retaining the visible color key. Mobile phone test then failed at 459.78px, then 439.78px, before compact grid/padding fixes made it green. Original phone-first assertions unchanged: desktop <450px, mobile <430px, desktop phone-screen >=450px.

Final combined command:
```
.venv/bin/python -m pytest tests/test_phone_first_workspace.py tests/test_recommendation_ui_clarity.py tests/test_queue_position.py tests/test_improve_ui.py tests/test_overview_ui.py tests/test_issue_loop_ui.py tests/test_improve_navigation_ui.py -q --tb=short --show-capture=no
```
**62 passed** (both phone-first tests + prior 60). `git diff --check` clean. Disclosure opens/closes with Enter; legend remains visible; bar focus/selected-outline/44px height, and no horizontal document overflow retained at 320/390/1280px.

No external calls, full suite, delegation, push, or actual review data. Existing staged `.superpowers/sdd/progress.md` and unrelated artifacts remain excluded. All owned sources under 600 lines.

## Stable integration UI follow-up
Read supplied integration log `/var/folders/cy/m9q20js10t9bvtd05b9lk35w0000gp/T/shell_bg_5namxysd.log`. Stable targeted rerun reproduced four failures; phone-first and compact-guide already passed.

- Refetched queue: replaced obsolete `All 0 must-fixes handled` expectation with correct empty-category semantics and no active card.
- Member journey: select a genuine question rewrite present in captured question text, not the survey title; assert its heading and actual original question are on the phone before exercising comparison/playback/mobile stacking.
- Pending-save: wait on `SC.reviewReady`, not an active Must-fix card, and explicitly focus an actionable queued finding. Preserve request locking, chapter round-trip, persisted pick/keep, reload and risk checks.
- Demo phone hero: observed 476px top (red vs <422px). Compact redundant sample metadata on mobile Improve only while retaining sample switching and quality coverage; original hero/pin visibility assertions pass unchanged.
- Broader same-file run found two stale demo contracts after engine/data updates: focus B7 by criterion and assert action-only/no-copy behavior; preserve the original unverified 3-minute text instead of inventing a verified 4-minute promise, with explicit 1.4 action-only recommendation checks.

Final command:
```
.venv/bin/python -m pytest tests/test_improve_safety_ui.py tests/test_member_journey.py tests/test_server_contracts.py tests/test_site_e2e.py tests/test_phone_first_workspace.py tests/test_recommendation_ui_clarity.py tests/test_queue_position.py tests/test_improve_ui.py tests/test_overview_ui.py tests/test_issue_loop_ui.py tests/test_improve_navigation_ui.py -q --tb=short --show-capture=no
```
**105 passed**, one existing Starlette/httpx deprecation warning. `git diff --check` clean. No engine/chapter files changed, no weakened layout thresholds, no full suite/external/live/delegation/push. Temporary synthetic fixture servers only; no actual review data.
