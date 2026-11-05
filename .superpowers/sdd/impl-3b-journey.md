# Workstream 3B: journey strip, Play it as a member, setup card, version delta (site)

Branch `feature/surveycoach-mvp`. Offline, synthetic data, intercepted writes, no live calls. `site/data.js` not regenerated, `surveycoach/` untouched, nothing pushed.
Commits: `db8c16b` (journey, dialog, setup card, delta, energy map retired), `bd61510` (D15 focus ring, plain-words scan), `cea4a80` (tooltip placement, compact pins, reward legend, dialog header), then this report.

## Done

| # | Item | Where |
|---|---|---|
| 1 | **Journey strip.** One segment per screen, width = served seconds (flex-grow, no other encoding, one neutral fill). Section labels above from `journey_sections` (served label wins; neutral labels such as `Screens 1-13` drawn exactly as served). Every segment shows its screen number (D11: none skipped, last one included). Pins use the four-state icon plus sr-only state words. Hover and keyboard-focus tooltip from the served `tooltip` text (Escape hides it, it sits right under its segment). One tab stop with roving tabindex: arrows, Home, End; Enter/Space click. Selected segment: `aria-current=step`, 3px outline, underline. `aria-label` summarises the journey. Text list alternative in a `details`. Narrow widths scroll the strip sideways with a visible "Scroll sideways to see every screen" hint (page never scrolls horizontally at 390). | `site/journey.js`, `journey.css` |
| 2 | **Used on the Verdict** (replaces the Energy map, legend and guide), **compactly in the Fix header** (`#improve-bar`, section labels dropped, number over pin, focus kept across re-renders via `data-fk`), and **under the phone**: `SC.phoneTimeline` keeps `~0:15 in · 6 min total`, `.timebar[aria-hidden]` and its single `<i>` marker, internals are now one `b` per screen (width = seconds, filled up to the current screen). Old `energy.js` deleted: `playback.js` keeps the playback clock and reading-time evidence, `member-preview.js` the dialog. Energy CSS removed from `overview.css`, `review-studio.css`. | `phone-tools.js/css`, `playback.js`, `overview.js/css`, `app.js` (3 lines) |
| 3 | **Play it as a member**: full-screen dialog "Play it as a member". Steps through the phone screens in order with Back/Next and the strip as a jump bar. Running time line ("Elapsed estimate: about 0:14 of about 3½ minutes"; for an uncertain route it keeps the old wording with no elapsed route). No pins at all (entries emptied, phone inert). Escape closes and returns focus, explicit Tab trap, one dialog at a time, closes on chapter change. The time-estimate explanation is the info popover (`SC.timeInfoButton`, was `energyInfoButton`; text rewritten: no colour or fatigue claims). | `member-preview.js/css`, `quality.js/css` |
| 4 | **Setup card** (replaces the bottom radio row): "Two quick checks so the verdict is right". Type: "Looks like a concept test" + confidence chip, Confirm / Change (the five existing options, existing PATCH). Reward: No / Yes + text (`maxlength` 120), `PUT /api/surveys/{id}/reward`. Optimistic, error with Retry (old answer put back), `busy` guard so a double activation sends one request, refetch via `SC.updateSurvey` / `SC.refreshDetail`. Collapses to "Survey type: Concept test · Reward: none (Change)". Never blocks the verdict. Not drawn when the page cannot save or the server did not send the fields. User text is shown with `textContent`. | `setup-card.js`, `verdict-setup.css` |
| 5 | **Since last version** card: served summary, served caveat, expandable before/after per fixed item ("Fixed with your rewrite" or the served resolution; a missing before/after is left out), "couldn't compare" box always visible when > 0, still/new folded lists, empty buckets draw nothing. Null or v1: not drawn (D16). Sits right after the hero. | `version-delta.js`, `verdict-setup.css` |
| 6 | **D15**: no tiny phone on the Verdict (test keeps `.overview-mini, .phone` count 0). Heading focus ring only after a key press (`html[data-input=keyboard]`, set in `overview.js`; `verdict.css` hides the ring otherwise). | `overview.js`, `verdict.css` |
| 7 | **Tests**: `test_journey_ui` (17), `test_member_preview_ui` (8), `test_setup_and_delta_ui` (18), `test_focus_ring` (2), banned-words scan extended (journey, setup incl. error state, delta, dialog; 2 widths). | `tests/` |

## Retired or changed tests (named replacements)

