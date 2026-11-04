# Part A Task 4 — presentation projection

Status: complete. Base: `1328093`, existing `feature/surveycoach-mvp` branch.
Commit message: `Absorb same-root findings and drop rubric bookkeeping from prose`.

## Checklist
- [x] Read the Task 4 brief before other file contents.
- [x] Add focused tests and observe RED before implementing behavior.
- [x] Implement presentation-only humanisation and same-place absorption.
- [x] Verify focused GREEN and full suite before commit.
- [x] Check diff whitespace and keep every new file under 600 lines.
- [x] Leave repository/enrichment wiring for later tasks.

## Changes
- Added `surveycoach/server/present.py` with `ABSORBS`, `humanize`, and
  `present_findings`; added `tests/test_present.py` with 37 cases.
- Explicit ID-only bookkeeping such as “This finding also covers 4.1 and 4.3.”
  becomes ordered, deduplicated criterion titles in `also_covers`.
- Ordinary prose remains verbatim, including decimal numbers, whitespace, and
  coverage-related sentences. Unknown-ID bookkeeping stays visible rather than
  silently discarding an explanation. Recognition is intentionally conservative:
  “This finding/issue also covers …” or “Also covers …”, with an ID-only list.
- Only must-fix findings in the four specified blocker families absorb lesser
  findings at the same location. Question keys include page scope; page,
  question, and survey keys cannot collide. A page-level finding never absorbs a
  question-level finding merely because both mention the same page.
- Findings retain their original order, count, severity, fingerprint, evidence,
  and other fields; absorbed findings are annotated, not removed.
- Deep copies protect stored and nested input data from consumer mutation.
- Reprojection retains humanised titles and recomputes absorption links, avoiding
  duplicate links, lost titles, or stale links after a location change.
- No existing test assertions changed; no scoring or decision safety rules changed.

## Verification
- Initial focused run: expected import failure because `present.py` did not exist.
- RED after importable API stubs:
  `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_present.py`
  — 18 failed, 19 passed. Failures identified missing prose transformation and
  absorption/projection fields rather than import or fixture errors.
- GREEN: same focused command — 37 passed in 0.24 seconds.
- FULL: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q`
  — 735 passed, 1 skipped, 1 warning in 149.49 seconds.
- `git diff --check` and staged diff whitespace checks passed.
- Line counts: implementation 74, tests 160, report 55.

## Constraints and concerns
- No delegation, worktree, push, external-service calls, or real database access.
  Full-suite tests used their local fixtures; live-model testing was disabled.
- No changes to protected `review/` or `uglyhome.png`; their pre-existing untracked
  entries remain unstaged. Only the implementation, tests, and this report are
  included in the task commit.
- The testing-router skill was loaded, but its delegation/install workflow was
  bypassed in favor of the explicitly requested no-delegation local pytest TDD.
- Existing FastAPI/Starlette warning: `httpx` test-client integration is deprecated.
  Unrelated to this projection. No implementation blockers.
