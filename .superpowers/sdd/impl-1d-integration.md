# Integration 1D: Phase 1 (1A status, 1B site, 1C copy) merge fixes

Branch `feature/surveycoach-mvp`, start HEAD `b606565`. Offline only, no delegation, no push.
Baseline for classification: commit `6554188` (pre-Phase-1) in a throwaway `git worktree` under `/tmp` (no stash, checkout or reset in the shared tree).

Starting point: 15 failed / 2359 passed. On `6554188` the same 7 test files give **56 passed, 0 failed**, so none of the 15 is flaky or environmental. Every one was caused by Phase 1.

## Per-failure table

| # | Test | Class | Root cause | Fix |
|---|---|---|---|---|
| 1 | `test_actionable_findings::test_one_intro_finding_requests_verification_without_inventing_promises` | (b) stale copy | 1C headline went from "Intro needs its 3 min promise checked and lacks confirmed reward terms" to "Welcome promises 3 min; check the time". The unknown reward is still in the evidence. | Assert the new headline, that the evidence still says the reward is unknown, `suggested_text is None` (no invented time on an uncalibrated route), and the new action contract (`action_kind == "steps"`, first step is a timed run). Original "timed run" and "calibrated" assertions kept. |
| 2 | `...::test_unverified_image_names_capture_without_hidden_layout_penalty` | (b) stale copy | B7 headline is now "Check that this image shows up on a phone" (banned word `reader`, brief 1C). The image name and "reader observed ... cause not measured" moved to the evidence. | Assert image name and `element_id` in evidence/finding, headline asks for a check, evidence says "not measured", action is a `you_check`. All scoring assertions untouched (B7 pending, 6.5 not penalised, strength kept). |
| 3 | `...::test_the_time_overrun_is_reported_even_though_it_is_below_the_blocker_threshold` | (b) stale copy | Same 1.4 headline change ("promise checked" is now "check the time"). | Assert "check the time" in the 1.4 headline. B5 absence and the evidence assertion unchanged. |
| 4-6 | `test_capture_screens::test_real_server_cleanup_on_exception_and_actual_group`, `test_manual_qa_server_sigterm_cleanup`, `test_real_capture_all_views_and_preserves_originals` | (b) stale fixture and script (not production code) | Two causes. (i) `pattern_snapshot()` relied on three different "Select all that apply" pastes grouping. 1C groups only identical actions (different rewrites never merge, a safety contract), so the seed found no group and raised "Expected a real grouped item". (ii) After seeding, `capture()` clicked `[data-chapter=share]` directly; at 390px 1B collapses the steps into the step menu, so the link is hidden (30 s timeout). | (i) `pattern_snapshot()` now gives the three distinct questions the same answer label with an emoji, so the real engine raises 9.1 "Emoji in an answer choice" with an identical paste and the plan groups it (real engine input, still no overriding of review output). `test_capture_screens` now expects criterion `9.1` for the group instead of `3.3`. (ii) The script opens the step menu first when the link is hidden (same logic as the test helper `go_to`). |
| 7 | `test_final_locations_ui::test_exact_question_labels_topics_and_share_match_download` | (b) stale expectation, plus a small real bug found on the way | `StopIteration`: three "Select all that apply" pastes differ per question text, so 1C correctly no longer merges them (and a group is not always in `quick_wins`; it can land in `more`). | Same `pattern_snapshot()` fix as above. The test now looks for the grouped card across all three plan tiers. Everything else is unchanged: each row shows the exact label, screen and first-five-words topic, "Use all" goes through, and the Share list, the copied text and the download all carry the same labels. Test labels one question "Research B" on purpose. |
| 7b | (found while fixing 7) | (a) real, small | The grouping key masks only `Q4`-style labels in you-check/steps lines. A question with its own RedJade label ("Research B") put that label in the instruction ("Scroll Research B on your phone...") and the identical check on the other questions no longer grouped (2 + 1 instead of 3). | Test first: `test_grouping::test_a_custom_question_label_in_a_you_check_does_not_split_a_group` (red, then green). `plan.action_signature` also masks the finding's own question label. Paste text is still compared exactly and never masked. |
| 8 | `test_final_races_ui::test_failed_new_job_keeps_previous_review_available` | (b) stale selector, **not** a 1B regression | The previous review is still shown after a failed job (the status line assertion passes). `#overview-headline` was a paragraph that 1B's overview rewrite replaced with the `#overview-h` heading; the id no longer exists anywhere in `site/`. | Assert `#overview-h` is visible and its text equals the saved `overview.headline` (stronger than visibility alone). Phase 0C behaviour is intact. |
| 9 | `test_image_load_uncertainty::test_unloaded_image_is_scoped_to_reader_and_has_conditional_action` | (b) stale copy | Same B7 headline change as #2. | The scope is now asserted in the evidence ("reader observed", "not measured"), headline has no `reader` and starts with "Check that", action is a `you_check` that mentions the phone. Explanation assertions (re-upload, smaller, readable, conditional "if") and the scoring assertions are untouched. |
| 10-12 | `test_phone_preview::test_answer_additions_are_ghosts_not_stem_rewrites_or_verified_fixes[single_choice\|multi_choice\|dropdown]` | (b) stale copy | 1B shortened the preview line for a page with no text replacement. Old: "Hypothetical preview · not accepted or saved. No text replacements; suggested answers still need authoring and behavior checks in RedJade." New: "No wording changes on this screen. RedJade is only changed when you edit it there." | Assert the new line says RedJade is only changed when you edit it there, and that it never claims "verified". All the ghost-answer assertions (dashed, sr-only label, stem untouched, snapshot not mutated, nothing written) are unchanged. See "Follow-ups" for a copy gap. |
| 13-17 | `test_survey_style::test_community_emoji_only_answer_is_flagged` (3 param ids) | (b) stale copy, **not** a regression | Checked first because it could have been a lost tone check. It is not: the emoji-only answer is still flagged exactly once with the same headline and explanation. Only `member_impact` was reworded by 1C (20-word plain-language rule). | `member_impact == "An emoji can look different on each phone."` and the new action (`steps == ["Add a word next to the emoji in this answer."]`). Count, headline and explanation assertions are unchanged. |

