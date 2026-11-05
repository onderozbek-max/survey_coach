# Workstream 3A: journey, reward, sign-off, Slack post, version delta (backend)

Branch `feature/surveycoach-mvp`. Offline, synthetic fixtures, nothing under `site/` touched, `site/data.js` not regenerated.
Commits: `cf1061a` journey, `4befa0f` version delta, `167863f` reward, `b16a57f` sign-off, `1556d8c` Slack/summary/developer flag, `3599049` one length target, then this report.
Every field below is real and tested (`tests/test_journey.py`, `test_version_delta.py`, `test_reward.py`, `test_signoff.py`, `test_slack_post.py`; shared helper `tests/review_helpers.py`). Example values come from the synthetic concept fixture.

## 0. What the site workers must do (short)

| Need | Read / call |
|---|---|
| Journey strip, sections, running marker | `detail.presentation.journey` + `detail.presentation.journey_sections` (section 1). Replaces `overview.energy` for the strip. |
| "Looks like a concept test, confirm" | `detail.survey_type_detection` (`label`, `confidence`, `reasons`, `confirmed`). Confirm with the existing `PATCH /api/surveys/{id}` `{survey_type}`. |
| Reward question (No / Yes + text) | `detail.reward`; save with `PUT /api/surveys/{id}/reward` (section 2). |
| Since last version card | `detail.version_delta` (null on v1: hide the card, D16) (section 5). |
| Sign off button and state | `detail.signoff`; `POST /api/surveys/{id}/versions/{v}/signoff` (section 3). |
| Copy Slack post, Download summary | `detail.share.slack_post` (copy it as is), `detail.share.summary_url` (section 4). |
| Hide the raw snapshot import | `GET /api/metadata` -> `developer`, or `window.SURVEYCOACH_DEVELOPER` (section 4.3). |

After any PUT/POST refetch `GET /api/surveys/{id}/versions/{v}`: that is the single source of truth. `site/data.js` is stale (new `reward`, `signoff`, `share`, `version_delta`, `presentation.journey`); regenerate with `python -m surveycoach.demo_export` (writes `site/data.js`). The offline demo data from `enrich` has `presentation.journey` but not `reward`/`signoff`/`share`/`version_delta` (those are added by the repository).

## 1. Journey (brief 4.4, D11)

`detail.presentation.journey` is a list with exactly one segment per screen; `journey_sections` is the ordered section list.
Both exist on every detail, even before a review (then every `state` is null and `n_items` 0).

