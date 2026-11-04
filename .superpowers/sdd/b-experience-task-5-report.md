# Part B Task 5 — Improve queue

Status: complete; focused and full non-live verification green. Base: `a7097c1`.
Owner: `code-puppy-8f2852`.
Commit subject: `Rebuild Improve as a focused one-thing-at-a-time queue`.

## Completed checklist

- [x] Server-authoritative queue over `detail.plan`: supplied tier/order/membership and denominators; no browser regrouping. Absorbed findings excluded from navigation/phone markers. Confirmed decisions update progress without mutating the server plan or stored findings.
- [x] Sticky 56px desktop sub-bar, progress tabs with keyboard arrows/Home/End, compact supplied energy map, All screens and Original / With changes. Centred 340–400px phone / up-to-560px panel with 48px gap; responsive stack. Removed old rail/journey/Next issue and duplicate screen/view controls. Secondary comparison, playback and larger preview text live under Preview settings.
- [x] Canonical location prefix shared with phone; tier icon/word, headline, impact, inline diff or answer addition, labelled alternative chips, absorbed headlines and explanation/evidence in Details. Neutral AI pill only for AI-origin advice, with required tooltip.
- [x] Explicit Use saves before copying. Failed/stale saves cannot copy. Honest clipboard failure toast retains the saved decision and Undo. Successful copy announces the required paste instruction, advances to the next undecided item, focuses headline and announces Next.
- [x] Keep opens required reason chips; chips save immediately, Other requires nonblank text. Skip writes nothing. Stale picks show the specified choose-again note. Section completion offers quick wins and Share.
- [x] Patterns retain supplied membership, show per-row locations/diffs/Use/Keep, and issue individual PUTs. Partial failure stops, reports exact partial count, never copies or claims all succeeded, and permits undoing only confirmed saves.
- [x] Undo restores prior writable decision fields (action/picked_text/reason/manual_done), or open when absent, using the existing same-client revision protocol. Newer edits are guarded; failed restores never claim success.
- [x] Native modal drawer with accessible name, search by current canonical label/topic, severity icon and screen-reader finding count, Escape/close focus restoration, screen selection and first-open-plan-item navigation. Empty screens retain a valid labelled panel.
- [x] Overview page/signal/fingerprint/tab options consumed, including same-chapter routes. Refetched detail replaces queue payload. Pager and compact-map keyboard navigation stay in context and preserve focus.
- [x] Existing tests migrated intentionally to new controls and post-save advancement; original clipboard, race, risk, scope, comparability, matching-only-preview and answer-addition safety assertions retained.

## TDD and verification

All commands ran from `/Users/o0o02dn/Documents/adminAI/survey-coach` using `.venv/bin/python -m pytest`.

- Initial RED: `tests/test_improve_ui.py -x -q`: failed on missing queue tabs before production changes.
- Focused feature GREEN: `tests/test_improve_ui.py -q`: 6 passed.
- Additional RED/GREEN cycles: same-chapter route consumption; refetched-detail replacement (old 0/3 versus new 0/0); actual layout (706px phone column exposed old chapter override); phone/pager context; keyboard toggle focus. Reproduced failures before fixes, then passing regression runs.
- Final focused command: `tests/test_improve_ui.py tests/test_improve_safety_ui.py tests/test_improve_navigation_ui.py tests/test_issue_loop_ui.py tests/test_workspace_decisions.py tests/test_answer_addition_ui.py tests/test_overview_ui.py tests/test_with_fixes_preview.py tests/test_member_journey.py tests/test_phone_first_workspace.py tests/test_unified_workspace.py tests/test_workflow_e2e.py tests/test_site_e2e.py tests/test_workspace_contracts.py tests/test_design_tokens.py tests/test_chapters_ui.py tests/test_server_contracts.py tests/test_start_review_e2e.py -q`: **113 passed, 1 warning in 59.84s**.
- Final full non-live command: `-m 'not live' -q`: **931 passed, 1 deselected, 1 xfailed, 1 warning in 173.22s**. Log: `/tmp/b5-verified-full.log`; focused log: `/tmp/b5-verified-focused.log`.
- Intermediate full run exposed three migration issues: removed selectors in server/start-review tests and removed CSS default `--w`. All fixed; subsequent run: 928 passed, 1 deselected, 1 xfailed, 1 warning in 176.97s. A final full run includes the last three navigation regressions and final code.
- `git diff --check`: clean. `node --check` passed for app, chapters, coach, actions, queue and drawer scripts. All touched code modules remain under 600 lines (app 356, queue 98, coach 75, actions 54, drawer 31, studio CSS 105; largest touched test 386).

