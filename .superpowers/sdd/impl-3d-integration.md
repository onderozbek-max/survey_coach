# Integration fix 3D: Phase 3 whole-suite integration

Branch `feature/surveycoach-mvp`. No push, no live calls, no delegation. Named files only were staged; no `git stash/checkout/reset/add -A/commit -a` in the shared tree. One temporary worktree, `/tmp/sc-3d-2d` at `e92a9db` (the 2D end state), was used for comparison and left in place.

## Result

| Run | Command | Result |
|---|---|---|
| 2D end | `pytest -q -m 'not live'` | 2462 passed, 0 failed |
| 3D run 1 (the TRUE failure list: HEAD + regenerated `data.js`, before any other fix) | `.venv/bin/python -m pytest -q -m 'not live' -p no:cacheprovider` | **10 failed, 2624 passed**, 1 deselected, 1 warning (427.69 s) |
| 3D final whole suite (HEAD `16b4c25`) | same command | **0 failed, 2659 passed**, 1 deselected, 1 warning (415.87 s) |
| 3D browser files only, second pass | `pytest -q -m 'not live' tests/test_*_ui.py tests/test_*e2e*.py` (23 files) | **0 failed, 232 passed** (105.92 s) |

The 1 deselected is the `live` test; the warning is the pre-existing Starlette `httpx` deprecation.

**Flakiness:** the browser files ran in the final whole run and again alone: no test failed once and passed once. The only flake seen anywhere (`test_about_is_consistent_keyboard_modal_in_every_chapter[sample-390]`, run 1) was a real app race, now fixed (F3 below). No test is classified environmental.

## site/data.js

`python -m surveycoach.demo_export` run twice: identical sha256 `9998af8a7027f86b6c419a0e65c4c3fa08335f9b7249fe37649f68347ae044d4` (re-run after the final edit; `git status site` clean). `grep -c http` is 0, so no URLs. Brand names in it are the pre-existing synthetic sample copy. Committed with the generator change.

It now carries, per sample: `presentation.journey` and `journey_sections` (already there once `enrich` had them), `survey_type_detection` (unconfirmed guess), `reward` (unanswered), `version_delta` (`null`: both samples are first versions, so "where applicable" means none), `signoff` (unsigned, empty history) and `share` (the Slack post; `link` and `summary_url` are `null`, because there is no server and no URL may appear). These come from the server's own functions (`detect_survey_type`, `read_reward`, `signoff_state`, `share_payload`) in a small `_server_fields` helper in `surveycoach/demo_export.py`, not from copies of their output.

Two things worth knowing:
1. **I first added `version: 1` to the sample and removed it again.** It put a "v1 · checked a while ago" chip on made-up data and pushed the phone 14 px down at 390 (failure F8). The sample has no `version` field now.
2. **The static `site/index.html` is only a shell** (its Verdict and Sign off sections are bare headings; setup card and Sign off are drawn by `workflow.js`/`overview.js` code that needs the server, `SC.updateSurvey` and `SC.api`; 3B and 3C chose that on purpose and tests cover it). So the static page shows the journey strip (`.journey` count 1) but **not** the setup card or Sign off. The data now carries the fields; the stand-in tests and the real server use them. Making the bare shell draw them would be new UI (read-only cards whose buttons cannot save), not an integration fix, so I did not do it. Say if you want it.

## Per-failure table (run 1: 10 failures)

Classes: **(a)** real regression, production fixed test-first; **(b)** stale expectation, updated with the same safety intent; **(c)** flaky or environmental. Nothing was retired and no safety assertion was weakened.

