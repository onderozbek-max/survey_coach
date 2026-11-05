# Workstream 0D: Phase 0 integration fix

Branch `feature/surveycoach-mvp`. Offline only, no live calls, no push, no delegation. Method: systematic debugging. Every failure was diagnosed against HEAD before touching anything, and the 0A count changes were checked per criterion against the pre-0A commit (`0a18882^`, extracted with `git archive` into a temp dir) rather than by matching new numbers.

Starting point: 10 failures (log `shell_bg_azj6i9eq.log`). Final run: see "Final suite" at the bottom.

## Failures, diagnosis, resolution

| # | Test(s) | Verdict | Root cause | Resolution |
|---|---|---|---|---|
| 1 | `test_enrich_contract::test_scope_keeps_absent_ai_blockers_without_inventing_assessments` (4 params) and | **Stale expectation** (old number encoded two bugs) | Per-criterion diff of boxer-briefs, pre-0A vs HEAD: 2.4 (0.5 -> unassessed), 7.6 (0.75 -> unassessed), 8.6 (0.0 -> unassessed). 7.6: 0A leaves it unassessed when an image has unknown bytes, and boxer-briefs has none measured. 2.4 and 8.6: the fixture states no `required` flags. Before 0B, `required` defaulted to `True`, so those two were judged on an invented fact. After the fix below they are unassessed. Nothing else changed. | Counts 21 -> 18 and 33 -> 30. Counts now live once (`CHECKED_WITH_ABSENT_AI_BLOCKERS` in `test_enrich_contract.py`, imported by `test_chapters_ui.py`) instead of being duplicated. Added two checks that do not depend on the magic numbers: `checked + len(unchecked_checks) == total` (the total stays 48), and 2.4/7.6/8.6 are asserted unassessed and listed by title. |
| 2 | `test_chapters_ui::test_about_discloses_absent_ai_blockers[disabled-21]`, `[wording_failure-33]` | **Stale expectation** (same cause as 1) | Same fixture and same counts, shown in the About dialog. | Uses the shared constant. |
| 3 | `test_judge_schemas::test_the_batches_cover_everything_the_engine_says_is_waiting_on_ai` | **Stale expectation, tightened rather than loosened** | 7.6 ("Readable, light, and accessible") now waits on measured image file sizes, which is reader evidence, not AI work. Putting it in an AI batch would be wrong. | Added `WAITING_FOR_MEASURED_BYTES = "7.6"`. 7.6 is allowed to be pending only if a media item really has `bytes is None` (new assertion), so a 7.6 that is merely missed still fails the test. |
| 4 | `test_clean_copy::test_copy_projection_preserves_raw_snapshot_and_precleanup_hashes` | **Stale fixture, production is right** | Hypothesis tested directly: setting `required=True` on the fixture's question gives exactly the pinned hash (`39a26a5b...`, content hash unchanged). The fixture left `required` unstated, which was `True` before 0B and is `None` now, a different review input. | The fixture states `required: True`, as every capture saved before the tri-state did. The pins are unchanged, so the test now proves that old saved versions keep their identity (0B's claim). |
| 5 | `test_demo_export::test_committed_site_data_is_not_stale` | **Expected staleness** (engine output changed) | 0A/0B changed review results and served snapshot fields. | Regenerated with `.venv/bin/python -m surveycoach.demo_export` (offline, replay-only `CacheOnlyProvider`). Two runs give the same sha1. A structural diff against HEAD shows only: 2.4/7.6/8.6 unassessed on boxer-briefs; 4.4/6.3 now N/A on coffee-pods (absent categories, 0A); derived totals (quality, scorecard, overview, scope, plan counts); `stimulus_text` (empty) on pages; two `note` strings. Every new string value is engine-generated from the two synthetic fixtures; there are no URLs and no foreign copy (the only RedJade mention is the existing disclaimer). |
| 6 | `test_start_review_e2e::test_link_start_to_saved_review_preserves_partial_coverage` | **Stale fixture** (0B semantics are right) | The stubbed read claimed `pages_captured=3` but supplied no capture files. The old UI built three "Captured screen" links from that counter, which is the guessed-index bug 0B removed. The server now stores the number of persisted rendered captures, so the About text says "0 captured screens", which is correct for that input. | The stub returns three real rendered captures (synthetic bytes in `tmp_path`, pages p0 to p2). The assertions are unchanged: "3 captured screens checked" and three Captured screen links now rest on real evidence. |

## Follow-up from 0B: unknown `required` (TDD, red then green)

