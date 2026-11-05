# Root-cause prevention audit — 2026-11-04

Backend owner: code-puppy-1272b4. Baseline: `1418117`. Scope: backend, focused tests, this report; UI belongs to parent.

## Why the seven problems happened

| Problem | Concrete cause and previous test gap |
|---|---|
| Inflated time | Raw page capture and structured question/help/options were treated as additive reading. Fixes repaired timing, including overlapping intro containers, but feature tests concentrated on ordinary choices; grid rows and scale labels had no representation-parity contract. |
| False missing welcome | Welcome inference relied on narrow greeting patterns rather than boundary + grounded purpose/invitation. Existing idealized intro fixtures did not exercise the actual invitation wording or system-screen negatives. Prior fix is retained; no new detector change needed. |
| Reading difficulty / unusable rewrite | Rubric/grade jargon escaped into member-facing advice; generating a finding did not require either a safe grounded rewrite or concrete manual action. Prior bounded rewrites and manual-action tests are retained, not replaced by speculative text generation. |
| Empty recommendation view | Empty results, hidden category and handled decisions were collapsed in presentation. Backend cannot infer whole-survey safety from an empty findings list. Existing scope/signals evidence contracts remain; parent owns UI states. |
| Unexplained colours | A cumulative-effort heuristic looked like issue severity. Timing and findings are separate inputs; the UI had not explained that distinction. Parent owns legend/display; no numeric model recalibration invented here. |
| “Cut ten choices to eight” | A configured layout threshold was promoted into a research optimum and an instruction to delete answers. Prior text-choice fix did not cover parallel image-choice advice, which still said “use 6.” |
| Image declared broken | Reader capture state was promoted into a member-facing failure and speculative cause. B7 was corrected, but 6.5 retained an independent, finding-free quality deduction for the same unloaded observation. Tests checked B7 alone. |

These were representation/evidence/copy-contract gaps, not seven independent researcher errors. Existing tests often pinned local output rather than comparing consumers of the same evidence.

## Achieved in this audit

- **Reading parity:** `timing._answer_labels` supplies both reading cost and raw/intro subtraction. Grid rows and scale labels now count with or without raw capture; endpoint metadata duplicated in full scale labels/options counts once. Exact extra raw occurrences remain reading; no semantic deduplication. Overview/signals already call the same `estimate`, so receive the correction without another calculator.
- **No hidden capture penalty:** 6.5 assesses its observed link/truncation conditions only. Unloaded images neither deduct points nor dilute real layout problems. B7 keeps its unassessed, worth-improving observation and phone-verification action; confirmed tiny loaded choices still retain must-fix behavior.
- **Unknown stays unknown:** numeric fraction plus `assessed=False` no longer allows ready or disappears from unchecked disclosure. Unassessed N/A stays unknown in score, normalized quality and scope; only assessed N/A is excluded. Partial JSON cannot manufacture assessed quality/blocker coverage through default `True`. Genuine assessed passes, failures, N/A and confirmed blockers retain existing behavior. No schema/framework added.
- **Parallel advice repaired:** 7.5 image-choice count remains a configured scoring/review cue, but no longer tells researchers to delete answers. It requires phone verification and preserves distinct answers, order, randomization, exclusivity and routing; no fake pasteable rewrite. Absolute “prettiest photo wins” claim removed.
- **Regression guard:** 23 new parametrized cases cover ordinary choices, dropdowns, ranking, grids, rating, slider, scale metadata overlap, extra occurrences, snapshot immutability, B4/B7 and multiple weighted dimensions. Existing recommendation tests cover grounded/manual actions and no placeholders. Two old fixture expectations were corrected: rows include label reading; explicit N/A fixture now explicitly sets assessed.

## Verification

- Initial new regressions: **13 failed / 5 passed**, before implementation.
- Additional scope regression: **1 failed / 18 passed**, before scope fix.
- Parallel image-choice advice regression: **1 failed / 19 passed**, before copy fix.
- Final focused offline command: **354 passed in 1.53s**, one existing Starlette/httpx deprecation warning:

```sh
.venv/bin/python -m pytest tests/test_root_cause_invariants.py tests/test_timing.py tests/test_timing_welcome_fixes.py tests/test_scoring.py tests/test_quality.py tests/test_checks_answers_phone.py tests/test_checks_images.py tests/test_review.py tests/test_review_projection.py tests/test_recommendation_quality.py tests/test_reading_choice_fixes.py tests/test_image_load_uncertainty.py tests/test_committee_trust_engine.py tests/test_committee_evidence_checks.py tests/test_signals.py tests/test_enrich_contract.py tests/test_ai_review.py tests/test_present.py -q
```

Changed production files are 53–350 lines, below 600. Named-path diff whitespace check passes. No full suite, live calls, vendor responses, actual database, deployment, push or delegation. Test-only synthetic temporary/in-memory repositories are used by existing focused tests. Unrelated staged progress and parent UI edits are excluded from commit.

## Deferred / remaining risks — not claimed fixed

1. **Parent UI handoff:** `site/energy.js:SC.previewReadingDelta` separately sums intro, raw, question/help/options and skips dropdown/grid options: duplicate rewrite savings remain possible. `SC.pageTexts`/preview word-count consumers also need representation-parity tests. Backend overview timing itself uses `estimate`; no site code edited here.
2. Exact option/row/scale subtraction requires whole-line evidence; flattened labels intentionally remain conservatively counted. Partial scale labels may not establish actual visual repetition. No semantic collapse or global word deduplication is safe.
3. Other fixed phone/grid/word/image-size thresholds still produce heuristic scores; this audit did not validate them scientifically or comprehensively rewrite every rule. Do not treat a low score as measured member difficulty. Image shape/resolution availability is not a complete accessibility/layout assessment.
4. `loaded: bool` cannot represent all media diagnostic states. No schema overhaul attempted. B7 verification still needs actual-phone evidence; AI text review must not clear it. Existing non-AI ownership tests pass.
5. Legacy projection can still validate partial saved dictionaries with today's model defaults; direct quality/scope projections are now conservative, but migrating historical evidence requires a separately scoped policy. No user history rewritten.
6. Timing remains uncalibrated captured-screen effort, not measured completion or a reliable member route. No actual survey duration or revised review result claimed; no saved capture/DB was opened or regenerated.
