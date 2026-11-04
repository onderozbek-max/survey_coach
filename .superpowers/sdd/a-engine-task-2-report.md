# SurveyCoach Part A — Task 2 report

## Status and scope

Completed Task 2 only on existing branch `feature/surveycoach-mvp`, starting at
`308cace`. Executor: `code-puppy-866ba0`; configured model used (native tools do
not expose model selection). No delegation, worktree, push, deployment, external
service calls, or real database operations were performed. Existing `review/`
and `uglyhome.png` were left untouched and remain untracked.

## Checklist

- [x] Read `.superpowers/sdd/a-engine-task-2-brief.md` first.
- [x] Inspect existing snapshot implementation, tests and project configuration.
- [x] Capture raw snapshot identity values on base `308cace` before implementation.
- [x] Add shared JSON fixture and focused regression tests before production code.
- [x] Observe focused RED for missing cleanup and raw navigation text.
- [x] Implement only prescribed `clean_copy` and `page_copy` projection changes.
- [x] Observe focused GREEN and run full suite before commit.
- [x] Review scope, line counts and whitespace; write this report.
- [x] Prepare requested local commit, keeping branch in place with no push.

## Files and behavior

- `surveycoach/snapshot.py` (165 lines): added prescribed case-insensitive
  `_NAV_TAIL` and pure `clean_copy`. Normalize NBSPs, strip repeated standalone
  trailing navigation labels, remove whitespace before newlines, collapse runs
  of 3+ newlines to a paragraph break, and strip outer whitespace. `page_copy`
  cleans intro/page/info-question text separately before ordered deduplication;
  empty cleaned parts and non-info question text are excluded.
- `tests/fixtures/clean_copy_cases.json` (14 lines): all five exact brief examples,
  plus empty/whitespace inputs, repeated mixed-case navigation labels covering
  all eight supported labels, and safeguards for inline/nontrailing labels and
  ordinary navigation-like prose. Shared two-item `[raw, expected]` format is
  ready for Part B's JS mirror; no JS changes in this task.
- `tests/test_clean_copy.py` (63 lines): 12 parametrized fixture cases plus intro
  projection, clean-before-deduplicate ordering, and immutable raw/hash identity
  regression tests (15 tests total).
- This report: execution, verification, scope and concerns.

No existing tests required updates. In particular, existing inline `... Next`
assertions remain valid because the required matcher only removes standalone
trailing navigation lines. No safety assertions were weakened.

## Identity and immutability evidence

`review_hash` and `content_hash` implementations and their inputs are unchanged.
The new identity test asserts literal preimplementation values for the brief's
Halloween snapshot:

- `review_hash`: `39a26a5bbe2168af793a7057b8de595a7ecb3da2cf711d3a96a26a8e6ce3f6be`
- `content_hash`: `0f124be939b89a9f533c10144f4beb95dfad362703f3850b0c3ebf0ff4d136da`

After reading projected copy/role, raw model dumps, round-tripped raw JSON and
both identities remain unchanged. A separate deep copy with the cleaned text
written into its capture produces different hashes, confirming identity still
tracks raw content rather than presentation. No validators, readers, repository,
review, decision/history, or hashing logic were edited.

## Verification (executed locally)

1. RED, before production changes:
   `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_clean_copy.py`
   Result: **15 failed in 0.22s**, exit 1. Twelve fixture tests failed because
   `clean_copy` did not exist; three projection tests failed because raw trailing
   `Next`/blank lines and pre-cleaning duplicates remained. Tests collected
   normally; these were expected missing-feature failures, not import errors.
2. GREEN:
   `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_clean_copy.py tests/test_snapshot.py tests/test_committee_trust_engine.py`
   Result: **68 passed in 0.22s**, exit 0.
3. Full suite before commit:
   `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q`
   Result: **692 passed, 1 skipped, 1 warning in 147.19s**, exit 0.
   The live-provider test was explicitly disabled; existing browser/API tests
   use local fixtures and temporary/in-memory databases. No live RedJade/LLM
   workflows were invoked.
4. `git diff --check`: passed. All changed/new files remain below 600 lines.
   Reviewed production diff: only the cleanup helper and page-copy projection.

## Concerns / follow-up

- No task blockers or regressions found.
- Existing dependency warning: Starlette's httpx TestClient integration is
  deprecated in favor of httpx2. Out of scope; no dependencies changed.
- Inline navigation text is intentionally retained by the prescribed regex.
  Changing that would risk deleting legitimate prose and is outside this task.
- Part B must consume the shared fixture when implementing its JS mirror.
- Skill routing normally requests delegation; explicit user prohibition took
  precedence. Used the required local TDD workflow directly; no skill installs
  or external registry calls.
- `.superpowers/` is ignored by repository rules. This report is force-added
  explicitly so it travels with the requested task commit; no other ignored
  planning artifacts are staged.

## Commit

Requested message: `Strip navigation labels and blank-line runs from screen copy`.
This report is included in that commit. Resolve its exact ID with
`git log -1 --format=%H -- surveycoach/snapshot.py` (avoids a self-referential
commit hash inside committed report content).
