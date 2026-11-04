# Task 1 — Evidence-led Member experience cards

Owner: code-puppy-fa63f3. Based on approved plan and HEAD 53adeda.

## Completed
- [x] Five non-time cards lead with highest-severity saved finding and exact canonical question/screen location. Equal-severity ties retain captured order.
- [x] No finding: summary names the weakest assessed check, saved credit and checked/total coverage; no dimension-wide positive claims.
- [x] Unknown summaries name dimension-specific missing evidence instead of repeating generic filler.
- [x] Details show supporting quote/explanation, other findings, assessed checks, missing checks, explicit not-applicable checks, and incomplete blocker assessments separately from the summary.
- [x] Absorbed findings remain evidence, without duplicating navigation markers. Handled decisions explicitly remain unverified fixes.
- [x] Existing time summary, state thresholds, routes, fingerprint order and screen order remain unchanged.
- [x] Native keyboard Details displays supporting evidence rather than repeating the summary; saved text renders as text, not HTML. Missing legacy details get an explicit absence message.
- [x] Canonical offline demo exporter regenerated site/data.js; no AI refresh/provider call, live visits or real DB access.

## TDD and exact verification
1. RED: `.venv/bin/python -m pytest tests/test_evidence_cards.py -q`
   - 19 failed in 0.34s, expected missing concrete summaries/coverage/details.
2. GREEN: `.venv/bin/python -m pytest tests/test_signals.py tests/test_evidence_cards.py -q`
   - 60 passed in 0.32s.
3. RED: `.venv/bin/python -m pytest tests/test_overview_ui.py -k long_signal_summary -q`
   - 2 failed, 15 deselected in 1.61s; old Details repeated summary instead of supplied support.
4. Offline generation: `.venv/bin/python -m surveycoach.demo_export`
   - wrote site/data.js from pinned synthetic fixtures/cache.
5. GREEN: `.venv/bin/python -m pytest tests/test_overview_ui.py tests/test_signals.py tests/test_evidence_cards.py tests/test_demo_export.py -q`
   - 90 passed in 5.61s.
6. Broad related checks (includes additional escaping/legacy fallback regression):
   `.venv/bin/python -m pytest tests/test_signals.py tests/test_evidence_cards.py tests/test_overview_ui.py tests/test_demo_export.py tests/test_plan.py tests/test_present.py tests/test_final_projection.py tests/test_review_projection.py tests/test_enrich_contract.py tests/test_quality.py tests/test_quality_ui.py tests/test_copy_deck.py tests/test_copy_guard.py tests/test_issue_loop_ui.py -q`
   - 228 passed, 1 warning in 11.53s.
   - Warning: existing StarletteDeprecationWarning: httpx TestClient deprecated; install httpx2 instead.
   - Chromium synthetic browser checks cover 390/759/1280 widths, no horizontal overflow, native Details keyboard expansion, route selection, preview/dialog cleanup, style updates, copy/decision loop and malicious saved text.

## Scope / integration notes
- No CSS or HTML changes/wiring needed. Existing overview.css uses shared tokens, restrained cards and native Details controls.
- Existing assessed-only state labels/thresholds deliberately preserved; coverage and explicit scope qualify them. No claim that missing AI or unchecked paths passed.
- Coverage denominator includes active scored criteria, not blockers; missing blocker evidence is separately disclosed in Details. No new score computation or model checks.
- No full-suite run or independent delegation (assigned restrictions). No screenshot-based visual claim; browser geometry/behavior assertions only.
- No reader, coach, structured-suggestion, plan or staged progress paths touched.
- Source sizes: signals.py 233, overview.js 107, test_signals.py 250, test_evidence_cards.py 82, test_overview_ui.py 315 lines; generated data.js remains one line.
- Parent should run final full nonlive integration/review after all workers finish. No new external dependencies.
