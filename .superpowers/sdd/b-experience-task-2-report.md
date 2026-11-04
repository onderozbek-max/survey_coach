# Part B Task 2 report

Status: complete. Base: `6278435`. Owner: `code-puppy-0af9a3`.
Commit message: `Add icon, word-diff and toast primitives`.

## Checklist
- [x] Read task brief first; implement Task 2 only in the supplied workdir.
- [x] Add failing Playwright tests before implementation.
- [x] Add all 18 decorative stroke-only icons through SVG namespace DOM creation.
- [x] Add deterministic word LCS diff with specified punctuation tokens, deletion-first ties,
  adjacent segment merging, 40,000-cell fallback and semantic safe-text rendering.
- [x] Add one body-level polite status region with one toast, optional one-shot Undo,
  explicit accessible dismiss button, Escape and 6-second expiry.
- [x] Invalidate replaced/dismissed toast handlers and queued old timers; clean up Escape listeners.
  Dismiss before invoking Undo so callback-created notifications survive.
- [x] Keep every new file below 600 lines (44, 31, 42 and 203 lines respectively).
- [x] Run targeted green tests and full suite before commit.
- [x] Leave existing application files, protected files, review data and untracked inputs untouched.

## Verification evidence
- System `python -m pytest` cannot run: that interpreter lacks pytest. No installation or
  external dependency fetch was attempted; used the existing `.venv/bin/python` instead.
- RED: `.venv/bin/python -m pytest tests/test_ui_primitives.py -q --tb=short`:
  36 failures, all explicit assertions for missing `SC.wordDiff`, `SC.renderDiff`, `SC.icon`
  or `SC.toast` before creating the production modules.
- GREEN: same command: 36 passed in 3.35s.
- Test-clock correction: paused Playwright's installed clock before advancing it, eliminating
  elapsed wall-clock drift in the exact 5,999ms/6,000ms assertion. No timeout weakening.
- Full suite: `.venv/bin/python -m pytest -q`:
  874 passed, 1 skipped, 1 xfailed, 1 warning in 155.65s.
- `git diff --check`: clean. New files also checked in the staged diff before commit.
- New tests use blank isolated pages, locally injected scripts, aborted network requests,
  and deterministic browser time; they do not access stored reviews or the application DB.

## Scope and concerns
- Modules intentionally remain standalone; loading them into chapter shells belongs to subsequent
  tasks. No HTML, CSS, decision persistence, API, data fixtures or protected files changed.
- Existing `open_review()` already defaults to `#improve`; `open_overview()` already exists.
- Full suite retains one skipped live test and one expected failure from the base. One warning
  reports Starlette TestClient/httpx deprecation; dependency migration is outside this task.
- Existing untracked `review/` and `uglyhome.png` are not staged or altered.
- No delegation, worktree creation, pushes or external service calls performed.
