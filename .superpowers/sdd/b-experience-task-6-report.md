# Part B Task 6 — quiet phone preview

Owner: code-puppy-e2ca82. Base: `1e0d297`.

## Checklist

- [x] Read Task 6 brief before implementation; phone-preview scope only.
- [x] Focused RED before production changes.
- [x] Implement and verify focused GREEN.
- [x] Run full non-live suite and investigate failures.
- [x] Record scope, evidence, and remaining concern; commit with requested message.

## Changes

- `SC.cleanCopy` ports Python navigation-tail matching and blank-line cleanup; all shared `clean_copy_cases.json` cases pass in Node. Cleanup is read-time in phone rendering, `pageTexts`, and `hitsOn`.
- Model normalization now creates view objects rather than adding missing arrays to captured pages/questions. The original-text lookup reads those normalized objects. Tests compare serialized snapshots before/after preview operations.
- Phone header uses canonical screen name and exact `Name · Screen i of n` label, without topic/kind duplication. Intro/info copy removes captured trailing navigation text while retaining exactly one `.next` visual navigation control.
- Right-gutter `.phone-marker` buttons replace sentence pins; accessible tier/headline labels, card-focus behavior, and `data-pin` scroll hooks remain. Evidence marks use `--mark` and a 2px tier-colored underline.
- `add_answer` findings render dashed `li.suggested-option` ghosts only in With changes; hidden `Suggested answer:` prefix; choice/dropdown support. Additions never enter the stem-replacement plan. Original/Keep hide the ghost; preview does not save decisions or mutate options. Exclusivity instructions and the existing behavior-verification warning remain in Details; no verified-fix claim is introduced.
- `button#phone-settings` (Aa) exposes a keyboard-accessible disclosure with Large text and Device size, pressed/expanded states, persistent control focus and Escape return. Device width is honored on mobile. Walkthrough/comparison controls remain under Preview tools; tests follow that disclosure and it retains its open state during redraws.
- Token-only CSS. All changed code files remain under 600 lines (largest: existing `test_site_e2e.py`, 386 lines; app.js 373).

## Verification

Commands used `.venv/bin/python -m pytest` from the project root.

1. Initial RED: `tests/test_phone_preview.py -q --tb=short` — **8 failed in 123.95s** (`/tmp/b6-red.log`). Missing cleanup/markers/ghosts/settings and raw navigation/header text were observed before implementation.
2. Focused final GREEN: `tests/test_phone_preview.py tests/test_member_journey.py tests/test_site_e2e.py tests/test_improve_safety_ui.py tests/test_answer_addition_ui.py tests/test_with_fixes_preview.py tests/test_clean_copy.py -q --tb=short` — **61 passed in 18.49s** (`/tmp/b6-focused-final.log`). Includes keyboard/focus, 390px reflow, gutter geometry, shared fixture parity, snapshot immutability and unchanged exclusivity warning.
3. Canonical-label assertion migrations: `tests/test_improve_ui.py tests/test_improve_navigation_ui.py -q --tb=short` — **21 passed in 8.35s** (`/tmp/b6-navigation.log`). Same-screen/card safety checks retained, comparing canonical names rather than removed header topics.
4. Final complete non-live run: `-m 'not live' -q --tb=short` — **1 failed, 950 passed, 1 deselected, 1 xfailed, 1 warning in 203.56s** (`/tmp/b6-full-final.log`). All Task 6 and migrated tests pass in this run. This is not a fully green suite.
5. `git diff --check` and `node --check` for model.js, phone.js and app.js pass.

## Remaining concern: pre-existing concurrency test

`tests/test_server_contracts.py::test_rapid_choice_changes_cannot_save_the_older_pick_last` holds a decision PUT and then clicks Keep while `improveOperation.busy` disables all decision controls. It times out waiting for that disabled button. This contract predates Task 6 and conflicts with the pending-save UI lock.

Verified with the unchanged test and base `1e0d297` app/model/phone/styles/review-studio assets served by a temporary Playwright interception plugin outside the repo: **1 failed, 1 warning in 32.91s**, same disabled Keep timeout (`/tmp/b6-baseline-concurrency.log`; temporary plugin `/tmp/b6_baseline_plugin.py`). No checkout/worktree or baseline file overwrite was used. The test and decision-concurrency production logic were left unchanged rather than weakening a safety assertion or expanding Task 6 scope.

