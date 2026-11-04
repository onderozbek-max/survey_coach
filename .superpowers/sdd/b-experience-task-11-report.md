# Part B Task 11 — Capture script and delivery checklist

## Status

Implemented from `5a663c9` on `feature/surveycoach-mvp`.
Commit message: `Capture board before/after screens and delivery checklist`.
Visual acceptance intentionally remains pending parent QA.

## Completed checklist

- [x] Read Task 11 brief first (after required directory discovery).
- [x] Add `scripts/capture_screens.py`, 296 lines; no production UI/style edits.
- [x] Empty temporary DB only; POST pinned offline sample; poll startup and job.
- [x] Own real uvicorn process, pass pre-bound free loopback socket without port
  race; wait/terminate/kill only this child; delete temporary DB on exit.
- [x] Produce Home, Overview, first must-fix Improve, genuine grouped Improve,
  Share with one actual chosen synthetic change, paused reconstructed walkthrough.
- [x] Capture 1440×900 and 390×844; output only under `review/after/`.
- [x] Generate normal and reduced-motion evidence, 12 PNGs each, print file list.
- [x] Add seven automated script tests, including real lifecycle/exception and
  serve/SIGTERM cleanup, empty DB refusal, deadlines/job failure, output safety,
  real PNG capture/dimensions/hashes and original-file preservation.
- [x] Full non-live suite and delivery document with evidence/acceptance separation.
- [ ] Human visual/keyboard acceptance — explicitly NOT inspected/performed here.

## Implementation and provenance

Sample endpoint uses committed synthetic boxer-briefs + reviewed offline cache;
OfflineOnly cannot call a model. If that sample has no grouped plan item, seed
`pattern_snapshot()` via `/api/surveys` with `ai: false`: three distinct multi-
select questions omit the same instruction and the actual engine groups their
criterion 3.3 findings. No fabricated review/plan/AI response override is used.
Share chooses actual engine-suggested wording through the UI. All decisions are
restricted to the disposable DB; reopen them before each viewport to avoid
carrying desktop progress into mobile. Original sample data, saved user evidence,
`review/*.png` and `uglyhome.png` remain untouched.

Browser routes permit only the exact owned origin; service workers blocked.
Normal/reduced runs reported no page errors or external request attempts.
Environment provider variables are removed in the child; create_app receives
explicit temporary DB and provider=None, not the production server entrypoint.
The only network traffic is local loopback HTTP for this server/test fixtures.
No delegation, worktree, push, live AI, external services or real DB.

## Evidence and verification

- `review/after/evidence.json`: successful normal run; all 12 images hashed,
  viewport/scroll-width/action-class/About metrics and browser diagnostics.
- `review/after/reduced-motion/evidence.json`: same for reduced motion.
- `review/after/{desktop,mobile}-{home,overview,improve,improve-pattern,share,preview-member}.png`.
- Same image names under `review/after/reduced-motion/`.
- `review/after/capture.log`, `reduced-motion-capture.log`, each `server.log`.
- `review/after/full-nonlive-tests.log`: **1013 passed, 1 deselected**, 186.73s;
  one existing Starlette/httpx deprecation warning.
- Targeted final script run: **7 passed**, 12.49s.
- `git diff --check`: clean. New source/docs below 600 lines each.
- Programmatic PNG decoding/dimensions is NOT visual inspection. No vision tool
  was used and no claim about aesthetic acceptance is made.

Initial capture attempts correctly exposed the API's JSON content-type requirement
and shared-temp-decision carryover into mobile. Both runner bugs fixed and final
normal/reduced captures regenerated; full suite rerun after last test addition.

## Delivery document and local QA instructions

`docs/superpowers/specs/2026-11-03-board-redesign-delivery.md` records every board
criterion, related passing automation, and unchecked visual/manual acceptance.

```sh
cd /Users/o0o02dn/Documents/adminAI/survey-coach
.venv/bin/python scripts/capture_screens.py --serve --output review/after/manual-qa
```

Use fresh URLs printed by that command. Pattern URL: choose Quick wins to see
three grouped rows. Overview: Preview as a member. Sample Improve: Use this
change then Share for a populated change list. Ctrl-C cleans up server and DB.

Capture commands:

```sh
.venv/bin/python scripts/capture_screens.py
.venv/bin/python scripts/capture_screens.py --reduced-motion --output review/after/reduced-motion
```

Options: `--output` (must be under after), `--timeout` (positive, default 60),
`--reduced-motion` (capture browser only), `--serve` (manual disposable server).
Full-page PNG heights may exceed the declared viewport height. No before image
was created: the supplied before/original evidence is deliberately preserved.

## Remaining concerns

No known capture blocker. Human five-second comprehension, complete keyboard-only
must-fix/Undo/Share run, all prose/quote checks and sticky-bar occlusion still
need parent visual QA. DOM action-class counts are not visual hierarchy proof;
Home uses different primary styling. Full-page images alone cannot demonstrate
sticky-bar safety at every scroll offset. No launch readiness/sign-off claimed.
