# Part A Task 9 — downloadable stakeholder summary

Base: `52a2e6c`. Owner: `code-puppy-3b1294`.

## Checklist
- [x] Read Task 9 brief; inspect summary route, projections, compatibility tests, and Part B Task 1 light tokens only.
- [x] Focused tests fail for missing download behavior (RED).
- [x] Implement escaped standalone attachment while retaining inline output (GREEN).
- [x] Run focused tests, full suite, and diff/safety checks.
- [x] Commit with required Task 9 message (this report is included in that commit).

## Scope
Only summary rendering, summary route, focused tests, and this report. No external calls, live DB access, delegation, worktree, push, protected review files, or uglyhome changes.

## Implementation
- `?download=1` adds an attachment filename with an ASCII lowercase slug, 80-character title bound, fallback `survey`, and integer round suffix. No title-controlled quotes, separators, CR/LF, or non-ASCII header data survive.
- No download (or `download=0`) retains the existing inline packet exactly, including its CSP; no existing assertions were changed.
- New download layout follows Headline, Member experience (six signal rows), Changes chosen, Kept on purpose, Still open, What we checked / not checked.
- Uses existing projected overview, screen naming, validated decisions and change-sheet logic. Stale picks remain open; originals do not masquerade as edits; kept risks retain explicit reasons.
- Word-level `del`/`ins` output escapes every text fragment. Add-answer edits insert the answer without deleting question wording; structural edits retain the manual-verification warning.
- Standalone light CSS copies only needed Part B Task 1 token values. No scripts, resource links, fonts, images, active URLs, or dependencies. User-supplied URLs remain inert escaped text rather than being silently removed from evidence.
- Unknown reviews, unchecked paths/criteria, unavailable AI, failed AI, and unverified launch-risk checks retain uncertainty. Estimates remain labeled; choices never certify source edits or launch approval. Inputs are not mutated.

## Verification
- RED: `.venv/bin/python -m pytest -q tests/test_summary_download.py` -> 8 failed for absent download argument/header/member-experience output.
- GREEN + compatibility: `.venv/bin/python -m pytest -q tests/test_summary_download.py tests/test_committee_rounds.py tests/test_answer_additions.py tests/test_server_contracts.py::test_summary_packet_distinguishes_earned_and_unchecked_points` -> 27 passed.
- Full suite: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q` -> **824 passed, 1 skipped** in 156.32s. Live AI deliberately disabled.
- Existing Starlette/httpx TestClient deprecation warning only.
- `git diff --check` clean. Files: report.py 231 lines, server/__init__.py 206, focused tests 134; all under 600.
- Existing untracked `review/` and `uglyhome.png` were left untouched and are excluded from the commit.

## Concerns / limitations
- No new visual browser inspection; existing full-suite browser coverage passed. Download is standalone HTML, not a promised one-page printout.
- Forbidden phrases are excluded from authored product copy; raw researcher evidence is escaped, not censored. Similarly, user-entered URLs can appear as inert text but never as executable resources.
- The report path is gitignored by existing repository settings, so it is explicitly force-added as requested; no ignore rules changed.
