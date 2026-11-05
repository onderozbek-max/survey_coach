# Workstream 0C: site state and rendering

Branch `feature/surveycoach-mvp`. Offline only: static `site/` server, intercepted synthetic API, Node for pure model code. No RedJade, no AI, no real DB. No `surveycoach/` Python touched. No push, no delegation. Spec: `docs/product-design-review-2026-11-04.md` (D3, D4, D5, D9, D10), `.superpowers/sdd/internal-audit-ui.md` (audits 1, 2, 3, 4, 5, 6 of that file; the plan's "audit 7/8/9/10/13" numbers refer to the same defects).

TDD: each fix had a failing test first, and the red state was re-checked against `HEAD` (via `git stash -- site`, or by checking out the old `coach.js`/`rounds.js`) for every group. All new tests are in `tests/test_site_state_0c.py` (16) and `tests/test_site_render_0c.py` (25).

## What changed

| # | Defect | Fix | Where |
|---|---|---|---|
| 1 | Answer rewrite `Yes` also rewrote `Yes or no?` and the help text | A fix gets a typed field address (`stem`, `help`, `option:N`, `scale`, `page`) resolved against the **displayed** fields. Exact match beats partial; anything not unique (duplicate labels, a word shared by stem and answers) resolves to `null` and stays manual. `applyFixes` honors it (`string` = that field only, `null` = nowhere, `undefined` = legacy page/question scope for raw callers). Phone resolves per page in `SC.renderPhone`, so every consumer (phone, comparison, hits, copy) goes through one resolver. Copy text and the change sheet already used exact `current_text`/`picked_text`; a regression test now pins that. | `model.js` (`displayedFields`, `fixField`, `scopeFixes`, `applyFixes`), `phone.js` |
| 2 | `hitsOn` counted raw page text the phone never shows | `hitsOn` and `pageTexts` are now derived from `SC.displayedFields(page)`, which mirrors `phone.js` (intro precedence, no options for dropdown/grid/text/rating/slider, scale ends only for rating/slider, validation screen not replaceable). A test renders nine control kinds and asserts `hits == visible replacements`. | `model.js` |
| 3 | Delayed save advanced the wrong item | Completion is bound to the originating queue item (`ctx.originId`). `queue.advance(origin)` and `queue.isActive(origin)` refuse unless that item is still active in the Improve chapter. A late completion reports through the toast only: no navigation, no status text, no focus theft. | `improve-actions.js`, `queue.js`, `coach.js` |
| 4 | Alternative wording changed coach but not phone | New `SC.drafts` store (per fingerprint, scoped by survey id and version, invalidated when the candidate set changes, never persisted). `choiceOf` in `app.js` reads draft first, so phone, comparison and coach share one selection; clicking an alternative redraws only the phone (scroll and focus kept). Cleared when a save succeeds. | new `drafts.js`, `app.js`, `coach.js` |
| 5 | Running recheck that fails left the previous review unloaded | `review(carriedFailure)`: a terminal job failure is caught, the previous review is reloaded and the failure is carried into the status banner (`data-tone=error`), even if the refetch no longer carries the failed job. Same for the known-pending-job path. | `workflow.js` |
| 6 | Uncertain-POST marker blocked reading existing reviews | With a `surveyId` the review opens, with a calm notice (`data-tone=notice`, new token-only style) in `#review-status`. Submissions stay locked (`lockRead(false)` is ignored while uncertain); the marker is never replaced or cleared (`remember`/`forget` are no-ops while uncertain). Decisions and rename are read-only (`SC.readOnly`). Home behavior (no `surveyId`) is unchanged. | `workflow.js`, `app.js`, `design-system.css` |
| 7 (D4) | `0000` | Explicit `> 0 ? … : null` in `rounds.js`, `coach.js`, and `share.js` (the static test found a third instance that `mount` was masking). `h()` untouched. Static test rejects `\.length\s*&&\s*h\(` in `site/*.js` and `*.html`. | `rounds.js`, `coach.js`, `share.js` |
| 8 (D5) | "Use all 2 suggestions" | Counts applicable suggestions only, pluralized, hidden under 2, applies to those only, says how many findings have no suggestion, and is disabled with a visible reason (`aria-describedby`) when all are already chosen. | `coach.js` |
| 9 (D3) | Unpadded buttons, button looks like an input | `.btn` added at `review.html` (check-again, download, next version), `about.js`, `quality.js`, `share.js`. `.btn`/`.btn-secondary` now use `--accent-soft` fill and `--accent` text (tokens only; accent/accent-soft contrast is already in the token test). The redundant `#chapter-share .btn-secondary` rule was removed. | `design-system.css`, `chapters.css`, html/js |
| 10 (D9) | Five different counters | New `progress.js`: `itemDecided`, `itemRelated`, `findingOnPage`, `progressOf/All/OnScreen`, `progressText`. Tabs show `label` + `N of M done` (or `none`), the toolbar line is `N of M done` over all tiers, drawer flags use the same items (`N of M done`, or `No items`, alert icon only while something is open). Position in the list no longer appears anywhere. Two-line tab captions keep the toolbar the same height at 1440px and fit at 390px. | `progress.js`, `queue.js`, `issue-list.js`, `review-studio.css` |
| 11 (D10) | "Checking…" on a finished review | New `card-status.js` (`SC.surveyStatus`): `Checking…` only for a live job with a real `stage`; otherwise `Queued`/`In progress`, `N must-fix(es)`, `Ready to share`, the readiness verdict (`SC.READINESS`), `Not checked yet`, or `Check did not finish`. Fixes "1 must-fixes" too. | `card-status.js`, `workflow.js`, `local.html` |

New script tags: `drafts.js` and `progress.js` in `review.html` and `index.html`; `card-status.js` in `local.html`.

## Tests

Existing tests changed on purpose (intended behavior change, no loosened assertions):
- `test_phone_preview.py`: an intro screen shows one copy, so `pageTexts` is `['Welcome!']`.
- `test_home_page.py`: chips are now verdicts, not `Checking…`.
- `test_improve_ui.py`, `test_improve_safety_ui.py`, `test_queue_position.py`: position captions (`Must-fix 1/3`, `… handled`) replaced by the one `N of M done` model; `test_queue_position.py` now pins that progress ignores which item is open.
- `test_site_e2e.py`: drawer text `0 findings` → `No items`.

Final run (offline): the requested loading tests (`test_loading_progress.py`, `test_reader_loading.py`), `test_issue_loop_ui.py`, `test_home_page.py`, `test_workflow_e2e.py`, `test_start_review_e2e.py`, `test_design_tokens.py`, both new files, plus the touched/adjacent preview and improve suites: **137 passed, 1 failed**. In addition every test file that drives the static site or the JS model (33 files, 350 tests, run before the final tidy): 348 passed, 2 failed.

The 3 failures are **not from this work**; each fails identically with `site/` at `HEAD`:
- `test_start_review_e2e.py::test_link_start_to_saved_review_preserves_partial_coverage` ("0 captured screens" vs "3 captured screens checked").
- `test_chapters_ui.py::test_about_discloses_absent_ai_blockers[disabled-21]` and `[wording_failure-33]` (check totals 20/32 vs 21/33).
Both look like in-flight changes under `surveycoach/reader` / checks (other workers).

All files stay under 600 lines (largest: `app.js` 410, `workflow.js` 340; new modules 25–40 lines).

## Judgment calls and limits (please review)

1. **Read-only reading of "block writes".** I read "block new submissions/writes but open existing reviews read-only" literally: with an uncertain marker, new checks, decision saves (Use/Keep) and title rename are disabled; previews, navigation, copying text from the phone and reading are not. Decisions are local and revision-guarded, so if you wanted only submissions blocked, delete the `SC.readOnly` block in `app.js` `renderAll`/`saveDecision`, and the rename guard in `workflow.js`; nothing else depends on it.
2. **`applyFixes` without a field is unchanged** (legacy page/question scope), because `energy.js` reading-time projection and several Node tests call it with canonical basis fields that have no field address. The audit's raw one-liner (`SC.applyFixes('Yes or no?', [f], null, {page_id, question_id})`) therefore still replaces; the rendered phone, hit counts, comparison and copy text no longer do. Making the raw call strict would break the canonical-reading projection contract (`test_preview_reading_projection.py` asserts dropdown/grid options count for reading time). The reading-time note under "Compare wording" can still count the same word in two fields until Python exposes a field identity on `reading_basis`; I did not touch that.
3. **Ambiguity stays manual.** A rewrite whose `from` matches several displayed fields (e.g. `Yes` in stem, help and an answer when no field equals it exactly) is no longer previewed at all. That is intentional (audit: "ambiguous matches should stay manual"), but a finding whose `current_text` is a phrase inside a stem that is also the whole text of an answer will resolve to the answer.
4. **Dropdown/grid option rewrites** are now "off the phone" (not hit), matching what the phone renders; before they were counted in `pageTexts` but not `hitsOn`.
5. **"Checking…" for a running job without `stage`** now reads "In progress" (the listing may not carry `stage`; I could not confirm the list payload offline).
6. **D13** (no-issue card spacing) was in the reading list but not the fix list; left for phase 2 where that card is replaced.
7. A late save's toast still carries Undo after the user navigated away; only navigation, focus and status text are suppressed.

## Follow-ups for other owners
- Python: expose a field identity on `reading_basis` entries if the reading-time estimate must also be field-scoped.
- Phase 1 header/verdict work can reuse `SC.progressAll` / `SC.progressText`.
