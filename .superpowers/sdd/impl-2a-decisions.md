# Workstream 2A: decisions, one ordered queue, My changes, next item (backend)

Branch `feature/surveycoach-mvp`. Offline, synthetic fixtures, nothing under `site/` touched. Commits: `1f7966b` (decisions), `964e2dd` (queue, next item), `2f84f41` (My changes), then this report.
Every field below is real and tested (`tests/test_decision_model.py`, `test_queue.py`, `test_my_changes.py`). Example JSON comes from the synthetic concept fixture.

## 0. What the site workers must do (short)

- Read **`detail.queue`** for the fix list, "N of M done" and "Next item". Do not count anything yourself.
- Read **`detail.my_changes`** for the tray. Show `items`; the Copy all button copies `copy_all_text`; per-item Copy copies `copy_text`. **Delete the JS `SC.changeSheetText` for the tray**: Python is the single implementation (section 4).
- Close an item with `PUT .../decisions/{fingerprint}` using `pick` (Add to my changes), `done` (Mark done in RedJade) or `keep` + chip. After every PUT, refetch `GET /api/surveys/{id}/versions/{v}`: the PUT only returns the saved decision.
- `site/data.js` is stale (new `queue`, `my_changes`, extra item fields). Regenerate with `python -m surveycoach.demo_export`. Until then `tests/test_demo_export.py::test_committed_site_data_is_not_stale` and `tests/test_copy_deck.py::test_every_committed_demo_entry_has_current_canonical_projection` fail (expected, not a regression).

## 1. Decisions

`PUT /api/surveys/{id}/versions/{v}/decisions/{fingerprint}` (unchanged URL). `fingerprint` is a finding fingerprint, a curated `you-check:...` key, or the duration item `time:over-target:...`. For a grouped card, send one PUT per member (`item.fingerprints`); the card is handled when every member is.

Body (all fields optional except `action`; unknown fields are rejected):

```json
{ "action": "pick|done|original|keep|open",
  "picked_text": "only with pick; must be one of the finding's saved suggestions",
  "keep_reason": "intentional|owner_decided|not_applicable|other",
  "reason": "free text",
  "client_id": "tab id", "revision": 0, "manual_done": false }
```

