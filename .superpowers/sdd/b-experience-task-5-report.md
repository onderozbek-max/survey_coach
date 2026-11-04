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