| # | Test | Class | Diagnosis and resolution | Commit |
|---|---|---|---|---|
| F1 | `test_backend_review_evidence::test_long_history_projects_two_rounds_for_detail_and_one_for_save` | b | 3A passes the reward answer to `project_review` as a third argument; the test's spy took two. Spy now forwards `*context`. The assertion (two projections for detail, one for save, history never walked) is unchanged. | `4ad2084` |
| F2 | `test_capture_screens::test_real_capture_all_views_and_preserves_originals` | b | `scripts/capture_screens.py` waited for the dialog "Preview as a member" and clicked Pause. 3B renamed it "Play it as a member" and removed autoplay. Script waits for the new name, no Pause, caption says "stepped". | `4ad2084` |
| F3 | `test_chapters_ui::test_about_is_consistent_keyboard_modal_in_every_chapter[sample-390]` | **a** (looked like a flake) | The test asserted without waiting, but the failure was not only that. The menu opens, then moves focus to its first item on the next animation frame. At 390 the first item is "My surveys". The test focuses "How we check" and presses Enter; when that frame landed in between, focus jumped to "My surveys" and Enter went there. That is a real race for keyboard and assistive-tech users. New red test `test_opening_the_menu_never_steals_focus_the_user_already_moved` (390, fails before the fix with focus on the wrong item), then `site/menu.js` only moves to the first item if focus is not already inside the menu. The About test also now waits with `expect(...).to_be_visible / to_be_focused / to_be_hidden` and `wait_for_function`, no fixed sleeps. Isolated: 4/4 passed, three runs in a row. | `45df199` |
| F4 | `test_header_verdict_a11y::test_verdict_accessibility_tree_and_keyboard_path` | b | Asserted the first H3 is "Member experience"; the setup card (3B) is now first. Same intent (H1 > H2 > H3, no skipped level): "Member experience" is an H3 and no heading level in the chapter jumps by more than one. | `830b468` |
| F5 | `test_improve_ui::test_queue_saves_adds_advances_and_undo_reopens` | b | Legacy-chrome check listed `.journey`, which is now the new strip's class and legitimately sits in the Fix header. Selector is `.energy-map`, the same change 3B made in `test_chapters_ui`. Rail, toolbar and next-issue bar are still asserted absent. | `830b468` |
| F6 | `test_overview_ui::test_supplied_overview_signals_strengths_and_energy` | **a** | `#chapter-overview .btn-primary` resolved to two buttons: Start fixing and the setup card's Confirm (and Save reward). The board-redesign contract is that `#start-improving` is the only primary in the chapter. New red test `test_the_verdict_keeps_one_primary_button_whatever_the_setup_card_is_asking` (3 primaries before), then `site/setup-card.js`: Confirm and Save reward are `btn-secondary`. The original failure now passes untouched. | `4ad2084` |
| F7 | `test_setup_and_delta_ui::test_without_the_setup_fields_there_is_no_card` | b | It relied on the stale `data.js` lacking the fields. The sample now carries them, so the test removes `survey_type_detection` and `reward` explicitly. Same assertion: no fields, no card. | `4ad2084` |
| F8 | `test_site_e2e::test_on_a_phone_the_phone_is_the_hero_and_opens_on_the_problem` | caused by my first `data.js` (not a product regression) | Phone started at y=432 (limit 422). Probe of both trees: header 67 px vs 53 px at 2D, the extra 14 px being the version chip my `version: 1` produced. Real-server probe at 390 gives phone y=403 in both the 2D worktree and HEAD, so the real page is unchanged. Fixed by dropping `version` from the sample (see data.js above). Test untouched, passes. | `d3b86fb`, fixed in `830b468` |
| F9 | `test_unified_workspace::test_saved_review_opens_phone_and_shared_system` | b | Expected `summary?download=1`; with the real server the link is now `detail.share.summary_url` (`download=true`, 3A/3C). Test asserts the href equals that field and is the `download=true` route. | `ec3e73f` |
| F10 | `test_workspace_contracts::test_legacy_phone_link_and_keyboard_issue_navigation` | b | Same as F9. | `ec3e73f` |

The four failures 3C saw from 3B's unfinished work are gone, as 3B's final commits fixed them: the two `index.html`/390 cases and the phone-hero case passed in run 1 except for F8's data.js cause above; the token check passes. About the token check: `--sec`, `--label` and `--count` are **declared** in `site/journey.css` (`--sec:1`, `--label:0`, `--count:1`) and `site/phone-tools.css` (`--sec:1`), with JS setting them per element (seconds, label length, segment count). They are layout inputs, not design tokens (no colour, spacing or type value), so putting them in the design-system token file would be wrong; the test resolves them honestly and I did not silence it.

## Accessibility sweep (new `tests/test_a11y_sweep.py`, 23 tests, 187 lines)

Five surfaces (Home, Verdict with journey, Fix, Sign off, Play-as-a-member dialog opened by keyboard) at 1440 and 390:

| Rule | How |
|---|---|
| no horizontal page scroll | `scrollWidth - innerWidth <= 0` |
| every interactive control has an accessible name | computed from aria-label, aria-labelledby, label, text, alt, title |
| exactly one H1 | visible `h1` count |
| aria-live regions not duplicated | unique ids, none nested in another live region, no identical announcement text in two regions |
| state never by colour alone | every `.state-chip` has text; every bare `.state-icon` sits in a control, row or paragraph whose text (screen-reader text included) names the state |
| hit areas | every visible control at least 24x24 CSS px; every `.btn-primary` at least 44 px high |
| visible focus on every tab stop | real Tab presses, computed outline or ring on the focused element (or its wrapping label); wrap-around detected with a marker attribute |
| reduced motion | on all five surfaces: no running animation, no `animation-name`, no transition duration; probe elements for `.celebrate-mark/.celebrate-dot/.progress-ring`; plus the real completion moment on the real server with motion reduced before the last fix (`getAnimations()` is empty) |

All 23 pass on the current tree: no product defect was found by the sweep itself (F6 was found by an older test). To prove the checks bite, I injected defects at runtime on the Verdict (scratch script in `/tmp`, nothing committed): a nameless button, a 10 px button, a second H1, an empty state chip, a 3000 px element, duplicate live ids and text, and `outline:none` on Start fixing were all reported; an injected animation under reduced motion was reported as 0 only because the global rule suppresses it (that rule is the protection being tested). Two test bugs were fixed while writing it (focus wrap detection; the dialog opening by mouse leaves a script-focused button without a keyboard ring, which is correct browser behaviour, so the sweep opens it by keyboard).

## Not done / judgement calls

- **Static sample shows no setup card and no Sign off** (see above). Data is ready; the shell has no code for them.
- The four "state" rules use the state markup the code has today (`.state-chip`, `.state-icon`). A new state widget with another class would need to be added to the sweep.
- Journey pins are `aria-hidden` icons; their state words live in the segment button's screen-reader text and the hover/focus tooltip. The sweep accepts that (the icon shapes differ and the words exist), as 3B designed.
- `test_a11y_sweep` is about 9 s because it uses intercepted synthetic data; the real-server completion test is the slow one.

## Commits (named files only)

`d3b86fb` data.js + generator; `4ad2084` setup buttons, capture script, history spy, one-primary test; `830b468` data.js without `version`, F4, F5; `ec3e73f` F9, F10; `45df199` menu focus race and About test; `16b4c25` sweep; then this report.
Untracked `review/after/*`, `review/*.png`, `tests/_phase*_*.py`, `uglyhome.png` pre-existed and were not touched or staged.