- `test_overview_ui`: six energy-dialog tests (scrub/pause, high energy, trap/reopen, uncertain path, keyboard scrub, auto-advance) retired. Replacements: `test_member_preview_ui` (steps, trap, Escape/focus, running time, uncertain route, 390) and `test_journey_ui` (keyboard, widths, labels). Autoplay is gone from the dialog (Back/Next per the brief); the phone's own "Play as a member" walkthrough is untouched. The energy-bar assertions became journey assertions; the style tests now open the type options through the setup card's Change and use a stand-in PATCH that flags `confirmed`.
- `test_recommendation_ui_clarity`: `test_compact_energy_legend_navigation_and_mobile_layout` retired (the energy legend no longer exists).
- `test_quality_ui`: renamed to the time-estimate popover (labels, title, and "Segment width"; colour and fatigue-zone numbers dropped because the colour encoding is gone). No safety assertion weakened.
- `test_chapters_ui`: the legacy-rail check `#rail, .toolbar, .journey` now reads `... .energy-map` (`.journey` is now the new strip's class).
- `test_preview_reading_projection`: loads `playback.js` instead of `energy.js`.

## Results (exact)

- Batch A: `test_journey_ui, test_member_preview_ui, test_setup_and_delta_ui, test_focus_ring, test_overview_ui, test_chapters_ui, test_copy_banned_words, test_design_tokens, test_header_verdict_a11y`: **117 passed, 1 failed**. The failure is `test_chapters_ui::test_about_is_consistent_keyboard_modal_in_every_chapter[review-390]`; it passed 4/4 twice when run alone (it failed once earlier on `sample-390`). It asserts the About dialog without waiting, in the Sign off chapter (3C's), so I classify it as a load-dependent flake, not caused by this work.
- Batch B: `test_phone_fidelity, test_fix_flow_ui, test_site_e2e, test_quality_ui, test_recommendation_ui_clarity, test_member_journey, test_improve_navigation_ui, test_preview_reading_projection`: **107 passed**.
- One earlier combined run saw `test_time_estimate_tooltip_hover...[390]` fail once; 3 solo reruns all passed (hover state left by the previous test).
- Not run: whole suite, `test_demo_export` and `test_copy_deck` committed-data checks (still red until someone regenerates `site/data.js`, as 3A said).

## Screenshots (uncommitted, `review/after/phase3/`)

`verdict-journey-{1440,390}.png`, `journey-tooltip-*`, `setup-card-*`, `delta-card-*`, `verdict-v2-collapsed-setup-*`, `play-as-member-*`. The 1440 screenshots were checked by eye (labels all visible, segments proportional, tooltip under its segment, pins stacked). The first dialog shots showed cramped compact pins; fixed in `cea4a80` and re-shot.

## Judgement calls to sanity check

1. **Floors break strict proportionality, on purpose.** A segment never goes below 28px (44px on touch devices) and a section never below its whole label (a 5 s Welcome gets about 65px at 1440). Everything above the floors is exactly proportional (tests measure it; a floor only ever makes a section wider, never narrower than its time).
2. **Fix header strip is hidden below 760px.** The existing e2e contract says the phone must start in the top half at 390 and it had 4px of headroom; the strip would push it to y=509. Navigation there is the pager, All screens, and the new bar under the phone. The Verdict and dialog strips stay at 390.
3. **Journey tolerance for stale data.** Committed `site/data.js` has no `presentation.journey`, so with it the Verdict simply has no strip (no fake fallback built from the energy data). A regenerated `data.js` fixes that; the sample's setup card also stays hidden (no `survey_type_detection`/`reward`, and the sample cannot save).
4. **`SC.timeInfoButton`** replaces `energyInfoButton` (quality.js, not in my ownership list but its text described colour zones that no longer exist).
5. **Autoplay removed from the dialog** (Back/Next per the brief).
6. Segment pins show open items only (3A's rule), so a screen whose items are all handled has no pin.

## Hooks into others' files (all small)

- `site/app.js` (3 lines): mounts the compact strip into `#improve-bar`, passes `journey` and `pageId` to `SC.phoneTimeline`, drops the two energy-bar focus lines.
- `site/index.html`, `site/review.html`: script and link tags only (staged by hunk, so 3C's lines were never touched). `site/queue.js` not touched.
- No edits to `share.js`, `rounds.js`, `home*`, `workflow.js`, `signoff*`, `logo*`, `share-card.js`, `developer.js`.

## Not done

- No axe (not approved). No visual regression snapshots beyond the screenshots above.
- Dialog "Play it" still renders the phone at 390 CSS px max; no larger variant (D15 asks for none or a readable one; it is readable).