## B6 review fix and B5 contract reconciliation — base `c621e44`

Owner: `code-puppy-94483f`.

- [x] Read `b6-review.md` and B6/B5 implementation reports before edits.
- [x] Reproduce option wrapping with real Chromium geometry before production fix.
- [x] Reserve an 18px control column and flexible copy/gutter column for existing options. Fold and suggested-answer rows deliberately retain their existing styling. No save/revision production logic changed.
- [x] Add radio and checkbox geometry cases at desktop (1280px) and narrow viewport (390px, 320px device, Large text). Assert wrapper starts on the control row, first label line overlaps the control vertically, and copy stays inside the option. Existing gutter/ghost checks remain.
- [x] Replace obsolete rapid-click server contract with delayed-save lock coverage: initial lock, chapter round-trip/redraw lock, one emitted request, successful release/unlock, exact committed pick after reload, then legitimate Keep and persisted reason/accepted risk/disabled bulk copy.
- [x] Reuse and strengthen `test_workspace_decisions.py::test_delayed_use_cannot_overwrite_newer_keep_after_navigation` for independent API ordering proof. Held request is revision 1/pick under the same client ID; newer revision 2/Keep is sent directly through the real temporary API. Delivering revision 1 last returns HTTP 200 with authoritative revision 2/Keep/reason, not the stale pick. Clipboard remains unchanged, controls unlock, and reload retains Keep/risk with bulk copy disabled.
- [x] Focused phone/server/safety run and FULL nonlive suite green before commit.

### Exact commands and output

All commands ran from `/Users/o0o02dn/Documents/adminAI/survey-coach`. Full logs are local `/tmp` files; summaries below are exact.

RED before CSS fix:
```text
.venv/bin/python -m pytest tests/test_phone_preview.py -k option_control -q --tb=short > /tmp/b6-review-red.log 2>&1
4 failed, 8 deselected in 2.92s
```
All four fail on `abs(copyTop - top) <= 1`, with actual difference `30.0`: the label wrapper wrapped below the control.

Intermediate focused run:
```text
.venv/bin/python -m pytest tests/test_phone_preview.py tests/test_server_contracts.py tests/test_workspace_decisions.py tests/test_improve_safety_ui.py tests/test_issue_loop_ui.py -q --tb=short > /tmp/b6-review-focused.log 2>&1
2 failed, 28 passed, 1 warning in 20.34s
```
The two new waits incorrectly accessed private `improveOperation` via `SC`; fixed the test setup to wait on observable rendered disabled/enabled controls using Playwright `expect`, without exposing internal state or changing production behavior.

Final focused GREEN:
```text
.venv/bin/python -m pytest tests/test_phone_preview.py tests/test_server_contracts.py tests/test_workspace_decisions.py tests/test_improve_safety_ui.py tests/test_issue_loop_ui.py -q --tb=short > /tmp/b6-review-focused-final.log 2>&1
30 passed, 1 warning in 20.65s
```

FULL nonlive GREEN (pytest exit 0):
```text
.venv/bin/python -m pytest -m 'not live' -q --tb=short > /tmp/b6-review-full.log 2>&1
955 passed, 1 deselected, 1 xfailed, 1 warning in 170.60s (0:02:50)
```
Existing warning: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` Existing expected failure and excluded live test remain unchanged.

```text
git diff --check
```
Exit 0, no output. Changed code files are below 600 lines: styles.css 188, test_phone_preview.py 176, test_server_contracts.py 182, test_workspace_decisions.py 109. No delegation, push, live/external access or protected-asset edits; existing untracked `review/` and `uglyhome.png` untouched.

## Boundaries

No delegation, worktree, push, external calls, live DB, real-model request, protected rubric/fixture/data edits, or unrelated product work. Browser tests used local static assets and intercepted synthetic detail; existing server tests used their temporary databases/FakeProviders. Existing untracked `review/` and `uglyhome.png` were left untouched. No screenshot/visual-audit claim; layout assertions are DOM/computed-style based.
