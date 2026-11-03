# Committee improvements implementation plan

> **For agentic workers:** Use subagent-driven-development with focused ownership, regression tests and integration review.

**Goal:** Turn the phone-first checker into a clear, trustworthy member-experience review and round-based change loop.
**Architecture:** Preserve vanilla browser UI and FastAPI/SQLite. Separate reusable issue presentation, journey preview and round comparison from orchestration. Historical snapshots remain immutable; corrected read-time review projections must be explicit and conservative.
**Tech Stack:** Python, Pydantic, SQLite, vanilla JS/CSS, Playwright, pytest.

## Constraints
- Keep phone preview central, source text honest, all unvisited paths explicitly unknown.
- No live survey reads, AI requests, production changes or mutations of user's saved review during QA.
- Preserve API compatibility; files below600 lines; no framework migration.
- Preview rewrites never silently accept choices. Use this explicitly saves and copies.
- Keep mine acknowledges risk; does not certify correction. No blockers found means within checked scope only.
- Future benchmarks, empirical drop-off and hosting need data/access and are not fabricated.

## Checklist
- [x] 1 Trust/methodology engine: regression tests for info welcome/ending, unknown strengths, validated scales, typing contradictions, grounded time corrections and independent AI findings; implement and run focused tests.
- [x] 2 Round loop API: stable conservative issue matching, carry decisions only when applicable, detailed fixed/still/new and uncertainty, title rename, known-link reuse, readable sign-off/change sheet. Tests before code.
- [x] 3 UI clarity: no competing tabs/decision forms; one issue component with Use this/Keep mine reasons; triage grouped issue navigator, plain vocabulary, verdict sentence and scope, next issue, title edit, round timeline, prefilled recheck and sticky action bar.
- [x] 4 Member experience: clickable effort journey using observed timing, original/rewritten synchronized comparison and local playback with honest estimates; lightweight fatigue/answer-integrity checks; progress stages from actual reader state only.
- [x] 5 Entry: consent by button, truthful reader mode, one full example, technical imports out of primary path; align README.
- [x] 6 Integration: unit/API/browser suite, actual saved review read-only desktop/mobile visual QA, independent code review, fixes, full suite and diff check; commit explicit files, leave uglyhome.png alone.

## Interfaces and verification
- Existing detail response gains optional `round_changes` with fixed/still/new lists and `carried` decision metadata. Older fields retained.
- Existing decisions keep persisted actions for compatibility; presentation maps to Use this/Keep mine.
- PATCH /api/surveys/{id} with title validates length and nonempty text.
- UI uses SC.workspaceDetail, existing events and decision revisions; no duplicate state writers.
- Run `.venv/bin/python -m pytest -q` and `git diff --check`.
- Browser checks synthetic saves only; existing library GET and navigation only.

## Verification result

Full suite: **660 passed, 1 skipped, 1 warning** in 146.24s. The warning is the existing Starlette/httpx deprecation. `git diff --check` clean. See `docs/superpowers/specs/2026-11-03-committee-delivery.md` for exact delivery boundaries and visual-QA limitations.

## Delivery boundaries
Implement phases0–3 using available captured evidence. The later proof phase (measured source accessibility, routing-wide timings, respondent benchmarks) must remain explicitly not checked until data collection exists. Do not claim captured images or predicted completion percentages.
