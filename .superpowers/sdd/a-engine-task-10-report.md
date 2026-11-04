# Part A Task 10 - forbidden-claims guard

Base: `5d5da32`. Owner: `code-puppy-cc0d94`.

## Checklist
- [x] Read Task 10 brief first; inspect repository state and existing test conventions.
- [x] Write scan and observe expected RED on the old local.html hero.
- [x] Add strict, exception-specific xfail pending Part B Task 10.
- [x] Verify prescribed source coverage, generated-data exclusion, and error visibility.
- [x] Run focused tests, full suite, and diff/scope checks.
- [x] Include this report in the local commit with the required message.

## Scope and implementation
Only `tests/test_copy_guard.py` and this report were added. No production copy or existing assertions changed.

- Scan all top-level `site/*.html` and `site/*.js`, excluding generated `data.js`, plus `surveycoach/server/report.py` and `surveycoach/signals.py`.
- Use the exact prescribed case-insensitive regular expression. Findings include relative path, line number, and matched phrase.
- Assert HTML and authored JavaScript discovery is nonempty to prevent a vacuous pass. Required Python files are read explicitly, so a missing file fails.
- Complete every source read before raising the dedicated `ForbiddenClaimError`.
- `xfail(strict=True, raises=ForbiddenClaimError)` applies only to the product-copy assertion. File/decode errors and ordinary assertions are not expected failures. A clean scan becomes a failing XPASS until Part B removes the marker.
- Four parameterized synthetic cases exercise each prescribed source category and every phrase, including case-insensitivity and both dropoff spellings. They prove generated data and nested assets are excluded.
- Additional tests verify missing HTML raises an ordinary assertion and missing Python files remain errors even after an earlier forbidden phrase.

## Verification
- RED: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_copy_guard.py` -> **1 failed, 4 passed**; the failure was exclusively `site/local.html:20: actually finish`.
- Focused final: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_copy_guard.py -rx` -> **6 passed, 1 xfailed**.
- Full suite: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q` -> **830 passed, 1 skipped, 1 xfailed**, 155.52 seconds.
- Existing Starlette/httpx TestClient deprecation warning only.
- No delegation, worktree creation, push, external service calls, live DB access, protected-file edits, or model override tool use. Existing full-suite browser tests use their synthetic local fixtures.
- Existing untracked `review/` and `uglyhome.png` remain untouched and excluded from the commit.
- Report path is already gitignored; explicitly force-add only this requested report. No ignore rules changed.

## Concerns / handoff
- The old hero is deliberately unchanged. Part B Task 10 must sweep the copy and remove the strict xfail marker.
- While the known hero remains, other forbidden phrases also produce the same expected claim failure; the scan still lists all matches. This is the requested temporary whole-scan xfail, not an active per-file regression gate until Part B.
- Scope intentionally follows the prescribed top-level source patterns; CSS, nested assets, generated evidence, and other Python modules are not scanned.
