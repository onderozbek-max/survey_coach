# SurveyCoach assessment clarity implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans. Track steps below.

**Goal:** Implement Onder's approved energy explanation, prominent style, transparent quality score, positional navigation and managed-network diagnostics.
**Architecture:** Extend immutable server projections, reuse the existing weighted rubric and vanilla JS components; no framework migration. Server owns calculations, UI owns rendering and positional navigation.
**Tech Stack:** FastAPI, SQLite, Python, vanilla HTML/CSS/JS, pytest and Playwright.

## Global constraints
- Existing non-LD codebase: preserve architecture and verified light tokens; WCAG 2.2 AA keyboard/touch/dialog behavior.
- No live survey reads, participant writes, publication, push, deployment, or freeze bypass. Original screenshots and uglyhome.png untouched.
- No stored review/decision mutation for projected scores. Accepted changes cannot increase assessed score before recheck.
- Preserve already staged progress.md; commit only named feature paths. Source modules below 600 lines.
- Score: earned assessed applicable points / assessed applicable points * 100. Show separate coverage against applicable rubric weight, provisional when incomplete, null when nothing assessed; independent blocker warnings. N/A excluded, absent checks included as unknown. Rounded display is not extra precision.

### Task 1: Queue positional navigation
Files: site/queue.js, tests/test_queue_position.py; existing queue tests.
- [ ] Add failing browser regressions with synthetic data: initial first open item, click third must-fix, jump third quick-win, handled progress distinct, More ideas positional too.
- [ ] Run `.venv/bin/python -m pytest tests/test_queue_position.py -q` and confirm failure.
- [ ] Replace tab decision fraction with active-item position / full tier total; inactive tabs show total only. Keep separate handled progress. Browser-selected items must sync active tier/index. Initial fresh queue starts first; don't reset deliberate inspection on redraw.
- [ ] Run new + existing queue tests, commit named files.

### Task 2: Quality projection
Files: surveycoach/quality.py, surveycoach/server/present.py, server/repository.py listing, server/summary.py download, tests/test_quality.py.
Interface: `build_quality(review: dict, rubric) -> dict`; inspect review result representation before implementation. Payload `quality` includes score/null, coverage_percent, assessed_points, applicable_points, unchecked_points, provisional, dimensions, blocker counts, basis/method version. Reuse rubric criterion weights, not duplicate constants. Recompute from immutable check results, not the old raw score or curated findings count.
- [ ] Add deterministic fixtures asserting half-credit normalization, unknown coverage, N/A exclusion, zero assessed null, full coverage, missing blocker disclosure, stable score under picks/keeps.
- [ ] Run focused tests red, implement projection and canonical enrichment/list/download wiring, run green. Update synthetic demo via scripts exporter only, never private DB. Commit named files.

### Task 3: Explanations and score UI
Files: site/quality.js, site/quality.css; site/overview.js, local.html, entry.js, review.html, index.html, share.js, about.js, app.js; tests/test_quality_ui.py and overview tests.
- [ ] Add browser tests for quality card, list/Share/header consistency, provisional/no-check states, methodology dialog keyboard Escape/focus return, non-hover mobile operation, hidden chapters no duplicate IDs.
- [ ] Add Energy map info button explaining real TimingConstants: words*.3 seconds, question interaction base/options, image3s, grid row4s, screen1.5s; color at cumulative180s/10 questions and420s/20 questions, uncalibrated captured route limitations. Derive constants server-side where practical to avoid drift. Small accessible popover/dialog usable hover/focus/tap with dismiss/return focus.
- [ ] Move Survey style below title before assessment, keep compact and truthful: local length/tone updates do not rerun saved AI. Preserve stale decision/style refresh protections.
- [ ] Render restrained quality card on Overview, compact list/header and Share, footer methodology modal link. Score not readiness, not outcome prediction; must-fixes remain prominent. AI caveat and coverage explained, no invented improvement from decisions.
- [ ] Run focused browser regressions plus claims guard; update guard to permit explicitly approved quality scoring, never blanket-disable guard. Commit named paths.

### Task 4: Reader managed-network diagnostics
Files: surveycoach/reader/proxy.py, transport.py, server/reader.py; tests/test_reader_proxy.py and reader job tests; README.md.
- [ ] Reproduce known setup using DNS-only check: current Mac PAC enabled, direct app.redjade.net resolution fails, explicit proxy env unset. Do not open real survey URL.
- [ ] Tests red: explicit approved proxy retained; unapproved proxy fails closed; supported macOS managed proxy detection explicit opt-in or narrowly trusted configured route; DNS resolution failure surfaced distinctly from unsafe address/policy and timeout.
- [ ] Implement safe diagnostics/setup, never execute PAC JavaScript/download arbitrary URLs, disable TLS/SSRF checks, or silently use arbitrary proxy env. If reliable auto-selection not possible, provide exact documented approved proxy startup command and actionable UI error. Preserve existing host allowlists and bounded transports.
- [ ] Test offline with mocked DNS/proxy/network platform, run reader security suite. Commit.

### Task 5: Final integration
- [ ] Full `.venv/bin/python -m pytest -q -m 'not live'`, `git diff --check`, file-size checks.
- [ ] Independent code review; fix important findings with regressions.
- [ ] Synthetic real-browser QA for queue index/style/quality/modal at desktop/mobile, no sensitive data. Regenerate captures only under review/after with synthetic temp DB; preserve originals.
- [ ] Keep branch local. Explain full app requires server; no Puppy Pages/deployment during freeze without approved route. Record actual tests, limitations and local preview URL.
