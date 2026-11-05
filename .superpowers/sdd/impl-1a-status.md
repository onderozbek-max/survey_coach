# Workstream 1A: backend status model and verdict payload

Branch `feature/surveycoach-mvp`. Offline, synthetic fixtures only, no `site/` or reader edits.
This file is the contract for worker 1B (the UI): every field name below is real and tested.

## 1. What shipped

| Area | Where |
|---|---|
| The one state table (4 states, labels, worst-of, decided, duration, signal rule) | `surveycoach/status.py` (80 lines) |
| Curated "You check" items (6 themes, generated only from evidence) | `surveycoach/you_check.py` (182) |
| One item list shared by tiles, cards, markers, verdict | `surveycoach/items.py` (~90) |
| Verdict, story, time, headline | `surveycoach/verdict.py` (115) |
| Signals/cards, screen markers, methodology | `surveycoach/signals.py` (~230, `_ratio_state`/`_signal_state` removed) |
| Finding contract fields + fallback + validator + banned words | `surveycoach/findings.py`, `surveycoach/recommendations.py` |
| Extras (You check + duration) shared by overview and decisions API | `surveycoach/server/extras.py` |
| Payload assembly, decisions, Home card, share | `server/present.py`, `rounds.py`, `plan.py`, `repository.py`, `report.py` |

New tests: `test_status`, `test_you_check`, `test_verdict`, `test_action_contract`, `test_status_server`,
`test_status_consistency` (the property test over all fixtures), `concept_fixture.py` (synthetic concept test),
`test_signals` rewritten. All files are under 600 lines.

## 2. The state table (`surveycoach/status.py`)

States, worst first: `fix_before_launch` "Fix before launch" / `worth_improving` "Worth improving" /
`you_check` "You check" / `looks_good` "Looks good". A card with no state has `state: null` and
`label: "Not checked automatically"`.

| Source | State |
|---|---|
| finding severity `must_fix` (even if its action is a human check) | `fix_before_launch` |
| finding whose only action is human judgement (B7 unverified image, 7.2 auto, 6.2 "N answer choices; review the phone layout") | `you_check` |
| finding `worth_improving` with a concrete fix | `worth_improving` |
| curated You check item | `you_check` |
| over-target duration (one decidable item, kind `time`) | `worth_improving`, never a fix |
| unassessed and not on the curated list | **not a state**: `methodology.not_checked_automatically` |

Card rule: state is the worst state among its **open** items. `looks_good` only when nothing is open,
at least 2 checks were assessed and passed, they cover at least half of the applicable checks, and no
partial credit is left unexplained (explained = a visible, non-absorbed finding). Otherwise `null`.
So a card whose summary names a problem can never be positive, and 1-of-7 assessed can never be Looks good.
Time follows the same rule (open items first; a within-target duration, or an item the user has dealt
with, gives `looks_good`; unknown duration stays `null`).

## 3. Payload shape

Field names and types are exact. Example *values* come from the synthetic concept-test fixture (`tests/concept_fixture.py`) and are illustrative.

All of this is on `GET /api/surveys/{id}` (`detail`). Home reuses the same objects (section 3.7).

### 3.1 `detail.overview`

```
overview: {
  headline: str,                 // == verdict.headline ("Not checked yet" when verdict is null)
  subline: str,                  // == verdict.story ("" when null)
  verdict: Verdict | null,       // null only when nothing was assessed and nothing was raised
  signals: Signal[6],            // order: time, clarity, honest, energy, tone, phone
  items: Item[],                 // THE list; every count below is derived from it
  you_check: YouCheck[],         // the curated items (also present inside items, kind "you_check")
  strengths: [...],              // unchanged
  energy: { total_seconds, path_uncertain, heaviest, screens: Screen[] }   // Screen.state is new
}
```
`overview.not_checked_automatically` no longer exists on the overview; it moved to `detail.methodology`.

### 3.2 `Verdict` (identical object in `overview.verdict` and `presentation.verdict`)

