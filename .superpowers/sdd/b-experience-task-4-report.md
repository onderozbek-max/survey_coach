# Part B Task 4 report

Status: implemented Overview and energy/member preview only, starting at 98d239c.

## Checklist
- [x] Read Task 4 brief and existing shell before implementation.
- [x] DOM contracts: supplied headline/subline, six supplied signals with icon/state labels and explicit navigation, honest supplied strengths (at most three, absent when empty), one primary action, secondary preview.
- [x] Desktop 7:5 hero with inert 0.72-scale highlighted mini phone, canonical title, relative version timestamp (version metadata fallback), three-column signals, full energy map, strengths/plan columns, five survey-style radios.
- [x] Mobile single-column signals, hidden mini phone, horizontally snapping energy bars, visible swipe hint, fixed bottom actions.
- [x] Energy uses Part A screen names, seconds, zones and heaviest entry, plan must-fix counts; labelled estimates, zone legend, unclipped ellipsis/title labels and alternating desktop labels above 14 screens.
- [x] Style PATCH followed by detail GET, projection refresh, saved announcement, restored focus; generic-title inline PATCH editor shares the update path with existing Rename.
- [x] Native fullscreen dialog: explicit keyboard wrap, Escape/close, focus return, 390px phone, Pause/Play, elapsed estimate, compact scrubber, pause on hidden document, synchronous timeout/listener cleanup on close/chapter exit, safe reopen.
- [x] Move previewReadingDelta and reusable playback clock into energy.js; delete journey.js; update both shell callers; no duplicated app timer.
- [x] Canonical screen navigation into Improve, preserving signal/page/fingerprint or plan-tab context as SC.improveFilter for the later queue task. No queue redesign attempted.
- [x] Token-only new CSS; all touched code files below 600 lines.
- [x] Preserve older safety assertions while scoping Improve phone selectors to #stage and changing old Intro expectations to Part A's Welcome.

## TDD and verification
- Initial command using pytest executable hit the existing tests namespace/import-path environment issue. Used PYTHONPATH=. .venv/bin/python -m pytest thereafter.
- RED: new Overview test failed because #overview-headline did not exist, before production changes.
- First focused integration run: 26 passed, 3 failed on legacy global phone selectors/lazy-Improve assertion; scoped selectors without dropping assertions.
- First full non-live run: 902 passed, 5 failed on additional global phone selectors and canonical Welcome naming; updated selectors/copy.
- Additional RED tests caught native dialog Shift+Tab escaping to browser chrome, focus loss after style re-fetch, and asynchronous close cleanup under a paused test clock. Added explicit keyboard wrap, radio focus restoration, synchronous close disposal.
- Final focused: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_overview_ui.py tests/test_site_e2e.py tests/test_chapters_ui.py tests/test_issue_loop_ui.py tests/test_member_journey.py`: **61 passed**.
- Final full suite: `PYTHONPATH=. .venv/bin/python -m pytest -q -m 'not live'`: **911 passed, 1 deselected, 1 xfailed**, 161.28s.
- Existing dependency warning: Starlette TestClient/httpx deprecation, unchanged.
- `git diff --check`: clean. No journey.js/renderJourney/schedulePlayback references remain in site/tests.
- Tests use intercepted synthetic detail, local static assets and pytest temporary SQLite with FakeProvider. No live AI, external survey access, stored review edits or protected screenshot modifications.

## Commit
Prescribed implementation/report commit: `Add the Overview chapter with signals, energy map and plan`.

## Concerns / scope boundaries
- The later Task 6 Improve queue/tab/filter UI is intentionally not built here; navigation selects the first requested canonical screen and supplies its filter context for that task.
- Static demo has no persistence endpoint: style radios are disabled rather than pretending to save. Local review supports real PATCH/re-fetch using temporary DB tests.
- Relative checked time uses available current-version metadata; missing sample timestamps honestly say time unavailable.
- No screenshot capture or external accessibility service was run. Responsive layout, focus trap, sizing and overflow have Chromium DOM/browser coverage at mobile/tablet/desktop widths.
- Pre-existing untracked review/ and uglyhome.png were left alone.
