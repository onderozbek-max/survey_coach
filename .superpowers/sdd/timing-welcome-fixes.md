# Timing + welcome fixes

Owner: code-puppy-5b9196

## Checklist
- [x] Read timing, snapshot, structure, and existing regression contracts.
- [x] Add failing deterministic offline feature regressions before implementation.
- [x] Verify RED: 15 failures / 9 passes for the missing behavior; an additional conservative-option regression later failed as expected (1 failure / 24 passes).
- [x] Implement exact page-local reading deduplication and grounded boundary welcome detection.
- [x] Replace unsupported length advice with estimate/guideline/pilot language.
- [x] Prevent uncalibrated member-facing time rewrites while preserving calibrated and uncertain-route guards.
- [x] Focused GREEN: 132 passed; no live services or full suite.
- [x] Check owned diff whitespace and source size (all changed source <600 lines).

## Implementation
- Timing subtracts one exact captured occurrence per represented question/help field, with whitespace normalization only; case and punctuation remain significant. Page-local accounting preserves repeated questions on separate pages and extra occurrences on one page. Unique concept stimulus and semantic paraphrases remain counted.
- Options require exact whole-line matches, avoiding subtraction of ordinary option words such as `Never` inside unique concept prose. This deliberately favors retaining ambiguous prose over aggressive deduplication; flattened option strings without line boundaries may conservatively remain counted.
- Intro text duplicated in raw capture is counted once. Interaction/media/page overhead constants are unchanged.
- First question-free info pages now recognize a grounded exploration/purpose plus an input/feedback invitation, including the actual cooking-up-meal-ideas wording and curly apostrophes. System/loading screens cannot become welcomes even when saying `Welcome`; middle concept and answerable pages stay excluded.
- B4 provides a short survey-title-scoped example (generic if no usable title), explicitly asking the researcher to verify purpose. No invented timing, reward, or placeholder tokens.
- 2.1 labels estimated member completion separately from crawl/load time, names the configured survey-type guideline, identifies uncalibrated estimates, and requests a timed pilot before shortening. Removed the unsupported completions/goodwill claim.
- 1.4 no longer emits an unverified member-facing duration promise from an uncalibrated estimate. Calibrated linear routes retain rewrite support; uncertain-route suppression and B5 calibration guards remain unchanged.

## Verification
Command:

```sh
.venv/bin/python -m pytest tests/test_timing_welcome_fixes.py tests/test_timing.py tests/test_snapshot.py tests/test_checks_structure.py tests/test_committee_trust_engine.py tests/test_actionable_findings.py tests/test_clean_copy.py -q
```

Result: **132 passed in 0.34s**. Updated three legacy timing assertions that previously required unverified promises. Initial system `python` lacked pytest; used the existing project virtualenv instead, with no installation.

Owned implementation: `surveycoach/timing.py`, `surveycoach/snapshot.py`, `surveycoach/checks/structure.py`.
Owned feature/contract tests: `tests/test_timing_welcome_fixes.py`, timing-only assertions in `tests/test_actionable_findings.py` and `tests/test_committee_trust_engine.py`.

No external/live/real-database/user-data changes, delegation, or push. Other workers' UI/content/phone/image changes and staged progress are intentionally excluded from the commit.

## P2 review follow-up: overlapping representations (c2a7e47)

Owner: code-puppy-6d6eda

- [x] Reproduce the reported intro-container bug before implementation: **4 failed, 27 passed** in the feature regression file. Failures covered the exact 8.1-to-10.2-second reproduction and repeated question/help/option fields following a removed intro.
- [x] Track unmatched structured fields while subtracting them from intro reading. If raw includes the full intro, that removed container already covers its matched structured fields; only unmatched fields may be subtracted again from raw. If the full intro is absent, raw retains its independent structured-field subtraction.
- [x] Assert intro/structured overlap counts once (8.1 seconds), while a legitimate extra seven-word question contributes 2.1 seconds (10.2 total). Also retain both occurrences when the intro itself contains the question twice, and cover absent-full-intro behavior.
- [x] Focused GREEN: **118 passed in 0.48s**, using the existing virtualenv:

```sh
.venv/bin/python -m pytest tests/test_timing_welcome_fixes.py tests/test_timing.py tests/test_checks_structure.py tests/test_committee_trust_engine.py tests/test_actionable_findings.py -q
```

`git diff --check` passed for implementation/tests. Scope for this follow-up is only `surveycoach/timing.py`, `tests/test_timing_welcome_fixes.py`, and this named report; no UI, live services, full suite, delegation, database/user-data changes, or push. Commit uses `--only` to preserve unrelated staged work.