```json
{
  "kind": "almost_ready",
  "headline": "Almost ready: 2 quick improvements and 7 things to check yourself",
  "story": "Members get a welcome, answer 1 warm-up question, see the idea, react to 3 similar ideas, then wrap up with 3 questions.",
  "tiles": { "fix": 0, "improve": 2, "you_check": 7 },
  "time": {
    "minutes": 3.5, "label": "About 3½ minutes",
    "summary": "About 3½ minutes. Concept tests usually take 6–10 minutes.",
    "target_low": 6.0, "target_high": 10.0, "state": "looks_good",
    "survey_type": "services_concept", "type_source": "detected", "path_uncertain": false
  },
  "progress": { "done": 0, "total": 9 }
}
```
- `kind`: `"fix_before_launch" | "almost_ready" | "ready_for_signoff"`.
- Headlines: `"N thing(s) to fix before launch"`, `"Almost ready: N quick improvement(s) and M thing(s) to check yourself"` (parts omitted when zero), `"Ready for sign-off"`. Always computed from open items.
- `story`: deterministic, built only from detected structure (welcome, warm-up, concept/stimulus, repeated blocks, wrap-up). Whatever is not detected is omitted; `""` if nothing at all. Never contains names or praise.
- `time.state`: `"looks_good" | "worth_improving" | null` (null when branching makes the total uncertain). `type_source`: `"confirmed" | "detected" | "default"`; the target uses the confirmed type, else a medium/high-confidence detection, else the stored type.
- `progress`: items closed vs all items (for a "3 of 9 done" bar).

**Rule (also in the `verdict.py` docstring and tests).** An item is open until an explicit decision closes it
(`pick`, `original`, or `keep` with a non-blank reason).
- any open `fix_before_launch` item -> `fix_before_launch`
- else any open `worth_improving` or `you_check` item -> `almost_ready`
- else -> `ready_for_signoff`

So Ready means: no open fix, every curated You check done or kept, and every improvement applied or kept on purpose.

### 3.3 `Signal` (one per card)

```json
{
  "id": "phone", "name": "Phone comfort",
  "state": "you_check", "label": "You check",
  "summary": "Q4 · Screen 5: 10 answer choices; review the phone layout",
  "items": [ { "id": "94afa1ce0617", "kind": "finding", "state": "you_check", "open": true, "headline": "10 answer choices; review the phone layout" } ],
  "lead": { "headline": "10 answer choices; review the phone layout", "location": "Q4 · Screen 5" },
  "navigation": { "fingerprints": ["94afa1ce0617"], "pages": ["p3"] },
  "findings": ["94afa1ce0617"],
  "pages": ["p3"],
  "methodology": { "coverage": { "checked": 2, "total": 8, "missing": ["7.1"], "not_applicable": [] }, "details": ["..."] }
}
```
- `state` may be `null`; then `label` is `"Not checked automatically"` and `summary` is `"Not checked automatically."`. When `looks_good`, `summary` is `"Nothing to fix here."`.
- `summary` leads with the first most-urgent **open** item (`lead`); the Time card's summary is always the duration sentence.
- `items[]` lists every item in the card (open and done); render a done one as ticked.
- Old top-level `coverage` and `details` moved under `methodology`. Do not show `methodology` on the card.
- Welcome time/reward copy (criterion 1.4) lives in **Tone**, not Time (D7). Time contains only duration (2.1, B5).

### 3.4 `Item` (`overview.items[]`)

```json
{
  "id": "you-check:display_logic:f9864b32",
  "kind": "you_check",
  "state": "you_check", "open": true, "decided": false,
  "headline": "Questions that follow an earlier answer",
  "location": "Screens 5, 7 and 9",
  "signal": "energy",
  "criterion_id": null,
  "instruction": "…",
  "fingerprints": ["you-check:display_logic:f9864b32"],
  "count": 1,
  "pages": ["p4", "p6", "p8"], "screens": [5, 7, 9]
}
```
- `kind`: `"finding" | "you_check" | "time"`. `instruction` exists only for non-findings.
- For `kind: "finding"`, `id` is the plan group id (identical findings across a repeated block are ONE item, `count > 1`), `fingerprints` are the members, `criterion_id` is set.
- Absorbed findings are evidence, never items.
- Tiles, cards, markers and the verdict all count these same items once (property-tested).

### 3.5 `YouCheck` (`overview.you_check[]`, max 6, theme order)

