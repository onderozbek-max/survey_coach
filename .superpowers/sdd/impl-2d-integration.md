# Integration fix 2D: Phase 2 whole-suite integration

Branch `feature/surveycoach-mvp`. No push, no live calls, no delegation. Named files only were staged; no `git stash/checkout/reset/add -A/commit -a` in the shared tree. Temporary worktrees (`/tmp/sc-2d-prev` at `9427bad`, `/private/tmp/sc-base-N033` at `6554188`) were left in place.

## Result

| Run | Command | Result |
|---|---|---|
| Phase 1 end (1D) | `pytest -q -m 'not live'` | 2375 passed, 0 failed |
| 2D run 1 (before any fix, the TRUE failure list) | `.venv/bin/python -m pytest -q -m 'not live'` | **115 failed, 2360 passed, 1 deselected, 1 warning** (2001.61 s) |
| 2D final run (HEAD `e92a9db`) | `.venv/bin/python -m pytest -q -m 'not live' -p no:cacheprovider` | **0 failed, 2462 passed, 1 deselected, 1 warning** (550.96 s) |

The 115 to 0 change nets 2475 to 2462 tests: 13 tests were retired because their whole premise no longer exists (listed below with replacement coverage), 0 were silently deleted. The one warning is the pre-existing Starlette `httpx` deprecation. The 1 deselected is the `live` test.

The run time fell from 2001 s to 551 s because the stale tests were burning 4 s Playwright timeouts each.

Nothing is classified flaky or environmental: every one of the 115 failures was deterministic on HEAD and is now green, so the `6554188` baseline comparison was not needed for any classification. (Reference only: `6554188` predates the fix flow, so the new-flow tests do not exist there.)

## site/data.js

`python -m surveycoach.demo_export` run twice: identical sha256 `8fea7893ece7d2bc0ab8d3ff161749c93c8cabe80878def902670a4d58a69c92`, re-confirmed at the end (still byte-identical, `git status site` clean). It contains no URLs (`grep -c http` is 0). Brand names in it are the pre-existing synthetic sample-survey copy, not foreign copy. Committed in `326633f`.

## Real regressions found (production code fixed, test first)

| # | Found by | Defect | Fix | Commit |
|---|---|---|---|---|
| R1 | `test_site_state_0c::test_alternative_choice_updates_phone_comparison_and_survives_unrelated_render` | In the new fix card, choosing an alternative wording redraws the paste block, which replaces the pressed button. Keyboard focus fell to the page body, so a keyboard user lost their place after every selection. The old card kept focus. | `site/fix-parts.js`: after the redraw, focus returns to the pressed alternative. | `1c3f466` |
| R2 | `test_final_fixes_ui::test_keyboard_undo_returns_to_restored_single_card` and the `test_undo_resolves_refetched_fingerprint_not_array_index` variants | Toast Undo moved focus to the card heading, then the async restore re-rendered the card and focus was lost to the body again. | `site/improve-actions.js`: after the undo render, focus lands on the card heading. | `e357566` |

