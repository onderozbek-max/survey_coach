# Part B Task 3 report

Status: complete. Base: `0195816`. Owner: `code-puppy-57e299`.
Commit message: `Introduce the three-chapter review shell`.

## Checklist
- [x] Read the Task 3 brief first; inspect workspace, entry, application and workflow code.
- [x] Add failing synthetic Playwright contracts before production changes.
- [x] Add shared hash router and chapter shells for saved reviews and the static sample.
- [x] Default to Overview; validate chapter names; preserve query and fragment on legacy redirects.
- [x] Support chapter links, direct hash changes, pushState, Back and Forward without duplicate dispatches/history entries.
- [x] Toggle hidden and aria-current; focus chapter headings without implicit scrolling; explicitly scroll to top with instant reduced-motion behavior.
- [x] Route focus-finding events to Improve without losing the requested finding.
- [x] Render Improve lazily; preserve its DOM/state across chapter changes and refresh deferred decision updates when revisited.
- [x] Remove rail container/rendering, toolbar mount and journey mount. Keep screen navigation through a compact native select.
- [x] Preserve old decision, risk reason, clipboard, hypothetical preview, comparison, walkthrough, title, round and recheck flows in Improve until B5.
- [x] Load icons, diff and toast after dom and before their consumers. No React or new dependencies.
- [x] Keep consistent About this review footer and 44px chapter targets; verify no mobile horizontal overflow.
- [x] Adapt legacy tests explicitly to Improve and screen-picker selectors while preserving safety assertions.
- [x] Run focused tests, full suite, whitespace checks and scope review before committing.

## Verification

Commands use the existing `.venv`; no package installation or external services.

- RED: `.venv/bin/python -m pytest tests/test_chapters_ui.py -q --tb=short`:
  **10 failed** in 34.41s, missing chapter sections/navigation and router functions.
- Focused green (router, issue loop, static sample, mobile phone, comparison):
  **46 passed** in 17.85s.
- Added explicit lazy-render/DOM-retention and removed-mount assertions.
- First full suite: **890 passed, 4 failed, 1 skipped, 1 xfailed**.
  Three failures exposed an old `body.insertBefore(..., topbar)` call: topbar is now nested.
  Fixed the insertion reference to the body-level workspace. The fourth test needed to enter
  Improve after a newly created round defaults to Overview. No safety assertion removed.
- Regression run for chapters, unified workspace, recheck workflow and workspace contracts:
  **18 passed** in 13.00s.
- Final full suite: `.venv/bin/python -m pytest -q --tb=short`:
  **894 passed, 1 skipped, 1 xfailed, 1 warning** in 157.67s.
- `git diff --check`: clean.
- Production sizes: app.js 359 lines; chapters.js 46; chapters.css 31. All changed files remain under 600 lines.

## Scope and concerns

- Overview and Share intentionally contain heading placeholders only. Their content belongs to subsequent tasks.
- About this review is the specified shell button; its actual sheet belongs to the later About task.
- `journey.js` remains loaded solely because comparison uses its existing `SC.previewReadingDelta` helper.
  The journey UI mount is removed; replacing that module with energy remains later scope.
- Existing preview controls remain under `preview-controls` rather than the removed toolbar mount,
  preserving decision/preview safety coverage until B5. Rail-only navigation tests now use the native screen picker.
- The saved-review above-fold assertion accounts for the new chapter header: phone must still start
  in the top half of the 900px viewport; the static sample's existing stricter mobile assertion still passes.
- One live test remains skipped, one expected failure remains expected; the existing Starlette/httpx
  deprecation warning is unchanged.
- Tests use intercepted synthetic detail or temporary fixture databases and localhost servers only.
  No live DB, model services, original/protected images, untracked `review/` or `uglyhome.png` touched.
- No delegation, worktree creation, push or external calls performed.

## B3 review fixes (base `c44f9af`)

Owner: `code-puppy-b04d3a`. Both P2 findings addressed; scope limited to routing,
playback invalidation and focused regression tests.

- [x] Read B3 review, brief and original report; trace both state transitions.
- [x] Add regressions and observe the expected failures before changing production code.
- [x] Intercept the skip shortcut without changing hash/history or dispatching a chapter
  event; explicitly focus and scroll the existing workspace. Invalid chapter fallback is unchanged.
- [x] Mark Improve dirty only when chapter exit stops active playback, so reentry renders
  the actual stopped action while ordinary non-playing DOM retention remains intact.
- [x] Verify keyboard Enter from Improve/Share in both saved-review and static shells,
  including workspace focus, visibility, unchanged route/history and no writes/errors.
- [x] Verify playback exits to Overview/Share, no advance while away or after reentry,
  correct Play/Pause labels, and actual resumed advance with a deterministic browser clock.
- [x] Run relevant tests and whitespace check; commit only scoped files.

Exact commands/results (localhost synthetic intercepts and temporary fixture DB only):

1. RED: `.venv/bin/python -m pytest tests/test_chapters_ui.py tests/test_member_journey.py -k 'keyboard_skip or playback_stops' -q --tb=short`
   — **6 failed, 11 deselected in 4.13s**. Four skip cases changed the route to
   `#workspace` and displayed Overview; two playback cases retained Pause after reentry.
2. GREEN: `.venv/bin/python -m pytest tests/test_chapters_ui.py tests/test_member_journey.py -k 'keyboard_skip or playback_stops' -q --tb=short`
   — **6 passed, 11 deselected in 3.69s**.
3. Relevant regression run: `.venv/bin/python -m pytest tests/test_chapters_ui.py tests/test_member_journey.py tests/test_issue_loop_ui.py tests/test_site_e2e.py tests/test_phone_first_workspace.py tests/test_unified_workspace.py -q --tb=short`
   — **54 passed in 21.35s**.
4. `git diff --check` — clean (exit 0).

No dependencies, delegation, pushes, external services, live DB or protected assets
were used/changed. Existing untracked `review/` and `uglyhome.png` remain untouched.
All changed files remain below 600 lines. Full suite not rerun for this scoped fix.