```json
{ "index": 3, "screen": 4, "page_id": "p3", "label": "Q3", "kind": "stimulus",
  "seconds": 12.5, "running": 35.2,
  "section": "s4", "section_label": "Idea 1",
  "state": "you_check", "n_items": 2, "n_done": 0,
  "tooltip": "Q3 · ~13 sec · 2 things to check" }
```
```json
{ "id": "s2", "label": "Warm-up", "kind": "warmup", "start_screen": 2, "end_screen": 2, "running": 5.4, "seconds": 9.0 }
```
- `kind` of a segment: `welcome | stimulus | question | info | ending`. `stimulus` = a question screen that carries its own concept copy (D1).
- **One width encoding**: `seconds`. `running` is the second this screen starts (use it for the phone's timeline marker: position = `running / total`; the marker should use the same strip, not the blue-to-red bar).
- **The segments add up exactly**: `round(sum(seconds), 1) == overview.energy.total_seconds` and `round(total / 60, 1) == overview.verdict.time.minutes` (property-tested on the concept fixture and every offline demo survey). To make that exact, a segment's `seconds` is the difference of the timing model's running totals, so it can differ by at most 0.1 s from `overview.energy.screens[].seconds`. Use the journey for widths and tooltips, never mix the two.
- `state` = worst four-state state among the **open** items on that screen (same rule as `energy.screens[].state`; property-tested equal). `n_items` = open items on the screen, `n_done` = handled ones. A grouped fix card counts once on each screen it touches. Whole-survey items are on no segment.
- `tooltip` is server text: `"<label> · ~<N> sec · <parts>"`. Parts, worst first: `1 thing to fix`, `2 things to improve`, `1 thing to check`, joined with `, `. When everything on the screen is handled: `all handled`. No parts when nothing is on the screen. Seconds read `~N sec` under 90 s, then `~N min`.
- Click target: jump to `page_id`.

Sections (`kind`: `welcome | warmup | idea | repeat | wrapup | ending | screens`), deterministic, **structure only**:

| Rule | Label |
|---|---|
| welcome screen(s) | `Welcome` |
| ending screen(s) (thank-you, screen-out, last screen) | `Thanks` |
| an info screen is a boundary; neutral runs next to each other merge | `Screens 2-5` / `Screen 5` (ASCII hyphen) |
| question screens before the first concept screen, only when the concept structure is understood (same rule as the verdict story's "warm-up") | `Warm-up` |
| a lone concept block that is the first one in its run | `The idea` |
| two or more consecutive blocks of the same shape (a concept screen plus the follow-ups up to the next concept screen, compared by question kinds and option counts); a third block confirms a longer last block, whose extra screens become the wrap-up | `Idea 1`, `Idea 2`, ... |
| the screens after the confirmed last repeated block | `Wrap-up` |
| anything else, including two unlike concepts, two repeats with a long last block, no concept at all | neutral `Screens a-b` |

The concept fixture gives `Welcome · Warm-up · The idea · Idea 1 · Idea 2 · Idea 3 · Wrap-up · Thanks` (screens 1 / 2 / 3 / 4-5 / 6-7 / 8-9 / 10-12 / 13). No name is ever taken from survey wording, so `Tray` is not used (the word "Idea" is the generic one, matching the verdict story's "similar ideas"). Negative controls are in the tests (no concept -> neutral; unlike concepts -> neutral; two blocks with a long last -> neutral).

`journey_sections[]`: `id, label, kind, start_screen, end_screen` (1-based, inclusive, contiguous, they tile all screens), `running` (start second), `seconds`.

## 2. Reward and survey type (brief 4.8)

Stored per **survey** (every version reads the same answer; a new column on `surveys`, existing databases migrate on open). It is outside the snapshot, so it never changes a content hash.

`detail.reward` (always present; also on every Home item as `reward`):
```json
{ "has_reward": null, "text": "" }
```
`PUT /api/surveys/{id}/reward` body `{ "has_reward": true|false|null, "text": "<=120 chars" }` -> 200
```json
{ "id": "…", "survey_id": "…", "reward": { "has_reward": true, "text": "Earn 50 points" } }
```
- `has_reward` is **required** and strictly boolean or null (`"yes"`, `1`, missing -> 422). `null` puts the question back to unanswered.
- `text` is sanitised (control, zero-width and direction-override characters removed, whitespace and newlines folded to single spaces), at most **120** characters after that, and only allowed with `has_reward: true` (text with `false`/`null` -> 422). Unknown fields -> 422. Unknown survey -> 404. Markup is stored as typed; render with `textContent`.
- **How it steers the checks** (the check itself reads it, so score, verdict, You check list and the queue all agree; `ReviewContext.reward`, `run_review(..., reward=)`, `project_review(..., reward)`):

| Answer | Check 1.4 and the welcome finding |
|---|---|
| `null` | unchanged: finding "Welcome doesn't mention a reward", a You check: "If members get a reward, is the exact reward in the welcome text?" |
| `false` | no reward half at all: no finding, no nagging, full credit for that half. A missing time still produces its own finding, without reward wording. |
| `true` | the only check is that the welcome mentions it (any reward wording, or the owner's own words appear in the welcome). If not: a You check "Members get a reward (<text>): does the welcome text mention it?" (or "...say what it is?" without text). |

  Changing the answer changes that finding's fingerprint/existence, so a decision made on the old one is dropped by the existing "decision follows its evidence" rule. I did not find any other reward wording in the checks (the AI judge prompt only forbids inventing reward terms).
- **Survey type.** `detail.survey_type_detection` is now `{type, confidence (0..1), label: "low"|"medium"|"high", reasons[], confirmed: bool}`. `confirmed` equals `survey_type_chosen` (true only after the user sets a type; auto-detection never confirms). Copy: "Looks like a **concept test**" when `confirmed` is false, with the label; confirm by `PATCH /api/surveys/{id}` `{"survey_type": "services_concept"}`. It is also on every Home item.
- **One length target** (bug fixed): the verdict used the confirmed type, else a medium/high detection, but check 2.1 was judging by the stored type. A concept test stored as a product test (5 min) at 5.7 minutes got a 2.1 finding while the verdict said the 6-10 minute target was met. Every check now uses the same type as the verdict (`display_type`). `verdict.time.type_source` says which: `confirmed | detected | default`.

## 3. Sign-off (brief 4.7)

`POST /api/surveys/{id}/versions/{v}/signoff` body `{ "name": "Priya N", "acknowledge_open": false }` -> **201** with the sign-off state (same object as `detail.signoff`).
- `name`: 1-80 characters after sanitising (control, zero-width and direction-override characters removed, newlines/whitespace folded). Empty, too long, not text -> 422. `acknowledge_open` is strictly boolean. **Unknown fields are rejected, so a client-sent `signed_at` or `version` is a 422**: the timestamp is the server's clock, UTC, `YYYY-MM-DDTHH:MM:SSZ`.
- **Accepted only when** `overview.verdict.kind == "ready_for_signoff"`, or `acknowledge_open: true`. Otherwise 422: `"This survey is not ready for sign-off: 3 items are still open. Finish them, or sign off with them open."` With no finished review there is no verdict: 422 `"There is nothing to sign off yet: ..."`, even with `acknowledge_open`. Unknown survey or version: 404.
- **When open items are acknowledged** the record stores `acknowledged_open: true` and every open item verbatim (`open_items`) with the counts at that moment. Never hidden, never rewritten. If nothing is open, `acknowledged_open` is false even when the flag was sent.
- **Storage**: new table `signoffs`, append-only (SQL triggers abort UPDATE and DELETE). Signing the same version again appends; the latest wins.
- **No accounts exist**: `who` in the You check list is the signer's name (they vouch for the list), and `at` is the time of that item's latest decision (the `decision_events` log, same clock). Open items have `who`/`at` null. An item closed in an earlier session shows its original time.

`detail.signoff` (always present):
```json
{ "signed": true, "version": 1, "signed_off_by": "Priya N", "signed_off_at": "2026-11-05T19:48:26Z",
  "changed_since": false,
  "record": {
    "name": "Priya N", "signed_at": "2026-11-05T19:48:26Z", "version": 1,
    "verdict_kind": "almost_ready",
    "headline": "Almost ready: 1 quick improvement and 6 things to check yourself",
    "counts": { "fix": 0, "improve": 1, "you_check": 6, "done": 2, "total": 9, "unverified": 1 },
    "acknowledged_open": true,
    "open_items": [ { "id": "ac04f1cda781", "state": "you_check", "headline": "Welcome doesn't mention a reward", "location": "Welcome · Screen 1" } ],
    "you_check": [
      { "id": "images", "fingerprint": "you-check:images:51dd590f", "title": "Images load on a phone", "where": "Screen 13",
        "status": "done", "reason": null, "who": "Priya N", "at": "2026-11-05T19:48:26Z" },
      { "id": "display_logic", "fingerprint": "you-check:display_logic:f9864b32", "title": "Questions that follow an earlier answer",
        "where": "Screens 5, 7 and 9", "status": "kept", "reason": "Owner decided: Checked on my phone",
        "who": "Priya N", "at": "2026-11-05T19:48:26Z" },
      { "id": "randomization", "fingerprint": "you-check:randomization:d152303b", "title": "Ideas shown in a random order",
        "where": "Screens 4, 6 and 8", "status": "open", "reason": null, "who": null, "at": null } ] },
  "history": [ { "version": 1, "name": "Priya N", "signed_at": "2026-11-05T19:48:26Z",
                 "verdict_kind": "almost_ready", "acknowledged_open": true, "latest": true } ] }
```
(`open_items` and `you_check` shortened here; the real lists are complete.) Unsigned: `signed: false`, `signed_off_by/at: null`, `record: null`, `changed_since: false`.
- `you_check[].status`: `done | kept | open`.
- `changed_since` is true when the current counts differ from the recorded ones (someone reopened or closed items after signing). Show "Signed off by Priya on …, changed since" rather than hiding the record.
- **A new version starts unsigned**: `GET .../versions/2` has `signed: false`; `history` lists every record of the survey across versions (oldest first; `latest` marks the winner per version), so the page can say "v1 was signed off by Priya N; v2 has not been signed yet". The old record is untouched and still the state of v1.
- Sign-off does **not** verify anything: items marked "done" are still the author's word (`counts.unverified`).

## 4. Slack post, summary, developer flag

### 4.1 `detail.share`
```json
{ "slack_post": "Survey review: Sunrise Skillet Concept Test (v1)\nVerdict: Almost ready: 1 quick improvement and 6 things to check yourself · ~3½ min\nKept on purpose: 1 (Screens 5, 7 and 9: Questions that follow an earlier answer – Owner decided: Checked on my phone)\nChecked by hand: Images load on a phone\nLink: https://app.redjade.net/s/sunrise",
  "link": "https://app.redjade.net/s/sunrise",
  "summary_url": "/api/surveys/<id>/versions/1/summary?download=true" }
```
`slack_post` is `null` until a check has finished; disable the button then. Copy it verbatim.

Convention (the brief's), built **only** from stored data:
1. `Survey review: <name> (v<N>)`
2. `Verdict: <verdict headline> · ~<time> min` (nearest half minute; ` (varies by route)` appended when branching makes the total uncertain)
3. `Fixed since v<N-1>: <count> (<Q>: <headline>; ...)` joined with ` · ` to `Kept on purpose: <count> (<Q>: <headline> – <reason>; ...)`. The fixed part exists only on v2+ and comes from `version_delta.fixed`. It says "since v<previous>" (the comparison is always with the direct previous version), not literally "v1" on v3. Kept comes from decisions with a stored reason (`Owner decided: …`). Lists are cut to 3, then `; +N more`.
4. `Checked by hand: <You check titles marked done>` (kept You check items are listed under Kept, because "kept" does not say it was checked).
5. `Link: <origin + path>`.
Lines with nothing to say are omitted (never "none").

Safety (tested): all user/vendor text is folded to one line (a reason cannot add or forge a line), `&`, `<`, `>` become entities, backticks become `'`, `@here/@channel/@everyone` get a zero-width break; every URL anywhere in the text (title, reason, link) is cut to origin + path, so `?token=…`, `#access=…`, credentials and queries never appear. Unusable links (`javascript:`, bad port, no host) are dropped.

### 4.2 HTML summary (the download)
`GET /api/surveys/{id}/versions/{v}/summary?download=true` (existing route and filename pattern) now starts with a **Review summary** card: survey name, version, link (plain text, origin + path, never an `<a>`), verdict, open counts, time, checked time, sign-off line ("Signed off by … on …, with N open item(s) acknowledged. Changed since." or "Not signed off yet"), "Checked by hand" list with status, who and when, and "Fixed since vN" when there is a delta. Self-contained (inline CSS; tested: no `<script>`, `<link>`, `<img>`, `<iframe>`, `src=`, `href=`, `@import`, `url(`), everything escaped. The on-screen `/summary` carries the same card. The existing sections (member experience, changes chosen, kept on purpose, still open, what we checked) are unchanged.

### 4.3 Developer flag
`create_app(db, developer=True)`, env `SURVEYCOACH_DEVELOPER=1`, or `python -m surveycoach.server --developer`. Effects: `GET /api/metadata` gets `developer: bool`; `/environment.js` adds `window.SURVEYCOACH_DEVELOPER = true;` only when on. **The import API (`POST /api/surveys`, `/recheck`) is unchanged and not gated**: dozens of tests and tools use it, so the flag only tells the page whether to offer it. 3B/3C: show "Advanced · local snapshot import" (`site/review.html`) only when the flag is on, and move the "We open your test link like a member would…" wording next to the link field (a UI copy change).

## 5. Version delta (brief 4.6, D16)

`detail.version_delta`: **null on v1** (and whenever there is no previous round). On v2+:
```json
{ "from_version": 1, "to_version": 2,
  "counts": { "fixed": 4, "still": 1, "new": 0, "uncertain": 1 },
  "summary": "4 fixed · 1 still open · 0 new · 1 couldn't compare",
  "caveat": "Fixed = no longer flagged by our checks.",
  "fixed": [ { "fingerprint": "…", "criterion_id": "3.1", "headline": "Reading level is high", "location": "Q1 · Screen 2",
               "resolution": "No longer flagged", "before": "Which of these apply?", "after": "Pick all that apply.", "by_rewrite": false } ],
  "still": [ { "fingerprint": "…", "criterion_id": "…", "headline": "…", "location": "…", "resolution": "Still flagged" } ],
  "new": [ … ], "uncertain": [ { …, "resolution": "Not verified: changed context, missing screen, ambiguous match or unchecked criterion" } ] }
```
- Built from the existing `compare_rounds` buckets untouched: counts equal the bucket lengths by construction (property-tested), **`uncertain` is never dropped**, and a disappeared finding is only "no longer flagged by our checks", never proof (use `caveat`; show "couldn't compare" as the fourth number).
- `before`/`after` exist only on fixed items: stored wording, whitespace-folded, at most 160 characters with an ellipsis; either can be null (an added answer has no `before`; an unplaceable change has no `after`). `by_rewrite` is true when the item was fixed with the author's own picked rewrite ("Fixed with your rewrite"), the only case with real evidence.
- The full `round_changes` (with whole findings) is unchanged for existing consumers.

## 6. Judgement calls (please sanity check)

1. **`Idea 1/2/3`, not `Tray`.** No domain word is invented. `Warm-up` is allowed only when the concept structure was understood, the same rule the verdict story uses, so the strip and the story never disagree.
2. **Pins and `n_items` count open items only**, like the existing markers. A screen whose items are all handled shows no pin and the tooltip says `all handled`.
3. **Segment seconds are differences of running totals** so the sum is exact (see section 1). The cost is up to 0.1 s of drift from `energy.screens[].seconds`.
4. **`who` = the signer.** There are no accounts. If you want honest `who: null` instead, it is one line in `signoff._you_check`.
5. **Sign-off is per version, not per survey**, and a closed-then-reopened item sets `changed_since` instead of voiding the record.
6. **Developer flag is advertise-only** (section 4.3). Gating the API would break the import-based tests and tools.
7. **Reward `false` gives full credit to the reward half of 1.4** rather than making it not applicable (no scoring-weight change). Say if you would rather it left the denominator.
8. **Same type for every check (section 2)** changes which findings an unconfirmed, auto-detected concept test shows (it no longer gets a product-test length finding). That is the intended behaviour; no existing test depended on the old mismatch.
9. **`snapshot.source_url` is still served raw** in `detail.snapshot` (existing behaviour, local UI only). The Slack post and the HTML never use it unscrubbed; the UI should show `detail.share.link`, not `snapshot.source_url`.

## 7. Tests

- New: `test_journey` (14), `test_version_delta` (6), `test_reward` (26), `test_signoff` (27), `test_slack_post` (28). Shared helper `tests/review_helpers.py` (`encoded`, `save_review`).
- Focused run, all green: `test_status_server, test_queue, test_my_changes, test_decision_model, test_status_consistency, test_committee_rounds, test_timing, test_timing_welcome_fixes, test_present, test_workspace_decisions, test_workspace_contracts, test_summary_download, test_final_projection, test_server_api, test_server_contracts, test_server_security, test_server_jobs, test_server_naming, test_survey_style, test_enrich_contract, test_mvp_input, test_mvp_ask, test_loading_progress, test_labels, test_survey_type_detection, test_recommendation_quality, test_checks_structure, test_committee_trust_engine, test_actionable_findings, test_check_actions, test_action_contract` plus the five new files. No older test needed changing. I did not run the whole suite or the browser (`test_site_*`, `test_share_ui`, `test_share_state_ui`, `test_home_page`) suites.
- Still red until 3B/3C regenerate it (expected, not a regression): `tests/test_demo_export.py::test_committed_site_data_is_not_stale` and `tests/test_copy_deck.py::test_every_committed_demo_entry_has_current_canonical_projection` (committed `site/data.js` predates the 1A/2A/3A payloads).
- Mutation spot checks while writing: the journey tests fail if the wrap-up truncation rule is loosened (two-block negative control) and the Slack tests fail if the link is not stripped.

## 8. Files

New: `surveycoach/journey.py`, `reward.py`, `safe_text.py`, `server/version_delta.py`, `server/signoff.py`, `server/slack.py`, `server/review_card.py`, five test files, `tests/review_helpers.py`.
Edited: `checks/registry.py` (context carries `reward`), `checks/structure.py` (check 1.4, `REWARD_WORDS` moved to `reward.py`), `review.py`, `server/{__init__,__main__,repository,present,rounds,decisions,report}.py`, `server/README.md`. `clean_text` moved to `safe_text.py` and is still importable from `server/decisions.py`. All files are under 600 lines (largest: `repository.py` 408).
No push, no delegation, no live calls. Unrelated working-tree files (`review/` assets, staged `progress.md`) untouched.