`test_preview_effect_does_not_count_raw_only_text` (flagged by 2B as possibly hitting 2C's stimulus rendering): **not a regression**. Its assertions (a page-level raw-only string is not rendered on the phone and is not counted in the preview-effect line) pass unchanged on HEAD with 2C's renderer. It failed because of the test setup: the harness re-enriched the payload and dropped the injected page text, and the test clicked the old `With changes` label with no added change. Fixed in the harness and the preview flow; see below.

## Harness changes (tests/test_issue_loop_ui.py)

- `derive()` keeps the test's injected `screens` and `snapshot` (enrich re-derives `stimulus_text` from page text/media and was clobbering injected page fields).
- `derived=False` serves an injected payload exactly (overview rendering tests).
- New shared helpers: `keep_item(page)` (open Keep panel, pick a reason, Save, wait for Undo) and `single_paste(detail)` (first single-member pasteable queue entry). `site_state_0c` and `final_fixes` now use them instead of their own copies.
- One rule learned and written into the tests: a finding's explicit `action_kind` wins over inferred paste/steps, so tests that turn a finding into a paste must also set `action_kind='paste'` (and clear `steps`).

## Per-failure table (all 115 from run 1)

Classification: **(a)** real regression, **(b)** stale expectation updated to the new equivalent behaviour keeping the safety intent, **(b-retired)** whole premise gone, retired with named replacement. No (c).

| File | Failing in run 1 | Class | Cause and resolution |
|---|---|---|---|
| `test_phone_fidelity.py` | 16 (stimulus pin/highlight, rewrite lands only in stimulus, member-type stimulus, ghost-only answer ×2, no-horizontal-scroll ×6, pinned Next, scroll region keyboard ×3, preview line honesty) | b | Preview now needs an added change (2B) and the harness dropped injected stimulus fields. Tests add a change first through a helper, use valid option ids, and keep the injected page fields. Same layout/overflow/keyboard assertions. Commit `2f7242a`. |
| `test_overview_ui.py` | 9 | b | Tiles route by queue state, grouped findings live in the card Details, decision status is a handled line; tests serve the injected payload with `derived=False`. Commit `f052e24`. |
| `test_chapters_ui.py` | 4 (About ×3 + scope refresh) | b | Injected payload was being re-enriched; now `derived=False`. Same disclosure assertions. Commit `df57b9a`. |
| `test_member_journey.py` | 2 | b | Injected payload retained; compare needs an added change. Commit `df57b9a`. |
| `test_quality_ui.py` | 1 | b | Injected payload retained. Commit `df57b9a`. |
| `test_share_state_ui.py` | 1 | b | Injected plan retained. Commit `135ba99`. |
| `test_capture_screens.py` | 1 | b | `scripts/capture_screens.py` follows the first open queue item and grouped-card Details. Commit `4ebf794`. |
| `test_workspace_decisions.py` | 2 (action-only keep, delayed use vs newer keep after navigation) | b | Fix-card handled line, Undo then Keep, tray stays empty. Race intent kept. Commit `f409ca7`. |
| `test_server_contracts.py` | 1 (pending save locks decisions until committed, survives reload) | b | Same pending-lock contract against the fix card. `f409ca7`. |
| `test_unified_workspace.py` | 1 | b | `f409ca7`. |
| `test_workspace_contracts.py` | 1 (legacy phone link and keyboard issue navigation) | b | `f409ca7`. |
| `test_site_state_0c.py` | 5 | 4 b, 1 a | Copy sheet names only the chosen target (needs `action_kind='paste'`); delayed save does not advance unrelated navigation, now: hold the PUT, click another list row, release, user is not moved and focus is not stolen; save without navigation still advances (toast `Added to My changes`); preview effect raw-only test (harness fix, see above, **not** a regression); alternative choice test found **R1**. Commit `1c3f466`. |
| `test_structured_suggestions_ui.py` | 16 | b | Card selectors `.suggested` to `.fix-paste`; diff now behind Show changes; Copy is its own button and Add saves a pick (never copies), so exact-copy assertions press Copy and exact-save assertions check the PUT. Added `open_rec` so the prepared finding is the open card. Bundle/ambiguity/escaping assertions unchanged. `99a1982`. |
| `test_structured_generation.py` | 3 | b | Same port; grounding output carries no action kind so the helper sets paste. `99a1982`. |
| `test_demo_structured_suggestions.py` | 1 | b | Same port, exact copy of the real Q1 bundle kept. `99a1982`. |
| `test_answer_addition_ui.py` | 1 | b | Add-answer card label `Add this answer`, only the new label offered and copied, Details says do not replace the question, Share text has no `Replace with:`. `99a1982`. |
| `test_recommendation_ui_clarity.py` | 13 | 6 b, 7 b-retired | Ported: steps-only item visible, screen with nothing to fix is a compact row never "handled", refetched empty queue never "All 0 handled", selecting a screen opens its first open item, empty filter never a dead end, compact energy guide now inside Play it as a member (3 widths). Retired (tab/plan scoped; see list below). `8143af1`. |
| `test_site_render_0c.py` | 7 | 3 b, 4 b-retired | `test_one_progress_model_everywhere`, `progress_ignores_which_item_is_open`, empty state chip ported; four Use all tests retired. `2da3966`. |
| `test_final_fixes_ui.py` | 6 | 5 b, 1 a (R2) | Keep now needs the panel Save and the reason label `Owner decided`; toast text `Back on your list`; refetch drops findings and queue entries together; keyboard undo found **R2**. `e357566`. |
| `test_improve_safety_ui.py` | 3 | 2 b, 1 b-retired | Undo cannot overwrite a newer keep (now Add, card Undo, Keep, then the stale toast Undo: no write, revision 3); failed restore never claims restored; absorbed pin not rendered. Tab membership test retired. `e0bf57a`, `13bbdeb`. |
| `test_queue_position.py` | 2 | b | Progress counts saved decisions only, undo restores. `13bbdeb`. |
| `test_improve_navigation_ui.py` | 1 | b | Mode toggle plus pager keyboard focus retained; the toolbar energy chart no longer exists. `13bbdeb`. |
| `test_with_fixes_preview.py` | 1 | b | Preview disabled with a reason and no write; the single write is the Add; Original restores; a keep is not previewed and its reason survives reload. `44fa8af`. |
| `test_improve_ui.py` | 17 | b / b-retired | See below. `d0d7174`. |

### Retired tests (whole premise gone) and replacement coverage

| Retired | Why | Replacement |
|---|---|---|
| `test_screen_matches_related_findings_across_categories[also_affects/absorbed_by/question_id]` (3) | Screen-to-tab matching across plan tabs; the server now builds one queue from `overview.items` | `test_queue.py` (entries list every screen, counts equal tiles); `test_recommendation_ui_clarity::test_selecting_a_screen_opens_that_screens_first_open_item`; `test_improve_safety_ui::test_absorbed_finding_pin_is_not_rendered...` |
| `test_scoped_empty_filter_is_not_screen_clear_or_all_decided`, `test_scoped_all_decided_is_distinct_from_no_findings`, `test_other_category_open_finding_prevents_screen_completion`, `test_unqueued_screen_finding_is_not_falsely_handled` (4) | Per-tab scoped empty/complete states ("Nothing more in this view", "outside this category") | `test_recommendation_ui_clarity::test_a_filter_that_matches_nothing_is_never_a_dead_end`; `test_improve_ui::test_overview_with_everything_handled_routes_to_the_completion_moment`; `test_fix_flow_ui::test_handling_everything_ends_in_the_completion_moment`; `test_queue.py::test_n_of_m_done_equals_the_tiles...`, `test_next_open_id_is_none_when_nothing_after_is_open` |
| `test_use_all_*` ×4 (counts, hides under two, says what is left, disabled with reason) | The Use all button was replaced by one action on a grouped card | `test_fix_flow_ui::test_add_to_my_changes_applies_to_the_whole_group_and_fills_the_tray`; `test_queue.py::test_action_kind_and_pasteability_are_per_entry`; `test_fix_flow_ui::test_with_my_changes_is_disabled_until_there_is_one` |
| `test_empty_tab_says_none_not_zero_of_zero` | Tabs gone | `test_site_render_0c::test_a_state_with_nothing_open_shows_a_zero_chip_not_a_missing_one` |
| `test_refetched_detail_replaces_queue_membership` | Tab membership | `test_recommendation_ui_clarity::test_a_refetched_empty_queue_...`, `test_final_fixes_ui::test_undo_resolves_refetched_fingerprint_not_array_index` |
| `test_signal_route_selects_server_tab_without_rebuilding_pattern` | Tabs gone | `test_fix_flow_ui::test_filter_chips_and_the_verdict_state_param`; `test_improve_ui::test_a_route_with_fingerprints_opens_that_item...` |
| `test_pattern_keyboard_row_focus_survives_pending_success_failure_and_undo` | Per-row panel focus; a group is one card now | Focus to the card heading after save/undo: `test_final_fixes_ui` (keyboard undo, R2), `test_improve_ui::test_queue_saves_adds_advances...`, `test_fix_flow_ui::test_keyboard_path_list_to_card_to_tray` |
| `test_stale_alternatives_absorbed_and_completed_section` (completion section and `.also-affects` parts only) | "All 3 must-fixes handled" / "Continue to quick wins" and the also-affects line | Stale pick and alternatives kept as `test_improve_ui::test_stale_pick_is_announced...`; completion as above |
| `test_energy_...legend` in the improve toolbar | The toolbar mini chart is gone | Same assertions now run inside Play it as a member (320/390/1280) in `test_recommendation_ui_clarity` |

Net: 1323 test functions before the 2D edits, 1314 after (collected cases 2475 to 2462 including parametrisation). New tests: `tests/test_fix_group_safety.py` (4 cases) plus the ported and added cases named above.

## Safety behaviours: coverage in the new fix flow

| Behaviour | Test(s) |
|---|---|
| Delayed save bound to its origin item, no wrong advance | `test_fix_flow_ui::test_a_slow_save_is_submitted_once_and_moves_on_only_from_its_own_item`; `test_site_state_0c::test_delayed_save_does_not_advance_unrelated_navigation`; `test_workspace_decisions::test_delayed_use_cannot_overwrite_newer_keep_after_navigation` |
| Save without navigation still advances | `test_site_state_0c::test_save_without_navigation_still_advances` |
| Retry on failure only on request, no auto retry | `test_fix_flow_ui::test_a_failed_save_says_so_keeps_the_item_open_and_retries_only_on_request` |
| No duplicate submit while pending (controls locked) | `test_improve_ui::test_pending_lock_survives_replacement_controls`; `test_server_contracts::test_pending_save_locks_decisions...`; `test_fix_flow_ui` slow-save test |
| Keep reason persists through reload | `test_with_fixes_preview::test_kept_item_is_not_previewed_and_its_reason_survives_a_reload` (real server); `test_improve_ui::test_keep_requires_a_reason...` (saved reason and note) |
| Keep needs a reason, nothing saved before Save | `test_improve_ui::test_keep_requires_a_reason_and_saves_only_on_save...`; `test_fix_flow_ui::test_mark_done_and_keep_with_a_reason_chip` |
| Undo cannot overwrite a newer decision | `test_improve_safety_ui::test_undo_cannot_overwrite_newer_keep`; `test_fix_group_safety` (batch + undo) |
| Failed restore never claims restored | `test_improve_safety_ui::test_undo_failed_restore_never_claims_restored` |
| Undo resolves by fingerprint not array index | `test_final_fixes_ui::test_undo_resolves_refetched_fingerprint_not_array_index` (3) |
| Field-scoped replacement (stimulus only in stimulus, hits equal visible replacements) | `test_phone_fidelity::test_a_rewrite_of_stimulus_wording_lands_only_in_the_stimulus`; `test_site_state_0c::test_hit_count_equals_visible_replacements_for_every_control_kind`, `test_copy_and_change_sheet_text_name_only_the_chosen_target` |
| Read-only recovery and uncertain marker lock (an unconfirmed request opens the review read-only, blocks every submission; reading and previews stay usable) | `test_site_state_0c::test_uncertain_marker_opens_existing_review_read_only_and_blocks_submissions` (passes unchanged against the fix card; the `SC.readOnly` branches in `site/app.js` disable the card's decision controls and `saveDecision` refuses to write) |
| Uncertain walkthrough qualifies timing and suppresses the elapsed route | `test_overview_ui::test_uncertain_path_qualifies_energy_and_suppresses_elapsed_route`; `test_member_journey::test_uncertain_captured_walkthrough_qualifies_total_timing` |
| Grouped card: one PUT per member, partial save never claims success, newer choice stops batch before later writes, undo restores each prior object and only what its own save wrote | `tests/test_fix_group_safety.py` (new, 4 tests, real server) |
| Preview shows only added changes, a keep is not a change | `test_phone_fidelity` preview line, `test_final_fixes_ui::test_kept_item_is_not_a_change...`, `test_with_fixes_preview` |
| Alternative choice keeps focus and its text through unrelated renders | `test_site_state_0c::test_alternative_choice_updates_phone_comparison...` (R1) |

No safety assertion was weakened. Where an assertion changed shape it moved to the new control (for example "Use writes and copies" became "Add writes, Copy copies, neither does the other's job").

## Commits (named files only)

`326633f` data.js; `2f7242a` phone fidelity and harness; `f052e24` overview; `df57b9a` about/journey/quality; `135ba99` share state; `4ebf794` capture script; `f409ca7` decisions/server/unified/workspace contracts; `1c3f466` 0C state + **R1**; `99a1982` structured suggestions/generation/demo/answer addition; `8143af1` recommendation clarity; `2da3966` 0C render; `e357566` final fixes + **R2**; `e0bf57a` improve safety; `44fa8af` preview e2e; `13bbdeb` navigation/queue position; `d0d7174` improve ui; `e92a9db` group safety. This report is added after `e92a9db`.

Untracked `review/after/*`, `review/*.png`, `tests/_phase2_*.py` and `uglyhome.png` pre-existed and were not touched or staged.

## Notes for the next phase

- The probe, debug and timeout-helper files used during diagnosis live only in `/tmp` and are not in the tree.
- Several tests still read `detail['plan']` as input to the harness (`prepare` functions that pick findings by plan membership). That is harmless because the stand-in re-derives the queue, but the plan itself is now legacy for UI purposes.
