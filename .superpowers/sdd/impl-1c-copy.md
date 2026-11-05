# Workstream 1C: actionable finding copy, branch-path You check, copy debt

Branch `feature/surveycoach-mvp`. Offline, synthetic fixtures only. Nothing under `site/` was touched, and `site/data.js` was not regenerated.

## Done

1. **Explicit action on every check finding.** `finding()` in `checks/registry.py` now requires exactly one action: paste (with `suggested_text` and `field_location`), 1–3 steps, or one `you_check` question. A check can no longer fall back to the legacy action silently. The fallback stays only for old saved findings and AI-written wording. Every criterion on the 1A legacy list is converted: structure, content, reading, answers, experience, phone, images.
2. **Member impact and card body limits.** Member impact is at most 20 words and plain language. A test (`test_check_actions.py`) checks grade ≤ 8.5 and the banned words over the battery. The visible card body is capped at 45 words (`MAX_BODY_WORDS`, `visible_body_words`). Longer impacts are cut at a clause boundary and the full text stays in details. Banned words can't be reintroduced by the fallback path.
3. **Copy debt cleared.** `KNOWN_COPY_DEBT` is now `{}` and the test passes with it empty.
   - B7's headline is "Check that this image shows up on a phone".
   - B1, B2 and 8.5 member impacts fit the limit.
   - Added: every paste in the fixtures has a `field_location`, and every card body fits 45 words.
   - The old test "checks still on the legacy fallback" became "only AI findings use the fallback".
4. **Repeated blocks grouped.**
   - `plan.py` groups on criterion + normalised headline + action signature. The signature masks the `Q4`/`Q6` label in steps and you-check lines. It compares paste text exactly, so two different rewrites never merge.
   - `labels.group_label` gives the location, for example `Q4, Q6 and Q8 · Screens 5, 7 and 9`. A grouped you-check also gets an `instruction` naming every question.
   - Each member keeps its own fingerprint and screen marker, so decisions stay per member and the group is done when all members are decided. Tested end to end with a reload.
   - A review saved by the old code (old copy, no action fields) with decisions on it is also tested. The decisions still apply to the regrouped card, and the stored review row is byte-identical afterwards.
   - `guard_recommendation` no longer overwrites the 7.2 copy on a finding that has its own action. Legacy saves are still rewritten.
5. **Long answer list is a You check.** "N answer choices" is now `Scroll Q4 on your phone: are all N answers easy to reach?`. The safety statements (don't delete distinct answers, keep order, randomization, exclusivity and routing) stay in details. Image-count 7.5, 7.2 and B7 broken-image use the same pattern.
6. **Reading rewrite is safe.**
   - Q1 now rewrites to `How often do you buy ready-to-heat or ready-to-cook meals, like prepared meals or meal kits, to enjoy at home?`
   - Behaviour, timeframe, category, examples and qualifiers are kept. If any are lost, there is no rewrite.
   - A hard question gets steps naming 2–4 hard words found deterministically, plus a plain word only from a small vetted synonym map. Grade numbers stay in details.
   - Tests in `test_reading_rewrite.py` cover key-term retention (`at home`, the verb, the category terms) with negative controls.
7. **Branch-path You check.**
   - New item `branch_paths` ("Check the other paths", signal `energy`), built in `you_check.py`.
   - It appears when the walk is not fully covered and there is a walked route, visible branching or a screen-out page.
   - It names the conditional questions and screens, or the screen-out screen. With nothing to name it still gives one instruction.
   - It counts toward the budget of 6. Detection order is priority order, so when 7 apply the timed run is dropped, not the branch check. Display order stays in theme order.
   - It blocks "Ready for sign-off" until ticked or kept. End-to-end test: a control survey with nothing partial reaches ready; the partial one stays "almost ready" until the branch item is kept.
   - Negative controls: a fully walked survey (even with conditional questions) gets no item, and a linear survey with no walk record gets none.
   - `coverage` is threaded through `build_you_checks`, `extra_items`, `signals.build_overview`, `server/extras.py` and `server/present.py`.

## Judgment calls and notes for the parent

- **Imports with no walk record and no branching get no branch item.** The scope text already says the capture isn't verified, and a "check the other paths" claim would be false with no route walked. If you want it on `unchecked_paths` alone, it is a one-line change in `_branch_paths`. The catch: every sample and import then sits at "almost ready".
- **1B and the `instruction` field.** The new field is only on grouped you-check findings (count > 1). `instruction` previously existed only on non-finding items. The cards need to show `location` (now a joined label) and `instruction` when it is present.
- **Test edits to old tests and why:**
  - `test_checks_images` 7.2, `test_review` CLI and `test_reading_choice_fixes` changed because the intended copy changed.
  - `test_status_server` legacy-save test now strips the action fields explicitly. Fresh reviews carry them, so it can't assume they're absent.
  - `test_plan` still passes. The grouping signature lower-cases and collapses whitespace.
- **AI judge prompt untouched.** AI findings still use the shared fallback (a prompt change would invalidate every cached answer). `judge/prompts.py` was not needed.
- I ran `git stash` and `git stash pop` once to compare against a clean tree. It restored cleanly (all 1B `site/` edits intact), but I won't do it again while 1B is working.

## Not done

- No live checks or re-record of AI answers.
- `site/data.js` is stale until the parent regenerates it.

## Test results (focused list, not the whole suite)

`tests/test_checks_*, test_recommendation_quality, test_status_consistency, test_signals, test_present*, test_review*, test_root_cause_invariants, test_enrich_contract, test_judge_schemas, test_ai_review, test_you_check, test_plan, test_action_contract, test_reading_choice_fixes, test_status_server, test_required_unknown_checks, test_committee_evidence_checks, test_absent_categories_and_b3, test_check_actions, test_reading_rewrite, test_grouping, test_branch_paths, test_verdict, test_demo_export, test_copy_deck`

**1173 passed, 5 failed.** All 5 failures are expected until the parent regenerates `site/data.js`:

- `test_demo_export::test_committed_site_data_is_not_stale`
- `test_copy_deck::test_every_committed_demo_entry_has_current_canonical_projection`
- `test_copy_deck::test_authored_copy_has_no_retired_deck_phrases[fix before launch | check again | almost ready]` — these flag retired phrases in worker 1B's in-progress `site/*` files (`local.html`, `queue.js`, `states.js`, `share.js`, `review.html`, `header.js`, `workflow.js`), not in anything I own.

Commits: `8eeea43` (items 1–5) and `b83e3b1` (item 6), then the report.
