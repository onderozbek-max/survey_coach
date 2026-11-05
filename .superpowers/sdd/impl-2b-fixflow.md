# Workstream 2B: fix flow (list, card, My changes tray)

Branch `feature/surveycoach-mvp`. No push. Nothing under `surveycoach/`, `site/data.js`, `site/phone.js` or the phone-frame
files was touched. Everything is offline.

## Done

| # | Item | Where | Evidence |
|---|------|-------|----------|
| 1 | One ordered fix list from `detail.queue` (Fix before launch, Worth improving, You check). Each row has a state icon plus words, a screen chip and a short title. Three state filter chips (the Verdict `state` param is honoured). ONE `N of M done` progress with a conic-gradient ring, still under `prefers-reduced-motion`. Three columns from 1024px (list, phone, card). Below 1024px: phone, then card, with the list in a "Fix list" drawer. The old tabs and the toolbar mini-chart are gone; the energy map is untouched. | `site/queue.js`, `fix-list.js`, `issue-list.js`, `fix-flow.css`, `app.js` hooks, `review.html`, `index.html` | `test_fix_flow_ui.py` (layout test at 1440/1024/390, filters, counts), screenshots |
| 2 | Fix card, identical for every finding. State chip and member-language title; one-line why from `member_impact`; exactly one fix (paste with Show changes, Copy and the `field_location` hint; or 1-3 numbered steps; or a you-check with "I checked"); actions Add to my changes / Mark done in RedJade / Keep as is… (reason chips Intentional, Owner decided, Not applicable, Other, plus a note of up to 200 characters); methodology and evidence in collapsed Details. Grouped cards show "Applies to Q4, Q6 and Q8 (screens 5, 7 and 9)" and one action saves the group. Phase 0C safety is kept: the save is bound to the originating item, no wrong advance, optimistic UI with a clear error and a Retry button, no duplicate submit. | `site/coach.js`, `fix-parts.js`, `suggestion.js`, `improve-actions.js`, `diff.js` (unchanged) | `test_fix_flow_ui.py`: slow save submitted once and does not move a user who has moved on; failed save says so, stays open, retries only on request; `test_final_races_ui.py` (grouped batch stops when the survey is replaced) |
| 3 | My changes tray: bottom sheet "My changes (N)" from `detail.my_changes` in RedJade order, per-item Copy, Copy all uses `copy_all_text` exactly, clipboard module with a textarea fallback, toast "Copied", polite live region. Empty state "Nothing added yet". Duplicate `SC.changeSheetText` and `SC.issueTarget` deleted and callers updated. | `site/my-changes.js`, `clipboard.js`, `rounds.js`, `toast.js` | `test_fix_flow_ui.py`, `test_issue_loop_ui.py::test_adding_a_change_...` (clipboard equals `copy_all_text`) |
| 4 | Original / "With my changes (N)" toggle: disabled at 0 with a visible reason ("Add a change to see it on the phone."), plus `aria-describedby` and a title. The preview shows only added changes (kept and open items are never previewed). The line under it is 2C's `.preview-effect`. | `queue.js` (`renderBar`) | `test_fix_flow_ui.py::test_with_my_changes_is_disabled_until_there_is_one`, `test_phone_preview.py`, `test_site_e2e.py` |
| 5 | D13: a screen with no items shows a compact row "Nothing to fix on this screen" with a check icon and "Next item: <title> →" (`next_open_id`); the user's place stays highlighted in the list. When nothing is open: "All N handled. Check your updated survey to confirm." with Check again (opens the header dialog) and Go to Sign off; no gradients, tokens only, no motion when reduced. | `site/completion.js`, `queue.js` | `test_fix_flow_ui.py` (nothing-here row incl. no overlap, completion, reduced motion) |
| 6 | D17 All screens drawer: icon Close button named "Close all screens", search label "Search screens", state icon plus text on every row (flags come from the queue), native modal `<dialog>` (focus trap, Escape closes, focus returns to the opener). | `site/issue-list.js` | `test_fix_flow_ui.py::test_all_screens_drawer_...` |
| 7 | Banned words plus accessibility. The banned-word scan now covers every card in its default state (Details collapsed), the open tray, both drawers and the end states, at 1440 and 390. The scan is scoped to the Fix flow's own text (toolbar, list, card, tray, toast) because the phone shows the member's survey content. Keyboard path list → card → tray. 44px targets, visible keyboard focus (at least 2px), state never by colour alone, no horizontal scroll at 1440, 1024 and 390. | `tests/test_copy_banned_words.py`, `test_fix_flow_ui.py` | see results |

