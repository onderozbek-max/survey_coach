# Workstream 1B: site header, verdict page, state UI, copy system

Branch `feature/surveycoach-mvp`. Only `site/*` and tests were touched. `surveycoach/` is untouched. `site/data.js` was **not** regenerated.
Screenshots are in `review/after/phase1/` (home, verdict, fix, share at 1440 and 390), uncommitted as asked.

## Done

**1. Header (4.1).** `site/header.js` + `header.css` (+ `menu.js` for the shared menu/disclosure behaviour). One header, built by JS, on `review.html` and the sample `index.html`:
logo (home), My surveys, inline-editable survey name (pencil button; Enter saves through the existing `SC.updateSurvey` PATCH, Escape cancels and returns focus, empty name rejected), the page's only H1 (equals the survey name, placeholder "Untitled survey" for generic titles), one version chip (`v2 · checked 1 hour ago`), steps **Verdict / Fix / Sign off** (hash ids `#overview #improve #share` unchanged), **Check again** always available, and a `…` overflow menu with **How we check** (the About dialog) and, at 390px, My surveys.
- Check again opens `#recheck-dialog` prefilled with the last safe link and reuses `startRead` (no automatic POST retry; uncertain marker lock and `lockRead` still apply; Escape is blocked while a read is running).
- Removed: the unstyled bottom check button, duplicate "Version 1" lines, the stacked Version/RedJade/Improve/Surveys/Rename block, the floating About/Quality footer links (D14 fixed: one H1 per page).
- 390px: collapses to logo + name (2-line clamp) + step menu + Check again (icon) + overflow; all targets at least 44px; no horizontal scroll at 390/1024/1440 on Verdict, Fix, Share.
- **Why brand and My surveys were missing in review2:** I could not reproduce it. The old markup rendered them at 1440 in light, dark and forced-colors. The old `.app-bar` was `position: sticky` in `review-studio.css` while `.app-header` rules in `design-system.css` also matched elsewhere, and the sticky improve bar sat at a hard-coded `top:69px`. My best explanation is that the sticky bars (hard-coded offsets) covered the app bar when scrolled. The new header is the single sticky element and everything under it offsets by its measured height (`--header-h`, set by a ResizeObserver, defaulted to 69px in tokens). Treat this as a fix by construction, not a confirmed root cause.

**2. Four-state UI (4.2).** `states.js` / `states.css`: `SC.stateChip`, `SC.stateIcon`, `SC.verdictState`. Icon + words, never colour alone; null state reads "Not checked automatically", never as good.
Tokens in `design-system.css`: `--you-check #5B3FA3` / `--you-check-soft #F2EEFB`, `--celebrate #8A4B00` / `--celebrate-soft #FFF4D9`, plus `--header-h`. `tests/test_design_tokens.py` gained an automated contrast check (text 4.5:1, icon/border 3:1 on chip fills and surfaces).
Distinct icons in `icons.js`: clock (Time), bubble (Clarity), scale (Honest answers), route (Flow), smile (Tone), phone (Phone comfort); four state shapes (alert-filled, ring, eye, check-circle).

**3. Verdict page (4.3).** `overview.js` (rewritten, 113 lines) + `verdict-cards.js` + `verdict.css`. Hero: state chip, headline, story, time line from `verdict.time.summary`, tiles Fix / Improve / You check, CTA `Start fixing (N)` or `Sign off` when `ready_for_signoff`, secondary `Play it as a member` (existing member-preview dialog). Six category cards with the signal's state chip, summary line and `items` list (3 shown, rest behind "Show N more"). "What members will like" only from `overview.strengths`. Score ring, 86/100, Provisional, coverage removed from Home, Verdict and Share (they live in How we check > Technical details, reading `methodology.quality`). The tiny phone preview is removed (D15). Energy map kept as is.
- Tile routing: **Fix** opens the Fix flow on tab `must_fix`. **Improve** and **You check** open it filtered by the open findings of that state (`route({fingerprints})`, honoured by the existing queue code).
- **Fallback (noted as asked):** curated You-check items that have no finding have no Fix card until phase 2, so that tile scrolls to and focuses the first category card that lists them, and announces it.
- `Start fixing (N)` opens the first tab that still has open items.
- The survey-type fieldset was kept (smaller, at the bottom, helper sentence removed) because the setup flow that replaces it is phase 4.

**4. Home card.** `home-card.js`, `card-status.js`: real name, verdict chip, `3 open · checked 1 hour ago`, Continue; six icons and the quality line removed. Live jobs read Checking… / Queued / In progress; failed with no verdict reads "Check did not finish". Example card on Home uses the new wording only.

