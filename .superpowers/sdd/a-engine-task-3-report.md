# Part A Task 3 — stale-pick explanations

Status: complete. Base: `a41c258`, existing `feature/surveycoach-mvp` branch.
Commit message: `Flag picks invalidated by improved suggestions`.

## Checklist
- [x] Read task brief first; loaded TDD skill before implementation.
- [x] Added focused tests and observed expected red before production change.
- [x] Added explanation fields only in `valid_decisions`' invalid-pick branch.
- [x] Verified focused green and full suite before commit.
- [x] Checked diff whitespace and changed-file line counts (<600 each).

## Changes
- An unavailable saved pick projects to `action="open"`, `picked_text=None`,
  `manual_done=False`, `stale_pick=True`, and `previous_text=<saved text>`.
- Still-offered suggested text and option text retain their valid pick unchanged,
  without stale explanation keys.
- Tests cover saved-input immutability, repeatable projection, metadata retention,
  and unchanged non-pick actions. No existing assertions were changed.
- No storage writes or accept/copy/keep safety rules were changed.

## Verification
- RED: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_stale_pick.py`
  — 1 failed, 5 passed. Failure was exactly the missing `stale_pick` and
  `previous_text` fields.
- GREEN: same focused command — 6 passed.
- FULL: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q`
  — 698 passed, 1 skipped, 1 warning in 150.67 seconds.
- `git diff --check` passed.
- Line counts: `rounds.py` 328; `test_stale_pick.py` 58; this report <600.

## Constraints and concerns
- No delegation, worktree, push, external service calls, or real database use.
  Live-model testing was explicitly disabled; the suite uses its local fixtures.
- Existing untracked `review/` and `uglyhome.png` were left untouched and unstaged.
- The test-orchestrator skill was loaded, but its delegation/install workflow was
  not followed because the task explicitly prohibited delegation/external calls;
  the requested local TDD workflow was followed directly.
- Only warning: installed FastAPI/Starlette test-client deprecation concerning
  `httpx`; unrelated to this task. No implementation blockers.