Phone fidelity at 390: filter chips live with the list (page column at 1024px and up, inside the drawer below), so the toolbar
is three compact rows and the phone starts in the top half. `test_site_e2e` "phone is the hero" still holds.

## Commits (mine)
`80c174c`, `3cec2a1`, `7a3447c` (earlier session) and, in this session: races/locations tests, phone preview and
issue-loop tests, workflow e2e, filter chips with the list, visible disabled-toggle reason, site e2e,
celebration spacing, `test_site_state_0c` partial update. Named files only.

## Tests: exact results
Command (one run): `pytest tests/test_issue_loop_ui.py tests/test_final_races_ui.py tests/test_final_locations_ui.py
tests/test_workflow_e2e.py tests/test_site_e2e.py tests/test_phone_preview.py tests/test_copy_banned_words.py
tests/test_design_tokens.py tests/test_queue.py tests/test_my_changes.py tests/test_fix_flow_ui.py`
→ **111 passed, 1 warning in 44.44s.** `tests/test_fix_flow_ui.py` is new (17 tests). The banned-word file gained
2 parametrized cases (1440, 390).

### Older tests changed on purpose (behaviour changed; no safety assertion weakened)
- `test_issue_loop_ui.py`: Use/Keep/Skip → Add to my changes / Keep as is… with reason chips. "Add" no longer copies;
  copying is its own explicit button and the tray. The stand-in server re-derives queue and My changes after every
  decision, as the real server does. Stale-save, failed-save, duplicate-submit and no-wrong-advance assertions kept.
- `test_final_races_ui.py`: the clipboard-race variant is dropped (Add no longer copies). The batch-race variant now
  checks that a replaced survey stops the remaining group writes (still exactly 1 PUT). Toast-focus test uses Mark done.
- `test_final_locations_ui.py`: per-member exact location is checked in the group card's Details.
- `test_phone_preview.py`: preview requires an added change; after saving, the card advances, so the test returns to the screen.
- `test_workflow_e2e.py`: keep reason chip + note survives a reload (the list is in a drawer at 390).
- `test_site_e2e.py`: preview only shows added changes; new card selectors; second sample has 3 you-check items and no fix items.

## Not done / known gaps (be honest)
- **Legacy suites outside the requested list were not run and will contain stale selectors**: `test_improve_ui.py`,
  `test_improve_navigation_ui.py`, `test_improve_safety_ui.py`, `test_queue_position.py`, `test_site_render_0c.py`,
  `test_with_fixes_preview.py`, `test_workspace_decisions.py`, `test_server_contracts.py`. They reference `#use-all`,
  `queue-more`, `.pattern-row`, `With changes`, `.keep-as-is` and similar. They need a rewrite or retirement
  (test_fix_flow_ui.py now covers the same safety ground).
- `tests/test_site_state_0c.py` (also outside the list): I updated the removed `SC.changeSheetText` caller and the
  `With changes` label in two tests; **11 passed, 5 failed**: `test_copy_and_change_sheet_text_name_only_the_chosen_target`,
  `test_preview_effect_does_not_count_raw_only_text`, `test_delayed_save_does_not_advance_unrelated_navigation`,
  `test_save_without_navigation_still_advances`, `test_alternative_choice_updates_phone_comparison_and_survives_unrelated_render`.
  The raw-only one likely collides with 2C's new stimulus rendering (page text now shows on the phone).
  The others still use `queue-more`, `#use-change` and old tab flows. Not fixed (quota).
- `site/data.js` is the stale committed file (policed by `test_demo_export`); the browser tests use fresh in-memory data.
  The static sample therefore only shows the new queue once data is regenerated at integration.
- The "no gradients" rule: the progress ring uses `conic-gradient` (explicitly allowed); the celebration uses none.
- Phone marker labels still say "Must-fix:" (phone.js, owned by 2C).
- Old vocabulary constants remain in `site/dom.js` (`SC.SEVERITY`) and `site/issues.js` (`SC.ISSUE_TIERS`);
  they are not rendered in the Fix flow.

## Screenshots (uncommitted) `review/after/phase2/`
At 1440 and 390: `fix-list-and-card`, `paste-card`, `steps-card` (from the boxer-briefs sample, because the concept survey has
no steps item), `you-check-card`, `tray-open`, `completion`, `all-screens-drawer`; at 390 also `fix-list-drawer`.
Runner: `tests/_phase2_flow_shots.py` (uncommitted; not collected by pytest by default).
