# Part A Task 6 report — plan curation

Base: `c3b6fea` on `feature/surveycoach-mvp`.

## Checklist
- [x] Read Task 6 brief first and inspect branch / existing conventions.
- [x] Write focused tests and observe RED before implementation.
- [x] Implement pure build_plan projection only.
- [x] Verify focused GREEN and full suite.
- [x] Review diff and constraints; commit with prescribed message.

## Implementation

Added `surveycoach/server/plan.py` with `build_plan(findings, decisions, points,
screens)`. All visible must-fix findings remain individual; other findings group
by criterion and case/whitespace-normalized headline. Criteria 9.1/9.2 are
nice-to-have ideas regardless of points unless explicitly must-fix. Improve
patterns rank by rubric points descending, then screen order; only six enter
quick_wins. Remaining improve patterns precede nice-to-have patterns in more.
Absorbed findings never enter lists or counts.

A plan item is decided only when every member has an explicit action of pick or
original, or keep with a nonblank reason. Mere pick metadata is not a decision.
Counts describe plan items, with open_must_fix counting undecided blockers.
Inputs are read-only; outputs contain fresh lists/dicts, not references to input
collections. No repository integration, persistence, UI or unrelated task work.

## Tests

- Initial RED: focused test collection reported the missing plan module.
- Added only a NotImplementedError API scaffold; reran focused tests:
  **21 failed** because plan curation was not implemented (before behavior code).
- GREEN: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_plan.py`
  → **21 passed**, 0.27 seconds.
- Full: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q`
  → **769 passed, 1 skipped, 1 warning**, 147.10 seconds.
- Coverage includes 12-item sentence-case pattern, individual B2 blockers,
  ranking/cap/overflow, both nice-to-have criteria, absorption, explicit choices,
  all-members decision semantics, grouping boundaries, location fallback,
  empty counts, repeatability, input immutability and output isolation.
- No existing tests or assertions changed or weakened.

## Constraints / concerns

No delegation, worktree, push, external/model calls, live database access or
protected-file changes. Existing untracked `review/` and `uglyhome.png` remain
untouched. New Python files: plan 69 lines; tests 145 lines (both below 600).
The report is in the existing ignored .superpowers tree and is force-added
explicitly; no unrelated ignored files staged.

Only warning: existing Starlette TestClient/httpx deprecation. The single skipped
test is the opt-in live-model test. No Task 6 blockers or behavior deviations.
Test-orchestrator delegation/install workflow was bypassed in favor of the user's
explicit local-only/no-delegation instruction and requested TDD skill.
