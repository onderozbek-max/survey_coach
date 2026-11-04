# Evidence cards and structured suggestions implementation plan

> **For agentic workers:** use executing-plans or subagent-driven-development task-by-task.

**Goal:** Implement user-approved concrete Member experience cards and question/answer recommendation formatting; diagnose failed reader without participant writes.
**Architecture:** Pure server overview projections supply evidence, UI renders semantic structure without changing original suggestion/copy/decision text. Reader diagnosis uses saved local metadata, never infers authentication from empty pages.
**Tech Stack:** Existing Python/FastAPI/SQLite, vanilla HTML/CSS/JS, pytest/Playwright.

## Global constraints
- No deployment/push, original screenshots/data untouched, no participant mode activation, no real survey visits without test-link approval.
- Immutable stored reviews and snapshots, stable fingerprints and decision/copy/stale protections.
- Existing non-LD application stays vanilla, token styles, WCAG2.2AA, source files under600 lines.
- Do not include preexisting staged progress.md or other workers' paths in commits; commit --only named files.

### Task 1: Evidence-led Member experience
Files: surveycoach/signals.py (extract helper if cohesive), site/overview.js, tests/test_signals.py and new evidence card regressions.
- [ ] Add failing tests: five non-time signals have specific summaries derived from related finding headline+canonical location; unknown explains missing dimension evidence; checked good summaries scoped to assessed evidence. Preserve no false pass. Details differ from summary.
- [ ] Implement prioritized evidence (must-fix before lower severity, captured order deterministic), exact labels for scoped findings, per-signal checked/unknown coverage and supporting details. Use direct evidence, not invented recommendations or repetitive prose. Existing route finding/page links remain compatible.
- [ ] Run red/green signal/overview/browser regressions. Regenerate synthetic demo offline canonical exporter only. Commit own paths and report exact tests.

### Task 2: Structured recommendations
Files: site/coach.js, new site/suggestion.js if needed, site/review-studio.css or dedicated stylesheet, html script loading, new tests/test_structured_suggestions_ui.py.
- [ ] Add failing tests for real structural suggestion format, question-only, answer-only/add_answer, alternatives, malicious text escaping, exact clipboard/persisted text unchanged, ambiguous bundle fallback.
- [ ] Parse only explicit known question/answer structure (inspect existing structural helper/schema first). Render labelled Question plus semantic Answer choices list; retain diff for plain wording, don't guess at sentence boundaries, preserve exact underlying text for act/copy. Handle structural old/current vs chosen diffs without duplicating or hiding removed wording. UI presentation not persistence migration.
- [ ] Run red/green targeted Improve/phone/copy/stale tests; commit named files, report.

### Task 3: Reader diagnosis
Files: reader/session.py/server/reader.py only if concrete cause identified, tests feature-specific.
- [ ] Inspect exact running56226 server log and saved job status/coverage only; no full preview URL or survey body dumped to outputs. Determine blocked startup vs browser exception/HTTP/empty title.
- [ ] Reproduce concrete exception offline, add failing regression before code fix. Never enable participant writes or weaken SSRF/TLS/blocklists to capture content. Improve safe actionable diagnostics on empty content, persist bounded sanitized failure classification if needed.
- [ ] Run focused reader regressions; if real test-link required explain limitation, ask only consequential missing authorization.

### Task 4: Integration
- [ ] Independent review and fix important issues, full nonlive pytest, diff/source-size checks.
- [ ] Synthetic browser desktop/mobile flow/copy/dialog evidence. New local preview with actual approved-proxy env retained, originals untouched, no stale-server overwrite or DB deletion.
- [ ] Final report distinguish UI implemented, actual cause diagnosed, survey read still unverified if no approved real link.

No accumulated-effort visualization change in this scope: user currently explicitly requested cards and structured suggestion implementation; current fatigue estimation remains as-is.
