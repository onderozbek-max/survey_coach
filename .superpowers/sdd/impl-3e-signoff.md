# Workstream 3E: Sign off consistency

Branch `feature/surveycoach-mvp`. Offline, synthetic data, no push, no live calls, no delegation. Named files only were staged.
Commits: `f6a5b04` (A and B), `af483ac` (C), `21b28c2` (D), `3e6746d` (token test, `--tray-h`, `data.js`), then this report.

## A. Root cause of (1) and (2)

**(1) Two surveys and two verdicts on one page: a screenshot-harness artifact.** `tests/signoff_helpers.py` (3C) hand-typed the Slack post as a constant (`SLACK = 'Survey review: Sunrise Skillet Concept Test (v2) ... Almost ready: 1 quick improvement and 2 things to check yourself ...'`) and injected it as `detail.share` into the Boxer Briefs demo detail, whose verdict was ALSO hand-typed (`'Ready for sign-off'`, `'2 of 2 handled'`). The card read the real (demo) title and the injected verdict; the post preview showed the typed constant. No server code mixed fixtures. `tests/_phase3c_shots.py` uses that helper, so `signoff-ready-1440.png` showed both. Fixed: the helper now computes `detail['share']` with the server's own `share_payload(detail)` after the verdict and items are set, so the harness can no longer disagree with itself.

**(2) Three "Checked by hand" items on the card, one in the post: a REAL bug (plus the artifact above).** The card (`share-card.js`) and the HTML summary (`review_card.py`) listed EVERY You check row under the heading "Checked by hand", including open and kept ones; the post (`slack.py`) listed only the ticked ones (and put kept ones under "Kept on purpose"). A real review with 2 ticked, 1 kept, 3 open showed 6 rows on the card and 2 in the post.

**Two more real divergences found by the new test:**
- Survey name: the card used `SC.surveyName` ("Untitled survey" for a generic title such as "Surveys"); the post and the summary used the raw title ("Surveys").
- Open counts: the HTML summary said `Fix 0 · Improve 1 · You check 6`, the card said `1 to improve · 6 to check`.

Root cause in one line: the card (browser), the post (`slack.py`) and the summary (`review_card.py`) each picked their own facts out of the detail.

## B. Fix: one source

New `surveycoach/server/review_facts.py` (77 lines): `review_facts(detail)` returns name, version, verdict (kind, headline), open (counts, the words, handled/total), `checked_by_hand` (ticked You check items, with who/when from the signed record), `still_to_check`, `kept` (headline, place, reason), `fixed`. Also `survey_name` and `open_text`.
- `slack.py` builds the post only from the facts (`slack_post(detail, facts)`); `share_payload` now also serves `detail.share.facts`.
- `review_card.py` (HTML download) lays out the same facts: Checked by hand (ticked), Still to check, Kept on purpose, Fixed since. The HTML `<h1>` also uses `survey_name`.
- `share-card.js` renders `detail.share.facts` (no rebuild in the browser); `signoff.js` "Open now: ..." reads `facts.open.text`. `SC.openSummary` and the browser-side You check row builder are gone. The card has three lists: Checked by hand, Still to check, Kept on purpose (with "accepted risk, not verified fixes").
- Verdict page headline is `overview.verdict.headline`; `facts.verdict.headline` is copied from it. Asserted equal.

