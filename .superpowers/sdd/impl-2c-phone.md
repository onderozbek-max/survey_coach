# Workstream 2C: phone fidelity (site)

Branch `feature/surveycoach-mvp`. Offline, synthetic data, TDD, no push, no delegation. Commits: `51a4197` (feature), `933ca9e` (dead CSS removal). No Python under `surveycoach/` touched.

## Status per deliverable

| # | Item | Result |
|---|---|---|
| 1 | D1 stimulus UI | Done. `page.stimulus_text` renders above the first question in body type (not the bold question style), after any captured page media. No image is ever invented. `SC.displayedFields` (model.js) now has a page-level `stimulus` field (no `question_id`), so the Phase 0C resolver scopes rewrites: a page-level fix lands only in the stimulus, a stem fix only in its stem (tested with the same sentence in both). Findings whose evidence sits in the stimulus get their pin and highlight there instead of a floating page note. Welcome/info unchanged. |
| 2 | D8 UI | Done. `Optional` only when `required === false`; `null`/missing/true show nothing; never shown when the stem, help or an option already ends with a visible vendor "Optional" (legacy data). |
| 3 | Device frame | Done. Status bar, 8px bezel, 44px radius, home indicator, `.phone-viewport` + keyboard-reachable `.phone-screen` (tabindex 0, role region, label). Next is pinned (sticky, solid backing, always at the bottom even on short screens). A "More below ↓" cue (a pill; no gradients) shows only while content is clipped and hides at the end (`data-more`). Last list item is no longer clipped by Next (tested at 1440/1024/390 with a 10-option select-all). |
| 4 | Pins | Done. Number = `entry.n` (the per-screen number the model already assigns), label `Must-fix: <headline>, pin N`. Must-fix pins are filled, worth-improving outlined; field outline is solid vs dashed. Tint and outline sit on the affected field block only; the question-level pink wash and selected outline are removed. Several pins on one field wrap two columns so the block stays compact. |
| 5 | Text size | Done. "Aa" and `#phone-settings` are gone. Preview tools now holds a labelled `Text size` group (Small / Default / Large, `aria-pressed`, native buttons: Tab, Enter, Space), persisted in `sessionStorage` (`surveycoach.phoneTextSize`), focus survives redraw. Device size select moved there too. |
| 6 | Preview line | Done. Exactly the three sentences from the brief. Original mode with pending changes says "N changes to preview. RedJade is only changed when you edit it there." Changes plus a ghost answer appends the ghost sentence. None of hypothetical/accepted/saved/verified (tested). |
| 7 | Timeline | Done. Single-colour track, fill, marker; `~0:15 in · 6 min total`; caveat is a `title` tooltip (no visible "estimate"). Uncertain-route text and no bar are unchanged. Energy map and journey strip untouched. |

## Files

New: `site/phone-frame.js` (frame, text-size store, Next bar), `site/phone-tools.js` (Preview tools, preview line, timeline), `site/phone-frame.css`, `site/phone-tools.css`, `tests/test_phone_fidelity.py` (31 tests). Changed: `site/phone.js`, `site/model.js` (the `stimulus` field, 2 lines), `site/index.html` and `site/review.html` (script and link tags), `site/styles.css` and `site/review-studio.css` (removed dead Aa/zoned-bar rules). All under 600 lines; tokens only, no gradients, no inline colour.

## Hooks in worker 2B's files (list for the merge)

`site/app.js` only, in `renderStage` (nothing else): the `Aa`/settings block and the "Preview tools" `<details>` became one `SC.phoneTools({...})` call; the preview line is `SC.previewLine({fixesMode, changes, ghosts: SC.ghostAnswerCount(item, context())})`; the timing block is `SC.phoneTimeline({seconds, total, uncertain})`. I also removed the now-unused `settingsOpen`, `clock` destructure and `comparison` string. `state.large` is still passed in `context()` but nothing reads it any more (safe to delete). If 2B renames mode buttons, my tests use `[data-fk=queue-mode-fixes]` and the text "Original"/"With changes" in the older tests.

Pin contract for 2B: the card number should be `entry.n` from `SC.buildModel` (per-screen order). The pin `data-fk` stays `pin-<key>`.

## Existing tests I updated (behaviour intentionally changed)

`test_phone_preview.py` (pin name now ends `, pin N`; ghost-only line; Text size path), `test_site_e2e.py` (`settings()` opens Preview tools; waits for the phone first), `test_site_state_0c.py`, `test_with_fixes_preview.py` (old "Edit RedJade to make them real" copy gone).

## Verification

Focused run: `test_phone_fidelity`, `test_phone_preview`, `test_issue_loop_ui`, `test_site_e2e`, `test_design_tokens`, `test_copy_banned_words`, `test_status_server`, plus `test_site_state_0c`, `test_with_fixes_preview`, `test_member_journey`, `test_overview_ui`: all green (120 + 97 + 103 in the three runs; whole suite not run). Screenshots (uncommitted): `review/after/phase2/{welcome,question-with-stimulus,long-list}-{1440,390}.png`, made by `tests/_phase2_shots.py` (uncommitted helper).

## Notes and known limits

- The phone cannot be a true 390x844 in a normal desktop window: height is `clamp(520px, 100vh - 300px, 844px)` (844 only when the window allows). At 1440x900 it is 390x600 and the toolbar above pushes its bottom edge about 40px below the fold, so the page scrolls slightly. Fixing that is layout above the phone (2B/phase 3).
- A fix that carries a `question_id` but whose text sits in the stimulus does not map to the stimulus field; it stays a manual edit (honest, matches the resolver's "unclear target" rule).
- Demo `site/data.js` has an empty `stimulus_text` for the sample survey, so the sample site shows no concept copy until it is regenerated (not done here).
- The "More below" button has `tabindex=-1` on purpose: the focusable scroll region already covers the keyboard.
- Hit while testing: the `<details>` `toggle` event can arrive after a fast click-then-keypress, closing the drawer on redraw. `phoneTools` now reads `details.open` synchronously before each action.
