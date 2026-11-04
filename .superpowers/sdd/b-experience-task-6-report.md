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

## Boundaries

No delegation, worktree, push, external calls, live DB, real-model request, protected rubric/fixture/data edits, or unrelated product work. Browser tests used local static assets and intercepted synthetic detail; existing server tests used their temporary databases/FakeProviders. Existing untracked `review/` and `uglyhome.png` were left untouched. No screenshot/visual-audit claim; layout assertions are DOM/computed-style based.
