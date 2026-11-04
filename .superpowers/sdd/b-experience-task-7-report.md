# Part B Task 7 - Share

Base: `d061569`. Scope: private saved-review Share chapter only.
Requested commit: `Add the Share chapter with change list, download and recheck`.

## Checklist
- [x] Read Task 7 brief before source exploration.
- [x] Focused red: seven Share contracts failed against the base (missing chapter content, unsafe source prefill, hidden old recheck).
- [x] Implement Share using the shared SC namespace and canonical screen names.
- [x] Focused green and revision-lock/reset/history security regressions.
- [x] Full non-live suite green.
- [x] Commit requested message (this report included in that commit).

## Implementation
- New `site/share.js` projects explicit, non-stale picks only. Recommended previews, absorbed findings and kept reasons never enter the bulk clipboard payload. Per-change copy is scoped to that edit.
- Changes grouped by canonical model screen name; text edits use `SC.renderDiff`, additive answers say Keep question / Add answer option, never replace the stem.
- Summary counts actual changes and reasoned keeps; open must-fixes count server-plan items with any unhandled member. Partial grouped completion and stale picks remain open. Choosing is not verified correction.
- Kept reasons live in a separate disclosure with accepted-risk wording. No fabricated readiness; limitations remain available in Details. Existing decision saving, lock/revision/Undo/reset persistence and backend security are unchanged.
- Private Share owns Copy all (sole primary, hidden and disabled at zero), version-pinned existing `summary?download=1` download route, version comparison and existing recheck form/job submission.
- Comparison retains no-longer-flagged / still-flagged / new / uncertain honesty and old/new evidence; version links retain `#share`. Missing comparison claims nothing fixed.
- Prefill accepts only credential-free HTTPS RedJade links without query/fragment/port/whitespace. Unsafe source URLs are not cleaned into apparently safe links or echoed into summary/copy. Existing submit validation and server protection remain in force.
- Improve Check again routes to Share and focuses prefilled input; reduced motion respected. Token-only chapter styling, 44px controls, safe text nodes, mobile wrapping.
- Migrated old private-workflow selectors while preserving safety assertions. Static demo and backend summary export unchanged.

## Verification
- Initial focused RED: `pytest tests/test_share_ui.py -q --tb=short`: **7 failed**, expected missing Share behavior.
- Reset RED: first `tests/test_share_state_ui.py` run: **1 failed, 1 passed**, showing Share did not refresh on authoritative detail replacement; added guarded workflow listener.
- Focused GREEN: Share contracts initially **9 passed**; added canonical-name, grouped-open and markup-safety coverage.
- Workflow migration set: **23 passed**, one existing Starlette/httpx deprecation warning.
- Share + durable safety set: **23 passed**, same existing dependency warning (Share, reset/history, revision locks, server contracts, persisted decisions).
- Full final non-live GREEN: `.venv/bin/python -m pytest -m 'not live' -q --tb=short`: **965 passed, 1 deselected, 1 xfailed, 1 warning in 167.65s**. The warning is the existing Starlette/httpx deprecation; the expected failure and live exclusion are unchanged.
- Full intermediate runs found seven then one obsolete private sign-off/change-sheet selectors; migrated all to the Share/download contract, retaining their safety checks. Final clean run includes the added tests.
- Download/token/unchecked-scope focused checks: **15 passed**, same dependency warning.
- `git diff --check`: clean. All added/modified files under 600 lines.

## Boundaries / concerns
No delegation, worktree, push, external service access, live database access or protected image changes. Browser cases use intercepted synthetic payloads; server cases use temporary SQLite/FakeProvider. Existing untracked `review/` and `uglyhome.png` left alone.

Download is the existing standalone HTML summary route, not a newly invented export; download/export safety tests remain part of the suite. No launch readiness is inferred from chosen changes or from an empty remaining queue. Test coverage is automated localhost behavior/layout, not a claim of screenshot-based visual approval.

## B7 review follow-up — historical baseline and Version terminology

Base: `527de77`. Addresses `.superpowers/sdd/b7-review.md` P2 and P3.

- [x] Read review and original report; reproduce misleading historical comparison copy with failing tests.
- [x] Replace the selected-version promise with: “The next check compares with the latest saved version, not necessarily the version displayed here.” This applies to latest and historical views without relying on potentially stale timeline metadata.
- [x] Change Share timeline links, accessible region/navigation names, comparison/fallback copy and submit action from Round to Version. Existing API `round` fields and CSS selectors remain unchanged.
- [x] Add successful historical reader submissions from displayed versions 1 and 2 with version 3 saved: unchanged same-study payload, version-pinned download, disclosure before submitting, and navigation to returned version 4. Add a temporary-DB contract proving version 4 compares to version 3 and historical review content remains immutable.
- [x] Run focused Share/recheck/rounds tests and commit only this fix/report.

### Exact commands and results

All commands run from `/Users/o0o02dn/Documents/adminAI/survey-coach`.

1. RED: `.venv/bin/python -m pytest tests/test_share_ui.py -q --tb=short` → **3 failed, 6 passed in 4.20s**. Latest-view copy contract and both historical cases fail on the old “compare it with this version” promise.
2. Intermediate: `.venv/bin/python -m pytest tests/test_share_ui.py tests/test_committee_rounds.py tests/test_server_api.py tests/test_server_jobs.py tests/test_workflow_e2e.py -q --tb=short` → **1 failed, 32 passed, 1 warning in 10.50s**. The new backend guard initially compared entire historical responses, including the legitimately growing `versions` timeline. Narrowed immutability assertion to all fields except that timeline; no backend changes.
3. GREEN: `.venv/bin/python -m pytest tests/test_share_ui.py tests/test_committee_rounds.py tests/test_server_api.py tests/test_server_jobs.py tests/test_workflow_e2e.py -q --tb=short` → **33 passed, 1 warning in 7.98s**. Warning is the existing Starlette/httpx deprecation.
4. `git diff --check` → **clean** (exit 0).
5. `git diff --stat` → **5 source/test files, 62 insertions, 10 deletions** before this report appendix.

No full-suite rerun claimed for this follow-up. No backend production files, delegation, push, live/external services, protected images or existing untracked files touched.