## Boundaries and concerns

- Local intercepted synthetic browser payloads, static assets and existing temporary SQLite/FakeProvider test fixtures only. No delegation, worktree, push, live database, external survey, real model, or protected-data/fixture/rubric edits. Existing untracked `review/` and `uglyhome.png` left untouched.
- Existing Starlette/httpx deprecation warning remains; no dependency changes made.
- Cross-tab decision concurrency remains the pre-existing documented last-arrival-wins contract. Undo protects same-page revisions, not cross-tab compare-and-swap.
- Pattern saves are intentionally individual, non-atomic PUTs. Partial saves are reported honestly and explicitly undoable, not represented as an atomic transaction.
- Later tasks still own the phone margin-marker/ghost-answer work and Share chapter replacement. Existing lower-page change sheet/recheck/summary functions remain available; this task removes duplicate Improve navigation/editing controls, not those later chapters' functionality.
- No independent visual/a11y audit claimed. Browser tests cover computed grid sizes, mobile overflow, visible phone positioning, native dialog behavior, keyboard focus and token contrast contracts.

## B5 review fixes — base `8481e60`

Owner: `code-puppy-2f9031`. All four findings addressed.

- [x] P1: app-owned operation state survives coach replacement and chapter/tab navigation. Rendered controls reflect the lock; Use/Keep/batch/Undo entry points share it. Every batch member's revision is snapshotted, updated for this operation's writes, and checked before later writes and before clipboard work. Confirmed saves remain available for honest partial reporting and revision-guarded Undo when superseded.
- [x] P2 routing: one page/fingerprint intersection predicate selects and advances through supplied server items; matching can select the correct server tab. Explicit empty fingerprints mean no signal matches. Page-only routes stay scoped. Pattern membership/order remains untouched.
- [x] P2 clipboard denial: no automatic advance. Exact saved text stays in a labelled, read-only, manually selectable textarea with an explicit Continue without copying control; saved decision and Undo remain available.
- [x] P2 keyboard focus: stable fingerprint-keyed pattern headings receive focus before save, survive pending rerenders, and are restored after success, failure, Keep reason-chip save and Undo.

### Exact local commands and captured output

Commands below ran from `/Users/o0o02dn/Documents/adminAI/survey-coach`. Output excerpts are exact pytest summaries (full failure traces retained in the named `/tmp` logs).

Initial RED, before production changes:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py -q > /tmp/b5-fix-red.log 2>&1
FAILED tests/test_improve_ui.py::test_clipboard_failure_is_honest_and_keeps_saved_decision
FAILED tests/test_improve_ui.py::test_signal_route_intersects_page_and_fingerprints_and_stays_scoped
FAILED tests/test_improve_ui.py::test_pending_lock_survives_replacement_controls
FAILED tests/test_improve_ui.py::test_pattern_superseded_earlier_row_stops_before_later_write_or_copy
FAILED tests/test_improve_ui.py::test_pattern_keyboard_row_focus_survives_pending_success_failure_and_undo
5 failed, 5 passed in 5.07s
```
Clipboard recovery assertion was subsequently made exact against the saved-text textarea (word-diff display is not verbatim saved copy); route fixture question IDs were cleared to isolate page membership.

First GREEN:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py -q --tb=short > /tmp/b5-fix-green.log 2>&1
..........                                                               [100%]
10 passed in 6.77s
```