Test (written before the fix; it failed on `checked` for all three cases, and on the name for the generic title once the checked list was fixed): `tests/test_signoff_consistency.py` (3 cases, real review in a temporary database: 2 You check items ticked, 1 You check item kept with a reason, 1 finding kept with a reason, signed with open items acknowledged, all through the server's own routes; the real site on a real uvicorn server). For `named-v1`, `generic-title-v1` ("Surveys" with a link that gives the server nothing to name it from) and `named-v2`, it compares card, Slack post, HTML download and Verdict headline on: name, version, verdict headline, checked by hand (list), kept on purpose (list), open words (card and HTML and the "Open now" line), plus that the preview is the post byte for byte and no link token leaks. Expected values are computed from the stored detail, not by the code under test.
Mutation check: using `detail['title']` in the post makes the generic-title case fail with `slack post disagrees on name: 'Surveys' != 'Untitled survey'`.

## C. Legacy blocks on Sign off

- (3) "Changes you chose" summary: `#share-summary` is now only `N changes chosen` (no open count, no kept count). It can never contradict the verdict because it makes no such claim. The `#kept-reasons` block is deleted (the card's Kept on purpose list replaces it, same caveat text). I kept the list of chosen changes with diffs and Copy change/Copy all (old tests and real use depend on it) rather than replacing it with the tray data: the old tests inject decisions without `my_changes`, so a tray-fed list would have meant rewriting them. Judgement call; the tray's own count and this list's count agree on a real server.
- (4) `renderRounds` (`rounds.js`, now 32 lines): the "Since version N" heading, the "N no longer flagged · N still flagged · N new · N uncertain" line, the "not blanket verification" jargon and the four detail lists are deleted. In their place: `See what changed since vN` (only on v2+ with `detail.version_delta`), a link to the Verdict page that focuses the "Since last version" card (`#delta-h` got `tabindex=-1`). On v1 nothing at all. The version timeline stays (it is the only way to switch versions; old tests rely on it), under a plain "Versions" heading.
- The four-bucket honesty (fixed / still / new / couldn't compare, plus the "Fixed = no longer flagged by our checks." caveat) now lives only in the Verdict delta card (`version-delta.js`, from `detail.version_delta`, unchanged).

Old tests changed (same safety intent, named replacement):
| Test | Change | Replacement |
|---|---|---|
| `test_share_ui::test_share_explicit_grouped_changes_copy_and_kept_reasons` (renamed `..._and_copy`) | summary is `2 changes chosen`; kept-reasons block asserted gone | card Kept on purpose: `test_signoff_finish_line::test_kept_on_purpose_is_in_the_card_and_the_post_with_the_same_reason`, `test_signoff_consistency` |
| `test_share_ui::test_share_zero_changes_and_honest_version_evidence` | no "Since version"/"no longer flagged" on Sign off | `test_signoff_finish_line::test_a_later_version_links_to_the_delta_card_and_carries_none_of_the_old_block` |
| `test_share_state_ui` (3 tests; one renamed `..._never_counts_open_items`) | summary text; no claim without a comparison | `test_no_link_on_version_one_and_none_without_a_comparison`, consistency test |
| `test_issue_loop_ui::test_keep_needs_a_reason_chip_and_mobile_finish_loop` | `.round-comparison` gone, not "no longer flagged" on Sign off | finish-line tests |
| `test_issue_loop_ui::test_failed_save_changes_nothing_and_round_evidence_is_readable` | the round evidence check now calls `SC.renderVersionDelta`: before/after, "couldn't compare", caveat. **The "couldn't compare" guarantee is kept and asserted** | the delta card itself |
| `test_site_render_0c::test_zero_count_round_shows_no_stray_digits` | stray-digit scan runs over all of Sign off; `.round-comparison` gone | same scan, wider |
| `test_signoff_ui` | uses `detail['share']` (real server code) instead of the typed `SLACK`/`LINK` constants; ready card has no "Still to check" group | `signoff_helpers.py` builds share with `share_payload` |
| `test_slack_post` | hand-built verdict fixture gets `tiles` (the facts read them) | n/a |

New: `tests/test_signoff_finish_line.py` (6 tests, mutation checked against the old `share.js`/`rounds.js`: all 6 fail on the old code): no open/kept claim in the change list (ready and not ready), link to the delta card then the four buckets shown there and none of the jargon on Sign off, timeline stays, no link on v1 or without a comparison, kept list in card and post with the same reason.

## D. Polish

- **More below cue** (`phone-frame.js/css`): it was a dark pill floating a guessed 84 px above the bottom (`--next-h:76px`), on top of the last visible answer, and a clickable button. Now a non-interactive `div aria-hidden` (no tab stop, `pointer-events:none`), a 32 px fade (`linear-gradient(to top, var(--phone-bg), transparent)`) sitting exactly on the Next bar: the bar's real height is measured into `--next-h` (resize-observed, so text size changes keep it right). Test: `test_phone_fidelity::test_the_more_below_cue_is_a_quiet_fade_sitting_on_the_next_bar` (1440 and 390): pointer-events none, not a button, gradient, bottom edge within 1 px of the Next bar's top, height at most 40, `elementFromPoint` at its centre is not the cue, hidden at the end of the list.
- **Tray vs list** (`my-changes.js`, `fix-flow.css`): `.fix-rows` gets `padding-bottom: var(--tray-h)`; the tray publishes its own height (resize-observed, so it follows open/closed). Test: `test_fix_flow_ui::test_the_tray_never_hides_the_last_list_rows` (short window, real server): padding equals the tray height closed and open, last row clear of the tray when scrolled to the end. Mutation check: without the padding it fails.
- `tests/test_design_tokens.py`: deliberately allows exactly that one gradient in `phone-frame.css` (`PHONE_FADE`); `test_phone_fidelity` pins it to the `.phone-scroll-cue` rule and that exact token-only string. `--tray-h` is declared in `fix-flow.css` (`:root`), set at runtime on `<html>`.

## Exact test results

| Run | Command (all with `.venv/bin/python -m pytest -p no:cacheprovider`) | Result |
|---|---|---|
| A/B | `tests/test_signoff_consistency.py tests/test_slack_post.py tests/test_signoff.py` | 58 passed |
| Consistency test before the fix | `tests/test_signoff_consistency.py` | 3 failed (card listed 6 "checked by hand", expected 2) |
| Finish-line tests on the old `share.js`/`rounds.js` | `tests/test_signoff_finish_line.py` | 6 failed (mutation proof) |
| Finish-line tests on the new code | same | 6 passed |
| Focused set (the files you listed plus the new ones) | `test_signoff_ui test_signoff_real_server test_status_server test_workflow_e2e test_phone_fidelity test_fix_flow_ui test_a11y_sweep test_copy_banned_words test_demo_export test_copy_deck test_signoff_consistency test_signoff_finish_line` | **167 passed** (59.6 s) |
| First focused run after D (before the token test was updated) | 20 files | 281 passed, 2 failed (`test_design_tokens`: the gradient and `--tray-h`), fixed in `3e6746d` |
| Browser files | `-m 'not live' tests/test_*_ui.py tests/test_*e2e*.py test_phone_preview test_phone_first_workspace test_unified_workspace test_workspace_contracts test_home_page` | **262 passed** (112 s) |
| Everything else (no browser) | `-m 'not live' tests --ignore-glob='tests/test_*_ui.py' --ignore-glob='tests/test_*e2e*.py'` | **2438 passed**, 1 deselected (the live test) (258 s) |

Not run: nothing skipped except the `live` test. No test failed once and passed once.

## `site/data.js`

Regenerated (the payload gained `share.facts` for each sample). `python -m surveycoach.demo_export` twice: identical sha256 `b94b7bdcf0b327b4a087ca4b3b25ff41a06286bd1706425ffe1d4c3d88cb8f40`; `grep -c http site/data.js` is 0.

## Judgement calls and not done

- The change list is still built from decisions in the browser (not from `my_changes`), see C.
- The version timeline stays on Sign off: it is the only version switcher.
- `SC.renderChangeSheet` (rounds.js) is unused dead code; left alone (out of scope).
- The fix list drawer at 390 px also gets the tray padding (harmless blank space; the drawer sits over the tray).
- A stale screenshot `review/after/phase3/signoff-ready-1440.png` still shows the old contradictions; not regenerated (screenshots are uncommitted and `_phase3c_shots.py` now draws a coherent page).
- A card/post comparison after re-opening an item post sign-off (`changed_since`) is not tested; both read the live detail, so they agree by construction.
