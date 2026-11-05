# Workstream 3C: Sign off & share, Home (site)

Branch `feature/surveycoach-mvp`. Offline, synthetic data, no `surveycoach/` Python touched, `site/data.js` not regenerated, no push, no delegation.
Commits: `6915a6a` sign off + logo + developer flag + test-link line, `0950c88` Home, `62aace0` real-server test + banned-word scan, then this report.

## Done

### Sign off step (replaces Share; hash `#share` and all element ids kept: `#share-summary`, `#change-list`, `#copy-all`, `#kept-reasons`, `#version-changes`, `#download-summary`)
- **Review summary card** (`site/share-card.js`): survey name, version, link from `detail.share.link` as plain text (never `snapshot.source_url`, never an `<a>`), verdict chip + headline, open counts ("1 to fix · 1 to improve · 1 to check · 2 of 5 handled"), time label, checked date, the You check list (signed record's list with who/when when it exists, otherwise the live list with Done / Kept / Still to check).
- **Copy Slack post** (hero, the only `.btn-primary` on the step): copies `detail.share.slack_post` exactly via `SC.copyWithToast` (async clipboard, textarea fallback), toast "Copied", one polite announcement; the post is shown read-only below it. Disabled with an explanation when `slack_post` is null.
- **Download summary**: secondary, uses `detail.share.summary_url` (falls back to the old URL when the payload has no `share`).
- **Sign-off** (`site/signoff.js`): name input prefilled from `localStorage` (`surveycoach-signoff-name`, only place it is stored), validated 1-80 chars after whitespace folding with inline `role=alert` error and `aria-invalid`; button "I've reviewed this survey"; when not ready, "Sign off with N open items" plus checkbox "I know N items are still open" (refused locally with an inline error if unticked; sends `acknowledge_open: true`; never sends it when the verdict is ready). "Open now: ..." counts stay visible before and after signing, and the items open at signing are listed. Success is calm: "Signed off by Name · Nov 5, 2026", no confetti, "Copy Slack post again", one `SC.say` announcement, focus moves to the card heading. Double clicks send one request (busy flag set synchronously). Failure shows "Sign-off was not saved. <server message>" with a manual Retry (no automatic retry; the typed name is kept). A new version shows "Version 2 has not been signed off yet." and "Earlier sign-offs" as a quiet timeline from `signoff.history`. A re-render (detail refetch) keeps focus on the same element id. Read-only mode (`SC.readOnly`) disables the button and says why.
- **Developer flag** (`site/developer.js`): "Advanced · local snapshot import" (review dialog, `details.advanced-recheck`) and the Home `details.import` are `.developer-only hidden` and shown only when `window.SURVEYCOACH_DEVELOPER === true`.
- **Test-link line**: the brief's wording sits once next to the link field in the Check again dialog (`#reader-mode`). `site/entry.js` no longer overwrites it with the server's engineering notice ("This reader blocks answer writes..."), which the server still sends but the page ignores.
- **D4 / D16** (`site/rounds.js`): v1 with no other version renders nothing (no "First version", no zeros, no timeline); the timeline only appears once there are 2+ versions, as a vertical text timeline (not button pills; old pill rules removed from `workflow.css`); heading is `h3` now. The stray-digit pattern test (`test_site_render_0c`) still passes.

### Home
- **Logo** (`site/logo.js`, `logo.css`): inline SVG phone with a chat bubble and check, token colours only, accessible name "SurveyCoach" (`role=img`), used in the review header (`header.js`, one-line hook) and Home. The plain blue square is gone; the brand link keeps the name "SurveyCoach home".
- **How it works** (`site/home-how.js`, `home-how.css`): three steps with micro-visuals built from tokens (phone with a pin, fix card with a state chip, Slack post). Visuals are `aria-hidden`; the text carries the meaning; no links or buttons in the row. The "See / Improve / Share" strip is removed.
- **Example mini-demo**: tagged "Example · fictional survey"; "Use" swaps the struck-through question for the new wording, updates the chip ("2 things to fix" to "1 thing to fix"), says "Question 4 now reads: ..." once through a polite region, moves focus to Reset; Reset restores everything. The duplicate "2 / 2 must-fix issues / 2 must-fix" is now one chip. The suggested wording uses body ink with a green left border instead of pale green text (I first thought a screenshot showed pale text; it was the 360 ms fade-in, opacity is 1 and the colour is `rgb(15, 27, 45)` after it).
- **D10**: Home never shows "Checking…" unless a live job has a `stage` (`card-status.js` already did this; now covered by a test: queued, running without stage, running with stage, completed, no job).
- Home fits 390px with no sideways scroll, one primary button, 44px targets.

### Tests (new)
- `tests/test_signoff_ui.py` (21): card facts and no source address (token URL absent from text and HTML), exact Slack copy, clipboard textarea fallback, ready sign-off, remembered name, name errors (empty, spaces, 81 chars, exactly 80 ok), not ready with acknowledge, ready never acknowledges, double click, failure + manual retry, v2 unsigned with history, signing v2 keeps the v1 record, v1 has no empty comparison, timeline is not buttons, developer flag hides/shows the import, test-link line once and in the brief's words, 390px (ready and not ready), keyboard-only path.
- `tests/test_signoff_real_server.py` (1): real server, real stored concept review, v1 signed with items open, v2 unsigned, copy equals the server's post, sign with acknowledge, record survives reload.
- `tests/test_home_how_it_works.py` (8): logo name on Home and review header, steps and micro-visuals, example labelled once and not pale, demo by keyboard and reset, 390px, no false "Checking…", banned words in Home default and demo-used states.
- `tests/test_copy_banned_words.py`: added a Sign off scan for ready / not ready / signed at 1280 and 390 (6 cases, all clean).
- Helpers: `tests/signoff_helpers.py` (3A payload shapes, POST route). Screenshot script `tests/_phase3c_shots.py` (underscore, uncommitted like the phase 2 ones).

### Older tests changed on purpose
- `test_workflow_e2e.py`: the snapshot import is developer-only now, so the test sets `SURVEYCOACH_DEVELOPER` through an init script; the summary link is the server's `summary_url` (`download=true`).
- `test_home_page.py`: the example is no longer one labelled image; See/Improve/Share is now the three How it works steps. No safety assertion was weakened.

## Test results (exact)
Focused run: `test_home_page, test_home_how_it_works, test_chapters_ui, test_site_e2e, test_start_review_e2e, test_copy_banned_words, test_design_tokens, test_loading_progress, test_status_server, test_signoff_ui, test_signoff_real_server, test_share_ui, test_share_state_ui, test_site_render_0c, test_workflow_e2e, test_header_verdict_a11y`:
**184 passed, 4 failed**. Not run: the whole suite.

The 4 failures are not 3C; all come from 3B's journey work in progress in the shared tree:
- `test_chapters_ui::test_static_sample_uses_shell_and_redirect_keeps_query_and_hash` (`.journey` now exists on index.html; test still expects none)
- `test_chapters_ui::test_about_is_consistent_keyboard_modal_in_every_chapter[review-390]` and `test_site_e2e::test_on_a_phone_the_phone_is_the_hero_and_opens_on_the_problem` (journey strip is 3 px wider than the 390 viewport: `LI.journey-section`, `OL.journey-segs`, right edge 393)
- `test_design_tokens::test_all_css_token_references_resolve` (`--count`, `--label`, `--sec` used in `journey.css`, defined nowhere)

## Hooks into files other workers touch
- `site/header.js`: one line (logo mark in the brand link).
- `site/review.html` and `site/index.html`: my script/link tags (`logo.js`, `logo.css`, `developer.js`, `share-card.js`, `signoff.js`, `signoff.css`) are in the same lines as 3B's journey/member-preview tags, so my commit `6915a6a` also carried 3B's hunks for those two files (they reference `journey.js`, `member-preview.js`, `playback.js`, which were untracked at that moment). Nothing of 3B's other files was committed.
- `site/index.html` (static sample) has no Sign off content; it only gets the logo.

## Not done / judgement calls
- Screenshots are in `review/after/phase3/` (uncommitted): Sign off ready, not ready, signed, Home, and the Home demo after "Use", at 1440 and 390. I looked at not-ready 1440 and Home 1440 only.
- Versions list newest first (server order), so the timeline reads Version 2 above Version 1; I did not reorder it because old tests expect the server order.
- Before signing, "who/when" in the You check list is not known (no accounts, and the record has none yet); it shows Done / Kept / Still to check, and who/when appear once signed.
- The "Changes you chose" block, Copy all changes and the round comparison for v2+ remain below the sign-off (old tests depend on them); `Copy all changes` is now secondary so the Slack button is the one primary action.
- The test-link line is only in the Check again dialog (next to the link field). The Sign off step shows the link as text, not a field, so it carries no second copy of the line.
- The server's `/api/reader/mode` notice still contains "reader"/"partial test participant" wording; I did not touch Python, the page just no longer displays it.
- `site/data.js` is stale for `share`/`signoff` (not regenerated, as instructed); the UI degrades without them (Slack button disabled, sign-off hidden).