```json
{
  "id": "images", "fingerprint": "you-check:images:51dd590f",
  "theme": "Images and media", "title": "Images load on a phone",
  "instruction": "Open screen 13 on your phone: does the image show up?",
  "where": "Screen 13", "pages": ["p12"], "screens": [13], "questions": [],
  "signal": "phone", "covers": ["7.1","7.2","7.3","7.5","7.6","B7"],
  "kind": "you_check", "state": "you_check", "open": true, "decided": false
}
```
Ids: `images`, `display_logic`, `randomization`, `required`, `other_text`, `timed_run`. Each appears only with evidence
(media present; wording that assumes an earlier answer; repeated concept screens; requiredness unknown or verified optional on
key questions; an "Other/Something else" option without a confirmed text box; branching or a stated time promise). The curated
images check stands down when a B7 finding already asks about those images, so images count once. Fingerprint is
`you-check:<id>:<8-hex hash of the evidence>`, so changed evidence gives a fresh, open item.

Closing one, **no new endpoint** (verified offline over HTTP):
`PUT /api/surveys/{id}/versions/{v}/decisions/{fingerprint}` with `{"action":"original"}` (Mark done) or
`{"action":"keep","reason":"Checked on my phone"}` (Keep). `pick` with text is rejected (ValueError, 422).
An unknown `you-check:` fingerprint is 404. The same applies to the over-target duration item (`time:over-target:<hash>`).

### 3.6 `energy.screens[]` (per-screen marker)

`{ "page_id","screen","name","seconds","zone","state" }` where `state` is the worst **open** item state on that screen, or `null`.

### 3.7 Everything else

```
detail.presentation = {
  verdict: Verdict | null,        // was a string ("N must-fix issues")
  launch_approval: false,         // unchanged
  scope: { review_available, checked_count, total_count, unchecked_checks, unchecked_paths, summary }   // unchanged
}
```
`open_blockers` and `acknowledged_risks` were removed from `presentation` (use `verdict.tiles.fix`).

```
detail.methodology = {
  quality: { score, provisional, coverage_percent, dimensions, blockers, basis, ... },   // was detail.quality
  not_checked_automatically: [ { id, title, signal } ]    // NOT a state, never blocks sign-off
}
```

Home list item (`GET /api/surveys`) is now:
`{ id, title, version, created_at, job, survey_type..., signals, verdict, tiles, ready_to_share, methodology: { quality, readiness, score_checked } }`
- `signals` is the same array as `overview.signals`; `tiles` is `verdict.tiles` or `null`.
- `ready_to_share` = `verdict.kind == "ready_for_signoff"` and job completed.
- Removed from the card: `readiness`, `must_fix`, `score_checked`, `quality` (now under `methodology`).
- A survey with no review has `verdict: null`, `tiles: null`, `signals: []`, `ready_to_share: false`.

Share packet (`/summary`): leads with the verdict headline and story, then tiles, then the sections
(Member experience, Changes chosen, Kept on purpose, Still open, What we checked / not checked). Score, provisional and coverage live
inside a `<details>` "Quality methodology" block.

## 4. Finding action contract (brief 6.3)

`Finding` gained four optional fields. Unset ones are **omitted** from saved and served JSON, so legacy saves keep their shape.

| Field | Type | Meaning |
|---|---|---|
| `action_kind` | `"paste" \| "steps" \| "you_check"` | exactly one |
| `steps` | `string[]` (1-3, each ≤ 30 words) | when `steps` |
| `you_check` | `string` | one question, when `you_check` |
| `field_location` | `string` | e.g. `"RedJade > Q1 > Question text"`, `"RedJade > Q1 > Answer 2"`, `"RedJade > Welcome > Welcome text"` |

In the served payload every finding has `action_kind` (and `action_fallback: true` while the fallback produced it);
`field_location` is added when the snapshot can pin the place and is omitted otherwise. Stored evidence is never decorated
(tested: the stored row has no `action_kind`).

Fallback for legacy findings: a human-judgement finding (B7 worth_improving, 7.2 auto, 6.2 long list) -> `you_check` with a fixed question;
otherwise `suggested_text` or options -> `paste`; otherwise `steps = [explanation]`, with sentences that mention criterion IDs or banned
words dropped (headline stands in if nothing is left). `recommendations.validate_finding(f)` returns problem codes
(`no_action`, `empty_paste`, `steps_count`, `empty_you_check`, `multiple_actions`, `step_long`, `member_impact_long`, `banned:<word>`).