New file `tests/test_required_unknown_checks.py` (22 tests). Red first: 15 of 20 failed on the old code; the other 5 were negative controls that must keep passing. The 2 tests for the new `note` field were added afterwards and passed on first run.

Production:
* **8.6** (`checks/structure.py`): passes only when an open-text question near the end has `required is False`. If no question is verified optional and any open-text question has `required is None`, the result is `assessed=False`, `fraction=None`, no findings, with an evidence note. Verified required only still gets the "make the final comment optional" finding. No open text at all still gets "No optional comment box". Required plus unknown is unassessed, because the unknown one may be the optional one.
* **2.4**: counts only `required is True`. Judgment call: unknown questions are not counted as optional either, so if counting them could change the verdict (for example 2 verified required plus 1 unknown, or all unknown), the result is unassessed rather than a pass. Taking "count only True" literally would pass a survey of five unknown typing questions, which is the same bug. When the verdict is settled (for example 4 verified required plus unknown), it stays assessed. Findings name only verified-required questions.
* **Evidence note**: there was no place for a reason, so `CheckResult.note: str | None` was added. It is omitted from serialization when `None` (a wrap serializer), so every existing saved review, served payload and `data.js` entry keeps its shape. `review._with_ai` keeps the note only while the merged result is still unassessed.

Consumers (asserted through `run_review`): the unassessed 8.6 and 2.4 appear in `review.unchecked`, are not in `scorecard.strengths` or the overview strengths, and show up as unchecked points in `build_quality` (D8 `unchecked_points >= 1`, `provisional` true). A verified-optional comment is still a full-credit result (positive control). No code change was needed in strengths, quality or scope: they already require `assessed`.

## Notes for the owner

* **Sample data trade-off.** The boxer-briefs sample fixture never states `required`, so the demo no longer shows the 2.4 and 8.6 findings it used to show (they were produced from the old default of `True`). I did not edit the fixture, because stating requiredness there would be inventing capture evidence. If you want the sample to keep demonstrating those two findings, add explicit `required` flags to `fixtures/boxer-briefs.json` and run `python -m surveycoach.demo_export`.
* Real RedJade requiredness detection (0B's "Optional" leaf element) is only verified against synthetic DOM. Until it is confirmed on a real capture offline, many real surveys will show 2.4 and 8.6 as unchecked. That is the intended honest outcome.

## Two follow-on failures caused by my own 2.4/8.6 fix (found by the first full run)

Making 2.4 and 8.6 honest changed two tests that had not failed before (they passed only because of the old `required=True` default). Both were diagnosed the same way: the criteria are code-only checks, so an all-clear AI judge cannot resolve them. They legitimately wait for requiredness, which this fixture never states.

| Test | Resolution |
|---|---|
| `test_ai_review::test_all_clear_judge_resolves_semantic_blockers_but_cannot_calibrate_timing` | Unchecked set now also includes "Light typing load" and "Room to speak freely". Points are `REQUIRED_STATUS_POINTS = 2 + 1` (rubric points of 2.4 and 8.6): unchecked 6 -> 9, code-only unchecked 56 -> 59, checked 89 -> 86. Not-applicable stays 5, and checked + unchecked + N/A is still 100. Verified with a one-off script before editing. |
| `test_judge_schemas::test_the_batches_cover_everything_the_engine_says_is_waiting_on_ai` | 2.4/8.6 may be pending only while some open-text question really has `required is None` (uses the engine's own `OPEN_TEXT`). A missed check still fails. |

## Files

Production: `surveycoach/checks/structure.py`, `surveycoach/findings.py`, `surveycoach/review.py`, `site/data.js` (regenerated).
Tests: `tests/test_required_unknown_checks.py` (new), `tests/test_enrich_contract.py`, `tests/test_chapters_ui.py`, `tests/test_judge_schemas.py`, `tests/test_clean_copy.py`, `tests/test_start_review_e2e.py`, `tests/test_ai_review.py`.
Untouched: staged `.superpowers/sdd/progress.md`, untracked `review/` assets, `site/*.js` other than `data.js`.

## Final suite

`.venv/bin/python -m pytest -q -m 'not live'`: **1573 passed, 0 failed, 1 deselected (the live test), 1 warning** (the existing starlette/httpx deprecation), 4m34s.

History: the baseline had 10 failures. My first full run after the fixes had 2 failures (the follow-on pair above, both caused by the honest 2.4/8.6 change), 1571 passed. After fixing those the second and final full run was clean. So the whole suite ran twice, not once, because the first run exposed the follow-on pair.