**5. Copy system.** Default visible text on Home, Verdict, Fix, Share updated per the table: queue tabs now **Fix before launch / Worth improving / More ideas**; "Go to Sign off"; share summary "N to fix before launch still open"; timing line `~0:15 in · 4 min total`; preview-effect lines; empty-screen heading "Nothing to fix on this screen"; energy caption "(an estimate)". `tests/test_copy_banned_words.py` scans Home, Verdict, Fix, Share (1280 and 390) for all banned words, ignoring dialogs and non-"Show more" `<details>`. **The allowlist for 1C finding copy is empty**: no finding text in the synthetic review tripped the scan.

**6. Accessibility/responsive.** `tests/test_header_verdict_a11y.py` (12 tests): header and verdict accessibility-tree snapshots, one H1 = survey name on every chapter, keyboard rename (open, cancel, save), overflow menu arrow-key/Escape, 390px collapse with 44px targets and step menu, Check again dialog prefill/focus return, tile and CTA keyboard path, state chips are icon + words and the four state icons and six category icons are all distinct, no score or tiny phone on Verdict at 390. Toast/rename status announces once (`Name saved.` appears in exactly one live region).

## Fixed along the way
- `app.js` sample-bar code shadowed the global `state` (sample picker never showed its selected survey, and threw on stale data). Renamed, regression assertion added to `test_site_e2e.py`.
- Hero grid overflowed horizontally at 390px; fixed with `minmax(0, 1fr)`.

## Not done / deferred
- Energy map mini-chart in the Fix toolbar still looks cramped and is clipped at its right edge; not redesigned (phase 3).
- Fix cards still show the "Must-fix" pill and finding bodies (phase 2 / 1C). The third tab stays "More ideas".
- The Fix toolbar still shows a second "0 of 30 done" line under the tabs (existing).
- Home below the cards, setup flow, Sign off content (copy-Slack post), journey strip, My changes tray: later phases.
- Whole suite was not run (as instructed).

## Intentional changes to old tests
Header/menu/dialog flows: `test_chapters_ui`, `test_final_fixes_ui`, `test_share_ui`, `test_issue_loop_ui`, `test_loading_progress`, `test_workflow_e2e`, `test_start_review_e2e`, `test_member_journey`, `test_phone_first_workspace`, `test_site_state_0c`, `test_unified_workspace`, `test_workspace_contracts`, `test_workspace_decisions`, `test_server_contracts` (mechanical: `go_to` / `open_how_we_check` / `open_recheck` helpers in `tests/site_helpers.py`; About is now a menu item; Rename is "Rename survey" / "Survey name" / "Save"; the recheck form is a dialog).
Tab labels and copy: `test_improve_ui`, `test_improve_safety_ui`, `test_queue_position`, `test_share_state_ui`, `test_recommendation_ui_clarity`, `test_site_render_0c`, `test_with_fixes_preview`, `test_answer_addition_ui`, `test_final_locations_ui`.
D-Score / verdict / Home: `test_home_page`, `test_overview_ui` (rewritten around tiles, cards, no mini phone), `test_quality_ui` (score now only in the methodology dialog), `test_site_e2e` (sample bar shows the verdict; fresh in-memory data served for `data.js`), `test_copy_deck` (dropped "fix before launch", "check again", "almost ready" from the retired-phrase list, because the new design makes them canonical).
`test_issue_loop_ui.open_review` now also remaps overview item/card fingerprints to the synthetic `fingerprint-N` ids so tile and card routing can be tested.

## Test results (focused only)
- Requested list plus new tests: `tests/test_home_page.py tests/test_chapters_ui.py tests/test_workflow_e2e.py tests/test_issue_loop_ui.py tests/test_design_tokens.py tests/test_loading_progress.py tests/test_start_review_e2e.py tests/test_copy_banned_words.py tests/test_header_verdict_a11y.py`: **85 passed**.
- Plus `test_overview_ui` (20): 105 passed together.
- Other affected UI files, all green: `test_quality_ui` 8, `test_site_render_0c` 24, `test_final_fixes_ui` 19, `test_site_e2e` + `test_with_fixes_preview` 23, `test_share_ui` + `test_improve_ui` 27, `test_member_journey` / `phone_first` / `server_contracts` / `site_state_0c` / `unified_workspace` / `workspace_contracts` / `workspace_decisions` / `site_e2e` 60, `test_copy_guard` 17.
- **Expected failures until the parent regenerates `site/data.js` after 1C:** `tests/test_demo_export.py` (stale export, 4 tests), `tests/test_copy_deck.py::test_every_committed_demo_entry_has_current_canonical_projection` (1).
- **Not caused by the site, needs 1A/1C attention:** `tests/test_final_locations_ui.py::test_exact_question_labels_topics_and_share_match_download` fails with `StopIteration` in Python before any UI runs (`next(i for i in plan['quick_wins'] if i['count'] == 3)`), so the plan grouping that test assumes no longer exists in the enriched payload. I did not change it.

## Commits
Named-file commits only on `feature/surveycoach-mvp`; no push. `site/data.js` and `surveycoach/` untouched by this workstream.