**Checks still relying on the fallback: all of them.** No check sets the fields yet. In the fixtures that is
1.1 1.2 1.4 2.5 3.2 3.3 3.4 4.2 4.3 4.4 6.1 6.2 6.3 6.4 7.2 7.3 7.6 8.3 8.4 8.5 9.1 9.2 10.1 B1 B2 B7.
The contract test (`test_status_consistency.py`) fails if a finding has no action kind or two, and on banned words in
visible text outside methodology. Visible copy written by the checks themselves that still breaks the rules is pinned in
`KNOWN_COPY_DEBT` (the list may only shrink; the test also fails when an entry is fixed but not removed):
- `B7` headline "Reader could not verify image loading: …" (banned word `reader`)
- `8.5`, `B1`, `B2` `member_impact` longer than 20 words

## 5. Judgement calls (please sanity check)

1. **Timed run-through** is generated only for branching or a stated time promise, not for length alone (length is already a
   decidable Worth improving item). Say if you want it on every survey.
2. **Ready needs zero open improvements too.** Per brief 3, open Worth improving gives `almost_ready`; the user closes it with Keep (reason).
3. **Home `ready_to_share` no longer requires full branch coverage** (`detail.coverage.full_branching_coverage`) and `review.unchecked`; it is
   the verdict. Unassessed checks never block (brief 4.2). **Risk to decide:** if the reader only walked some paths and the snapshot has no
   detectable branching, the verdict can say Ready while `presentation.scope.unchecked_paths` is non-empty. Recommended follow-up: a
   curated You check "branch paths" item fed from `detail.coverage` (needs the reader's coverage data inside `extra_items`). Not done: out of scope.
4. **Time card follows its items** (a kept over-target item settles the card to Looks good), while `verdict.time.state` stays the raw measurement.
5. Looks good thresholds (`MIN_ASSESSED = 2`, share ≥ 0.5) are constants in `status.py`.
6. Over-target duration item is suppressed when a visible length finding (2.1) already covers it; absorbed findings never explain anything.

## 6. Tests

- New focused suites pass. The requested focused run (`test_signals`, `test_present*`, `test_review*`, `test_recommendation_quality`,
  `test_quality`, `test_enrich_contract`, `test_root_cause_invariants` plus all new tests) is green, plus the Python consumers I
  updated: `test_evidence_cards` (rewritten for the new card contract), `test_final_projection`, `test_summary_download`,
  `test_survey_style`, `test_committee_rounds`, `test_home_page` (two Python tests).
- A wider sweep of every test file that references the changed shapes (35 Python-only files, 21 browser files) ends with **only**
  the three failures below. I did not run the whole suite.
- Mutation checks (broke the code on purpose, tests went red): looks_good on a single check, decided items still marking screens,
  must-fix demoted by a you-check action, curated images not standing down for B7, wrong `field_location` part.
- Real bugs found and fixed while updating consumers: absorbed child partial credit counted as "explained"; curated images and B7
  double count (now tested); Time card disagreeing with the verdict after Keep; `extra_items` and the decisions API now share the
  absorbed-finding rule.

### Expected red until 1B lands (not mine to fix, `site/` is off limits)

| Test | Why |
|---|---|
| `tests/test_copy_deck.py::test_every_committed_demo_entry_has_current_canonical_projection` | committed `site/data.js` was built with the old overview. Regenerate with `python -m surveycoach.demo_export` (that writes `site/data.js`). |
| `tests/test_demo_export.py::test_committed_site_data_is_not_stale` | same |
| `tests/test_home_page.py::test_home_renders_cards_example_and_toned_errors` | browser test; the UI still reads `quality`, `readiness`, `must_fix` on the Home card (now `verdict`, `tiles`, `methodology`) |

### Where `site/` still reads the old shape (for 1B)

`overview.signals[].coverage` / `.details` -> `.methodology.*`; `signal.state` values `strong|unknown|...` -> the four states or `null`;
`detail.quality` -> `detail.methodology.quality`; `presentation.verdict` (string) -> object; `presentation.open_blockers`;
Home `readiness`, `must_fix`, `score_checked`, `quality`; `overview.not_checked_automatically`.

## 7. Notes

- Unrelated working-tree files were left alone: `.superpowers/sdd/progress.md` (already staged by someone else), the untracked plan doc and `review/after/evidence-ui-final/`.
- No push, no delegation, no network.