| action | meaning | closes the item? | `handled_kind` |
|---|---|---|---|
| `pick` | Add to my changes (needs `picked_text`) | yes | `use` |
| `done` | Mark done in RedJade (author's word, **unverified until Check again**) | yes | `done` |
| `original` | the older "Mark done" the 1A UI sends; behaves exactly like `done` | yes | `done` |
| `keep` | Keep as is: needs a `keep_reason` chip **or** a non-blank `reason` | yes | `keep` |
| `open` | undo | no | null |

Rules, all returning 422 with a readable message:
- unknown `action` or unknown `keep_reason`: FastAPI's list error naming the allowed values (`"Input should be 'intentional', 'owner_decided', 'not_applicable' or 'other'"`).
- `keep_reason` on anything but `keep`: "keep_reason only applies when the action is keep".
- `keep` with neither chip nor text: "Keeping an item requires a reason: choose a reason or write a short note".
- a note next to a chip longer than **200** characters: "A note next to a reason is at most 200 characters". (A legacy keep with free text only keeps the old 10,000 limit, so old clients keep working.)
- `pick` without `picked_text`, or with text that is not a saved suggestion, or on a You check item: 422 as before. Unknown fingerprint: 404.
- `done` ignores any `picked_text` (stored as null). `done` and `keep` work on You check items.

Response (the saved decision):

```json
{ "action": "keep", "picked_text": null, "reason": "Priya signed off", "keep_reason": "owner_decided",
  "manual_done": false, "client_id": null, "revision": 0,
  "fingerprint": "you-check:required:d16f178d",
  "original": "Do you want Q1, Q2, Q3, Q5 and 3 more to be required? Check each one's setting in RedJade." }
```

Behaviour worth knowing:
- **Sanitised on read**: `reason` loses control, zero-width and text-direction-override characters (newlines and tabs stay); an unrecognised stored `keep_reason` is served as `"other"`. Markup is stored as typed and escaped by the share page; render with `textContent`.
- **Backward compatible**: rows stored before this work load byte-for-byte unchanged (no new keys are added on read). A stored legacy `keep` with a text reason still counts as handled.
- **`done` is never carried into the next version.** `keep`, `original` and `pick` still carry when the finding is still flagged. Rationale: "done" means "I fixed it"; the recheck is what verifies that, so the new version starts the item open (and puts it in `round_changes.fixed` if the check no longer flags it).
- **History is never rewritten.** The live `decisions` row holds the latest word; every save is also appended to the new `decision_events` table (a replayed `client_id`/`revision` adds nothing). Reads: `Repository.decision_history(survey_id, version, fingerprint=None)` (Python only, no HTTP endpoint yet). Stored snapshots and reviews are not touched by saving.
- Bug fixed on the way: a request with **no** `client_id` used to be treated as a replay of the previous one (so a second change was silently ignored). Only a request with the same non-empty `client_id` and an old `revision` is a replay now.
- The old browser code sends `original` for "Keep"/"Mark done" and `keep`+reason; both still work.
- `GET .../decisions` returns `{decisions: {fingerprint: decision}}` with these extra fields where present.
- Share page: "Still open" now uses the one `is_decided` rule (so `done` counts as handled); the kept list shows `Reason: Owner decided: Priya signed off` (chip label, then note). `change_sheet[].reason` carries that same text.

## 2. `detail.queue`: the ONE ordered list

Served on `GET /api/surveys/{id}` and `.../versions/{v}` (and in offline demo data via `enrich`). Built only from `overview.items`, which the tiles, cards, markers and verdict already use. It always exists; with no review it is empty.

```json
{
  "items": [ QueueEntry, ... ],
  "first_open_id": "53a57135b93d",
  "counts": { "done": 3, "total": 9, "open": 6, "unverified": 1,
              "by_kind": { "use": 1, "done": 1, "keep": 1 } }
}
```

`QueueEntry` (exactly these keys):

```json
{
  "id": "pattern-662ef374c125",
  "fingerprints": ["662ef374c125", "e6a178d38df9", "151304d10a33"],
  "kind": "finding",
  "state": "worth_improving",
  "open": false,
  "handled_kind": "use",
  "unverified": false,
  "keep_reason": null,
  "screen": 5, "page_id": "p4",
  "screens": [5, 7, 9], "pages": ["p4", "p6", "p8"],
  "title": "Missing \"Select all that apply\"",
  "location": "Q4, Q6 and Q8 · Screens 5, 7 and 9",
  "action_kind": "paste",
  "has_paste": true,
  "count": 3,
  "next_open_id": "53a57135b93d"
}
```

- `id` is the plan group id (equal to the fingerprint for a single finding, `pattern-<fp>` for a repeated block, `you-check:<theme>:<hash>` or `time:over-target:<hash>` for the others). `fingerprints` are what you PUT decisions on.
- `kind`: `finding | you_check | time`. `state`: `fix_before_launch | worth_improving | you_check`. (`looks_good` never appears: only things to act on are items.)
- **Order**: Fix before launch, then Worth improving, then You check; inside a state by first screen; items with no screen (whole survey) last; equal keys keep the plan order. Handled items **stay in the list** (render ticked), so M = `counts.total` and N = `counts.done`.
- `screen` / `page_id` = first affected screen (null for whole-survey items); `screens` / `pages` = all of them (a grouped card lists every screen).
- `action_kind`: `paste | steps | you_check` (You check and time items are always `you_check`). `has_paste` = the card has pasteable text (`action_kind == "paste"` and a suggestion or options exist).
- `open` = not handled. A grouped card is handled only when **every** member is.
- `handled_kind`: `use | done | keep | null`. For a mixed group it reports the weakest evidence: `done`, else `keep`, else `use`. `unverified` is true exactly when `handled_kind == "done"`: show "Marked done, not checked yet" until Check again. `keep_reason` is the first member's chip when kept, else null.
- **`next_open_id`**: the next entry **after this one in list order** that is open, else null. Never wraps. Works for handled entries too (a handled entry points to the next open item after it). `first_open_id` is the first open entry (null when everything is handled): use it for the starting position and for "all handled" (the completion moment).
- `counts.open + counts.done == counts.total`; `by_kind` sums to `done`; `unverified` counts handled entries flagged unverified.
- **Equality guarantees (property-tested, including the offline demo surveys)**: `counts.total == len(items) == len(overview.items)`; `{done,total} == overview.verdict.progress`; each verdict tile (`fix`, `improve`, `you_check`) equals the number of open entries in that state; grouped cards count once; verdict `ready_for_signoff` is reached when everything is closed by any mix of `use`/`done`/`keep`, with `counts.unverified > 0` telling you some of it is unverified.

`overview.items[]` gained the same fields (`handled_kind`, `unverified`, `keep_reason`, `action_kind`, `has_paste`, `page_id`, `screen`) so the card, tile and queue never use different data. Nothing was removed or renamed there.

## 3. `detail.my_changes`

```json
{
  "items": [ {
    "fingerprint": "662ef374c125", "headline": "Missing \"Select all that apply\"",
    "screen": 5, "page_id": "p4", "page_label": "Q4", "screen_label": "Q4 · Screen 5",
    "question_id": "why1", "question_label": "Q4",
    "field": "question_text",
    "field_location": "RedJade > Q4 > Question text",
    "before": "What about this tray has you saying 'Yes, please!'?",
    "after": "What about this tray has you saying 'Yes, please!'? Select all that apply.",
    "edit_kind": "rewrite",
    "copy_text": "RedJade > Q4 > Question text\nBefore: What about this tray has you saying 'Yes, please!'?\nAfter: What about this tray has you saying 'Yes, please!'? Select all that apply."
  } ],
  "count": 1,
  "copy_all_text": "<every item's copy_text, joined with a blank line>"
}
```

- Contains only `pick` decisions with text. Never kept, done, open, previews (a suggestion nobody accepted) or absorbed child findings. Stale picks (suggestion no longer offered) are already turned into `open` upstream.
- **Order (RedJade order)**: screen order; within a screen, screen text first, then each question in survey order; within a question: question text, help text, answers 1..n (in list order), scale labels, then "new answer". A change that cannot be placed lists last with `page_id`/`screen` null, `before: null`, `field_location: "RedJade > Survey overall"`.
- `field`: `screen_text | question_text | help_text | answer | scale_label | new_answer`. `before` is null for an added answer and for an unplaceable change; `copy_text` then says `Before: (nothing: this adds a new answer)` or `Before: (not found in the saved survey)`.
- `field_location` is the finding's own (`RedJade > Q1 > Question text`) or computed from the snapshot by the same rule. `page_label` is the screen name (`Q4`, `Welcome`, `Thank you`); `question_label` is null for screen-level text.
- Grouped cards give **one change per member** (each is a separate edit in RedJade, with its own location). The queue still counts the card once.
- `count` is the number for "My changes · 3". With 0, disable "With my changes".
- Block format of `copy_text` is exactly three lines: location, `Before: ...`, `After: ...`. `copy_all_text` is `"\n\n".join(copy_text)`; empty string at 0.

## 4. Which change-sheet implementation I chose

**Python, one place** (`surveycoach/server/my_changes.py`). It is built on `rounds.decided_findings`, the same walk the existing Python `change_sheet` uses (`detail.change_sheet` and `/change-sheet` are unchanged in shape and still used by the share page; they also list kept items). The field rule that decides "which field of the question holds this text" had three copies (`present.field_location`, `change_sheet` target, JS `issueTarget`/`changeSheetText`); the two Python ones now both call `rounds.field_part`, and `field_location` moved from `present.py` to `rounds.py` next to it. Two small behaviour changes follow from that: a change sheet line on help text is now targeted `Help text` (was `Question`), and a scale label from the labels list is `Scale label`. **Still two JS copies in `site/` (`SC.changeSheetText` in `rounds.js`, `SC.issueTarget` in `issues.js`): 2B/2C should drop them in favour of `my_changes` and the finding's `field_location`.**

## 5. Judgement calls (please sanity check)

1. **`keep` needs a chip or a note.** The brief says the chip is "optional", but the standing rule (1A verdict contract) is that a kept item needs a stated reason. A chip alone is enough, so the UI can offer chips with an optional note and never block on typing; a bare `keep` is a 422. Say if you want a truly reason-less keep (one-line change in `status.handled_kind` and `decisions.coherent_decision`).
2. **`original` is an alias of `done`** for counting and for `handled_kind`. It is the 1A "Mark done" and the old UI sends it for plain Keep too. `done` is not carried into the next round; `original` still is (existing behaviour, existing tests). The UI should move to `done`.
3. **Mixed group** reports `done` > `keep` > `use` (weakest evidence).
4. **Where the list lives**: top-level `detail.queue` rather than inside `detail.plan` (the plan is a finding-only structure built before the overview; the queue needs You check items and the time item too). `detail.plan` is unchanged.
5. **Handled items stay in the queue** (with `open: false`) so the totals are derivable from the one list. The spec's "list of open items" is `items.filter(e => e.open)`.
6. **Decision history** is an append-only `decision_events` table plus a Python read method, no endpoint yet (YAGNI until Sign off needs "who ticked it and when"; there is no user identity yet either).
7. `queue` module is named `surveycoach/fix_queue.py` to avoid shadowing the stdlib `queue`.

## 6. Tests

Focused run (not the whole suite): `test_status_server, test_grouping, test_status_consistency, test_workspace_decisions, test_present*, test_review*, test_enrich_contract, test_committee_rounds, test_summary_download, test_plan, test_status, test_final_projection, test_signals, test_action_contract, test_you_check, test_verdict, test_branch_paths, test_answer_additions, test_reading_choice_fixes, test_root_cause_invariants` plus the three new files (`test_decision_model` 22, `test_queue` 19, `test_my_changes` 11).
**Green except the two stale-demo-data tests named in section 0** (they need `python -m surveycoach.demo_export`, which writes `site/data.js`; I did not touch `site/`). I did not run the browser (`test_site_*`) suites.
(There is no `tests/test_decisions*.py`; `test_workspace_decisions.py` is the existing decisions suite and passes unchanged.)
Mutation checks (broke the code on purpose, tests went red, code restored): a card closing when only some members are handled (1 test red); `next_open_id` pointing at handled entries (4 red).

Files: new `surveycoach/server/decisions.py`, `surveycoach/server/my_changes.py`, `surveycoach/fix_queue.py`; edited `status.py`, `items.py`, `server/{__init__,repository,rounds,present,report}.py`, `server/README.md`. All under 600 lines (largest: `rounds.py`, 390).
No push, no delegation, no live calls. Unrelated working-tree changes (`site/model.js`, `review/` assets, staged `progress.md`) were left alone.