(The log prints 17 `FAILED` lines because two emoji ids appear twice in the short summary; the summary line says 15 failed, which matches the 15 in the brief.)

## Other changes

- `site/data.js` regenerated by the parent: committed as is.
- No production behaviour was changed except `surveycoach/server/plan.py` (7b).

## Follow-ups (not done, for the owner)

1. **Preview line with a ghost answer.** When the page only has a suggested new answer (`add_answer`) the line reads "No wording changes on this screen." while a dashed ghost answer is on the phone. It is true (no wording changed) and the ghost is labelled for screen readers, but the old line also said suggested answers still need authoring in RedJade. Consider restoring that sentence when a ghost is present (copy only, 1B/phase 2 owner).
2. **Temp worktree left behind.** My safety guard blocked `git worktree remove`, so the baseline worktree is still at `/tmp/sc-base-*`. It is clean and outside the repo. `git worktree remove /tmp/sc-base-*` then `git worktree prune` deletes it.
3. Grouped cards with only a `you_check` (6.2, 7.x) have no "Use" or "Use all" button. That is by design of the action contract, and phase 2 (fix card contract) covers the buttons.

## Final run

`.venv/bin/python -m pytest -q -m 'not live'`:

**2375 passed, 0 failed, 1 deselected** (294.97 s). That is the earlier 2359 passed, plus the 15 fixed ones, plus 1 new test (`test_a_custom_question_label_in_a_you_check_does_not_split_a_group`).

No remaining failures. Nothing was skipped or weakened to get here.