Expanded decision run:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py tests/test_improve_safety_ui.py tests/test_improve_navigation_ui.py tests/test_issue_loop_ui.py tests/test_workspace_decisions.py tests/test_answer_addition_ui.py tests/test_overview_ui.py tests/test_with_fixes_preview.py tests/test_workspace_contracts.py tests/test_design_tokens.py -q --tb=short > /tmp/b5-fix-focused.log 2>&1
FAILED tests/test_issue_loop_ui.py::test_stale_use_this_response_does_not_copy_over_newer_keep
FAILED tests/test_workspace_decisions.py::test_delayed_use_cannot_overwrite_newer_keep_after_navigation
2 failed, 53 passed, 1 warning in 102.98s (0:01:42)
```
Both tests attempted clicking now-disabled Keep during a pending PUT. Their setup now asserts the lock and injects a newer authoritative decision outside the panel. Original unchanged-clipboard, revision, accepted-risk, persisted Keep and disabled-copy assertions remain; the real API test still delivers revision 2 before delayed revision 1 using only its temporary fixture database.

Additional RED for a not-yet-written pattern row changed during another row's pending PUT:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py -k superseded -q --tb=short > /tmp/b5-fix-future-red.log 2>&1
FAILED tests/test_improve_ui.py::test_pattern_superseded_earlier_row_stops_before_later_write_or_copy[2-2]
1 failed, 2 passed, 9 deselected in 32.67s
```
This drove snapshotting revisions for the entire batch, not only confirmed records. Subsequent focused GREEN:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py tests/test_improve_safety_ui.py tests/test_improve_navigation_ui.py tests/test_issue_loop_ui.py tests/test_workspace_decisions.py tests/test_answer_addition_ui.py tests/test_overview_ui.py tests/test_with_fixes_preview.py tests/test_workspace_contracts.py tests/test_design_tokens.py -q --tb=short > /tmp/b5-fix-focused-green.log 2>&1
56 passed, 1 warning in 32.40s
```

Final run adds correct-server-tab/pattern-membership coverage:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py tests/test_improve_safety_ui.py tests/test_improve_navigation_ui.py tests/test_issue_loop_ui.py tests/test_workspace_decisions.py tests/test_answer_addition_ui.py tests/test_overview_ui.py tests/test_with_fixes_preview.py tests/test_workspace_contracts.py tests/test_design_tokens.py -q --tb=short > /tmp/b5-fix-final.log 2>&1
.........................................................                [100%]
57 passed, 1 warning in 31.11s
```
The warning remains the existing `StarletteDeprecationWarning` about httpx/TestClient. No full-suite rerun claimed for this patch.

Static verification:
```text
git diff --check
node --check site/app.js && node --check site/coach.js && node --check site/improve-actions.js && node --check site/queue.js
```
Both commands exit 0 with no output. Every changed code file remains below 600 lines; largest is app.js (362). No CSS changes: token-only styling preserved. Explicit action, save-before-copy, required Keep reasons, accepted-risk wording, individual pattern writes and guarded Undo remain covered. No delegation, push, external calls, live database access or protected-asset edits. Pre-existing untracked `review/` and `uglyhome.png` untouched.

## B5 completion-route follow-up — base `5be8a90`

Owner: `code-puppy-309bb3`. Remaining finding in `b5-review.md` addressed.

- [x] Tab-only Overview entry selects the first undecided server item or no active item; a fully completed Must-fix tier renders its completion heading and both continuation actions, never a decided card.
- [x] Decided fallback remains available for explicit page/fingerprint inspection. Direct screen inspection is unchanged. Shared filtering and server pattern membership/order remain unchanged.
- [x] Added focused regressions for both real Overview buttons and explicit page, fingerprint and screen inspection of decided items.

Exact commands below ran from `/Users/o0o02dn/Documents/adminAI/survey-coach`.

RED before production edit:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py -k 'completed_must_fix_route or explicit_completed_item_route' -q --tb=short > /tmp/b5-completion-red.log 2>&1
FAILED tests/test_improve_ui.py::test_overview_completed_must_fix_route_shows_completion[#start-improving]
FAILED tests/test_improve_ui.py::test_overview_completed_must_fix_route_shows_completion[#plan-summary button:first-of-type]
2 failed, 3 passed, 13 deselected in 2.44s
```
An earlier fixture attempt dispatched the screen event while still in Overview (which intentionally does not switch chapters). Corrected the test to enter Improve before inspecting a screen; no production change was needed for that setup issue.

GREEN after the minimal queue fallback correction:
```text
.venv/bin/python -m pytest tests/test_improve_ui.py tests/test_improve_navigation_ui.py tests/test_overview_ui.py -q --tb=short > /tmp/b5-completion-green.log 2>&1
......................................                                   [100%]
38 passed in 16.43s
```

Static verification:
```text
git diff --check && node --check site/queue.js
```
Exit 0, no output. No full-suite rerun claimed. Local synthetic intercepted browser fixtures only; no delegation, push, live/external access or protected-asset edits. Pre-existing untracked files left untouched. Changed code files remain below 600 lines.
