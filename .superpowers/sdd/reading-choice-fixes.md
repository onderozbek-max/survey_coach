# Reading and choice-list fixes

Owner: code-puppy-542ee7

## Completed
- [x] Added red regressions before implementation (13 failed / 1 passed).
- [x] Replaced grade jargon headline with **Question wording may be hard to read**.
- [x] Details explain automated US school-grade estimate, configured grade-8 review cue, and limits: neither actual comprehension nor a scientific pass/fail test.
- [x] Added deterministic direct-verb `purchase` → `buy` swap and bounded meal-example restructure; no full-question matching or topic-based sentence replacement.
- [x] Approved meal example now produces **How often do you buy prepared meals or meal kits to heat or cook at home?**
- [x] Unknown wording gets concrete manual editing/read-aloud/study-owner steps, no fake replacement text.
- [x] Ten-choice finding now asks for a phone-layout review, explicitly calling eight a configured cue, not a research optimum or mandatory maximum.
- [x] Grouping guidance uses supplied labels (e.g. Larger tray / Smaller tray), keeps separate selectable answers, and requires owner confirmation. No sorting, merging or answer deletion.
- [x] Preserve intended order/randomization, exclusivity and routing; no invented choice text or automatic selection.
- [x] Rules-only integration regression runs the actual review pipeline on a synthetic in-memory snapshot. No AI, external survey, live capture, or user database used.

## Owned files
- `surveycoach/checks/content.py`
- `surveycoach/checks/phone.py`
- `surveycoach/checks/reading.py`
- `tests/test_reading_choice_fixes.py`
- This report

## Safety coverage
Direct verb vs noun purchase; quoted stimuli; unknown dense sentences; swapped question lead-in and category order; extra examples, category qualifiers, altered preparation logic and timeframe; ordered numeric list; unrelated options; eight-choice boundary; no mutation of questions/snapshot; no AI findings or rewrite options manufactured.

## Verification
- First new-test run: **13 failed, 1 passed**, expected old headlines/missing rewrites/list advice failures.
- First implementation focused run: **54 passed**.
- Added additional bounded-restructure negative cases.
- Broad related run: **200 passed, 3 failed**, all three failures in existing timing-promise tests while timing/structure worker changes were appearing.
- Second broad run: **198 passed, 2 failed, 2 deselected**; failures were B7 image-blocker assumptions while image worker changes were appearing. Other workers' files were not edited.
- Final stable owned/related run: **157 passed**, one existing Starlette/httpx deprecation warning:
  `.venv/bin/python -m pytest -q tests/test_reading_choice_fixes.py tests/test_checks_content.py tests/test_checks_answers_phone.py tests/test_review_projection.py tests/test_final_projection.py tests/test_present.py tests/test_copy_deck.py tests/test_demo_structured_suggestions.py tests/test_quality.py tests/test_committee_evidence_checks.py`
- `git diff --check`: clean.
- No full suite, delegation, push or user-data DB writes.

Environment note: initial `uv run` attempted dependency resolution and failed DNS; switched to existing `.venv/bin/python` for all successful test runs, without installing dependencies. System Python lacked pytest.

## Integration note for parent
The UI must render `explanation` for manual findings with no `suggested_text` (rather than only generic Make change in RedJade). This worker intentionally owns only rule generation; parent owns that UI. Existing legacy jargon-specific behavior and numeric scoring thresholds remain unchanged. Meal restructure is intentionally narrow: unsupported categories/qualifiers retain original wording apart from independently safe verb replacement. Draft advice requires study-owner verification of category scope.
