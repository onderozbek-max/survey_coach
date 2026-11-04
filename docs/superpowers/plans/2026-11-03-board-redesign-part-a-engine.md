# Board redesign, Part A: engine, trust and signals

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the trust bugs visible in the screenshots. Then give the UI one presentation payload (`screens`,
`plan`, `overview`) that tells the member-centred story decided in
`docs/superpowers/specs/2026-11-03-board-review.md`.

**Architecture:** All new logic is a *read-time projection* over immutable stored snapshots and reviews, built in Python
and attached to the detail payload. The browser never recomputes numbering, grouping or signals (DRY: one source of
truth). Stored rows are never rewritten.

**Tech stack:** Python 3.14, FastAPI, SQLite, pydantic, pytest. Vanilla JS consumers (Part B).

**Run tests:** `cd survey-coach && .venv/bin/python -m pytest -q` (baseline at `26dc557`: 666 passed, 1 skipped).

## Global constraints (apply to every task)
- Never mutate stored snapshots, reviews or decisions. Projections run inside `Repository._project_detail` / `detail`.
- Never fabricate outcomes: no completion, drop-off, benchmark or member-preference claims. Estimates say "estimate".
- Keep files under 600 lines; split by responsibility, not by line count.
- Do not touch `uglyhome.png` or anything in `review/` except new files under `review/after/`.
- Commit after every task with the message given. Run the full suite before each commit.
- If an existing test asserts old behaviour that this plan intentionally changes, update the assertion and say why in the
  commit body. Never weaken a safety assertion: no implicit accept, keep requires a reason, history immutable, and no
  copy before an explicit choice.

## File map

| File | Status | Responsibility |
|---|---|---|
| `surveycoach/labels.py` | new | The only screen and question naming scheme |
| `surveycoach/snapshot.py` | modify | `clean_copy`, `community_pulse` survey type |
| `surveycoach/server/present.py` | new | Humanise explanations, same-root absorption, `enrich()` |
| `surveycoach/server/plan.py` | new | Must-fix / quick wins / more ideas, pattern grouping |
| `surveycoach/signals.py` | new | Six experience signals, strengths, energy map, headline |
| `surveycoach/server/rounds.py` | modify | Use `labels.py`; flag stale picks |
| `surveycoach/server/repository.py` | modify | `survey_type` column, `update()`, call `enrich()` |
| `surveycoach/server/__init__.py` | modify | PATCH accepts `survey_type`; summary download |
| `surveycoach/server/service.py` | modify | Review jobs use the effective survey type |
| `surveycoach/checks/content.py` | modify | Style-aware emoji and caps rules |
| `surveycoach/judge/prompts.py` | modify | Community style rule; bump prompt version |
| `surveycoach/data/rubric-v2.yaml` | modify | `community_pulse: [5, 8]` |
| `surveycoach/demo_export.py`, `surveycoach/server/example.py` | modify | Call the same `enrich()` |

---

### Task 1: One numbering scheme (fixes Q11 vs Q22)

**Files:** create `surveycoach/labels.py`; modify `surveycoach/server/rounds.py` (`locations`),
`surveycoach/server/repository.py` (`_project_detail`). Test: `tests/test_labels.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_labels.py
from surveycoach.labels import finding_label, screen_labels
from surveycoach.server.rounds import locations
from surveycoach.snapshot import SurveySnapshot

def snap():
    q = lambda i, text="Pick one": {"id": i, "text": text, "kind": "single_choice", "options": [{"id": "a", "label": "A"}]}
    return SurveySnapshot.model_validate({"title": "T", "pages": [
        {"id": "p0", "position": 0, "kind": "info", "text": "Welcome to our survey about snacks."},
        {"id": "p1", "position": 1, "kind": "question", "questions": [q("s1", "How often do you snack?")]},
        {"id": "p2", "position": 2, "kind": "question", "questions": [q("g1"), q("g2"), q("g3")]},
        {"id": "p3", "position": 3, "kind": "info", "text": "Almost done."},
        {"id": "p4", "position": 4, "kind": "info", "text": "Thank you for sharing!"}]})

def test_every_view_uses_the_same_names():
    labels = screen_labels(snap())
    assert [s["name"] for s in labels] == ["Welcome", "Q1", "Q2–Q4", "Message", "Thank you"]
    assert labels[2]["questions"][1] == {"id": "g2", "number": 3, "label": "Q3"}
    assert finding_label({"question_id": "g2"}, labels) == "Q3 · Screen 3"
    assert finding_label({"page_id": "p3"}, labels) == "Message · Screen 4"
    assert finding_label({}, labels) == "Whole survey"
    place = next(p for p in locations(snap().model_dump()) if p["question_id"] == "g2")
    assert place["screen_label"] == "Q3 · Screen 3"

def test_researcher_question_labels_win_when_captured():
    s = snap(); s.pages[1].questions[0].label = "Q7a"
    assert screen_labels(s)[1]["name"] == "Q7a"
```

- [ ] **Step 2: Run it.** `.venv/bin/python -m pytest tests/test_labels.py -q`. Expected: FAIL (`No module named surveycoach.labels`).

- [ ] **Step 3: Implement `surveycoach/labels.py`**

```python
"""The one naming scheme for screens and questions. Every view reads it; nobody counts on their own."""
from __future__ import annotations

from surveycoach.snapshot import SurveySnapshot

_ROLE_NAMES = {"intro": "Welcome", "thank_you": "Thank you", "screen_out": "Screen-out", "end": "Last screen"}


def _topic(text: str, words: int = 5) -> str:
    parts = (text or "").split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def screen_labels(snapshot: SurveySnapshot) -> list[dict]:
    labels, number = [], 0
    for index, page in enumerate(snapshot.pages):
        questions = []
        for question in page.questions:
            if question.kind == "info":
                continue
            number += 1
            questions.append({"id": question.id, "number": number, "label": question.label or f"Q{number}"})
        if len(questions) == 1:
            name = questions[0]["label"]
        elif questions:
            name = f'{questions[0]["label"]}–{questions[-1]["label"]}'
        else:
            name = _ROLE_NAMES.get(snapshot.page_role(page), "Message")
        first = next((q.text for q in page.questions if q.kind != "info"), "")
        labels.append({"page_id": page.id, "screen": index + 1, "name": name,
                       "topic": _topic(first or snapshot.page_copy(page)), "questions": questions})
    return labels


def finding_label(finding: dict, labels: list[dict]) -> str:
    for screen in labels:
        for question in screen["questions"]:
            if question["id"] == finding.get("question_id"):
                return f'{question["label"]} · Screen {screen["screen"]}'
        if not finding.get("question_id") and finding.get("page_id") == screen["page_id"]:
            return f'{screen["name"]} · Screen {screen["screen"]}'
    return "Whole survey"
```

- [ ] **Step 4: Use it in `rounds.locations`.** Build `labels = screen_labels(SurveySnapshot.model_validate(snapshot))`
  once. Set the page-level `screen_label` to `f'{labels[i]["name"]} · Screen {i+1}'`. Set the question-level label to
  `finding_label({"question_id": question["id"]}, labels)`. Delete the local `number` counter. Info-kind questions
  keep a location but use the screen label.
- [ ] **Step 5:** In `_project_detail`, add `data["screens"] = screen_labels(SurveySnapshot.model_validate(data["snapshot"]))`.
- [ ] **Step 6:** Run the full suite. Fix any round-comparison tests that asserted `Screen n · Qm` text; they should now
  expect `Qm · Screen n`.
- [ ] **Step 7: Commit:** `Use one screen and question numbering scheme everywhere`

### Task 2: Clean screen copy (fixes "...celebrated! Next This takes about 14 minutes")

**Files:** modify `surveycoach/snapshot.py`. Test: `tests/test_clean_copy.py`, plus a shared fixture
`tests/fixtures/clean_copy_cases.json` that Part B's JS mirror also runs.

- [ ] **Step 1: Fixture and failing test**

```json
[["The spookiest time\n\n\n\n\n\nLet us know how you celebrated!\n\nNext", "The spookiest time\n\nLet us know how you celebrated!"],
 ["Tell us what comes next", "Tell us what comes next"],
 ["Thanks!\nSubmit\n", "Thanks!"],
 ["Line one  \n\n\n\nLine two\u00a0", "Line one\n\nLine two"],
 ["Next", ""]]
```

```python
# tests/test_clean_copy.py
import json, pathlib
from surveycoach.snapshot import SurveySnapshot, clean_copy
CASES = json.loads((pathlib.Path(__file__).parent / "fixtures/clean_copy_cases.json").read_text())

def test_clean_copy_cases():
    for raw, expected in CASES:
        assert clean_copy(raw) == expected

def test_time_rewrite_never_appends_to_a_button_label():
    snapshot = SurveySnapshot.model_validate({"title": "Halloween", "pages": [
        {"id": "p0", "position": 0, "kind": "info",
         "text": "Welcome! Let us know how you celebrated. It takes 10 minutes.\n\n\n\nNext"},
        {"id": "p1", "position": 1, "kind": "question", "questions": [{"id": "q", "text": "Pick", "kind": "single_choice",
         "options": [{"id": "a", "label": "A"}]}]}]})
    assert snapshot.intro_text == "Welcome! Let us know how you celebrated. It takes 10 minutes."
```

- [ ] **Step 2: Implement** in `snapshot.py`:

```python
_NAV_TAIL = re.compile(r"(?:^|\n)[ \t]*(?:next|continue|back|start|begin|submit|finish|done)[ \t]*$", re.I)


def clean_copy(text: str) -> str:
    """Screen copy as a member reads it: no trailing navigation label, no runs of blank lines."""
    text = (text or "").replace("\xa0", " ").rstrip()
    while (trimmed := _NAV_TAIL.sub("", text).rstrip()) != text:
        text = trimmed
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
```

Change `page_copy` to clean each part before de-duplicating:
`parts = [clean_copy(t) for t in (...)]` and `" ".join(dict.fromkeys(p for p in parts if p))`. Do **not** change
`review_hash`/`content_hash` inputs; stored identity must stay stable.

- [ ] **Step 3:** Run the suite. Any test expecting raw page text in an intro rewrite must be updated with a reason.
- [ ] **Step 4: Commit:** `Strip navigation labels and blank-line runs from screen copy`

### Task 3: Stale picks are explained, not silently reverted

**Files:** modify `surveycoach/server/rounds.py` (`valid_decisions`). Test: `tests/test_stale_pick.py`.

- [ ] **Step 1: Test:** a saved `pick` whose `picked_text` is no longer offered returns
  `{"action": "open", "stale_pick": True, "previous_text": <old text>}`. A still-valid pick has no `stale_pick` key.
- [ ] **Step 2: Implement:** in the reset branch, `dict(decision, action="open", picked_text=None, manual_done=False,
  stale_pick=True, previous_text=decision.get("picked_text"))`.
- [ ] **Step 3: Commit:** `Flag picks invalidated by improved suggestions`

### Task 4: Presentation projection (absorption and humanised prose)

**Files:** create `surveycoach/server/present.py`. Test: `tests/test_present.py`.

- [ ] **Step 1: Test**

```python
from surveycoach.server.present import ABSORBS, humanize, present_findings
TITLES = {"4.1": "Every member can find their answer", "4.3": "A way out when needed", "8.4": "Only relevant questions"}

def f(fp, cid, sev, q="q5", expl="Why."):
    return {"fingerprint": fp, "criterion_id": cid, "severity": sev, "question_id": q, "explanation": expl, "headline": fp}

def test_bookkeeping_sentence_becomes_also_covers():
    text, covered = humanize("Add a non-shopper answer. This finding also covers 4.1 and 4.3.", TITLES)
    assert text == "Add a non-shopper answer."
    assert covered == ["Every member can find their answer", "A way out when needed"]

def test_blocker_absorbs_same_root_at_same_place_only():
    out = {x["fingerprint"]: x for x in present_findings(
        [f("b2", "B2", "must_fix"), f("r84", "8.4", "worth_improving"), f("o41", "4.1", "worth_improving", q="q9")], TITLES)}
    assert out["r84"]["absorbed_by"] == "b2" and out["b2"]["also_affects"] == ["r84"]
    assert "absorbed_by" not in out["o41"]

def test_input_is_not_mutated():
    original = [f("b2", "B2", "must_fix"), f("r84", "8.4", "worth_improving")]
    present_findings(original, TITLES)
    assert "absorbed_by" not in original[1] and "also_affects" not in original[0]
```

- [ ] **Step 2: Implement**

```python
"""How findings read to a researcher. A projection: stored reviews are never changed."""
from __future__ import annotations

import re

ABSORBS = {"B1": {"5.1", "5.2", "5.3"}, "B2": {"4.1", "4.3", "8.4"}, "B5": {"1.4"}, "B7": {"7.1", "7.3", "7.6"}}
_ID = re.compile(r"\b(?:B\d|\d{1,2}\.\d)\b")


def _place(finding: dict) -> str:
    return finding.get("question_id") or finding.get("page_id") or "survey"


def humanize(text: str, titles: dict[str, str]) -> tuple[str, list[str]]:
    """Drop rubric bookkeeping sentences ("also covers 4.1"); keep everything else verbatim."""
    kept, covered = [], []
    for sentence in re.split(r"(?<=[.!?])\s+", text or ""):
        ids = [i for i in _ID.findall(sentence) if i in titles]
        if ids and re.search(r"\bcover", sentence, re.I):
            covered += [titles[i] for i in ids]
        elif sentence.strip():
            kept.append(sentence)
    return " ".join(kept).strip(), list(dict.fromkeys(covered))


def present_findings(findings: list[dict], titles: dict[str, str]) -> list[dict]:
    out = []
    for finding in findings:
        text, covered = humanize(finding.get("explanation", ""), titles)
        out.append(dict(finding, explanation=text, also_covers=covered))
    for blocker in (f for f in out if f["severity"] == "must_fix"):
        family = ABSORBS.get(blocker["criterion_id"], set())
        for other in out:
            if (other["severity"] != "must_fix" and other["criterion_id"] in family
                    and not other.get("absorbed_by") and _place(other) == _place(blocker)):
                other["absorbed_by"] = blocker["fingerprint"]
                blocker["also_affects"] = [*blocker.get("also_affects", []), other["fingerprint"]]
    return out
```

- [ ] **Step 3: Commit:** `Absorb same-root findings and drop rubric bookkeeping from prose`

### Task 5: Survey style (`community_pulse`) and style-aware tone checks

**Files:** `snapshot.py` (`SurveyType`), `data/rubric-v2.yaml`, `checks/content.py`, `judge/prompts.py`,
`server/repository.py`, `server/__init__.py`, `server/service.py`. Tests: `tests/test_survey_style.py`.

- [ ] **Step 1: Tests (write all first)**
  1. With `survey_type="community_pulse"`, a question `"What did you do this Halloween? \U0001F383"` and an answer
     `"Trick-or-treat \U0001F36C"` produce **no** 9.1 findings. An answer labelled only `"\U0001F44D"` produces exactly
     one finding headed "Answer is only an emoji". (Write emoji as Python `\U` escapes in tests; the repo's tooling
     strips literal emoji.)
  2. With `community_pulse`, "Which treats DIDN'T you like?" produces no "ALL CAPS" finding. "WHICH TREATS DID YOU LIKE"
     still does (CAPS_RUN).
  3. With the default type, the existing emoji tests still pass unchanged.
  4. API: `PATCH /api/surveys/{id}` with `{"survey_type": "community_pulse"}` returns 200. The next `GET` has
     `survey_type == "community_pulse"`, `survey_type_chosen is True`, and different 9.1 findings. The stored `reviews.result` row is
     byte-identical before and after (read it with sqlite3). `{"survey_type": "nonsense"}` returns 422. `{"title": "x"}` still works.
  5. `service.run_job` reviews with the chosen type (assert via a stub provider that receives the effective snapshot).
- [ ] **Step 2: Model and rubric.** Add `"community_pulse"` to `SurveyType`. Add `community_pulse: [5, 8]` under
  `length_targets_minutes`.
- [ ] **Step 3: Checks.** In `content.py`, add `EMOJI_ONLY = re.compile(r"^[^\w]*$")` and
  `playful = ctx.snapshot.survey_type == "community_pulse"`. In `emoji_rule`: when `playful`, skip the intro and question
  rules. For options, emit only when `emoji_count(label) and EMOJI_ONLY.match(label)`, using headline "Answer is only an emoji",
  explanation "Add a word next to the emoji so every member, and screen readers, get the same meaning.", and
  member impact "Emoji alone can read differently across phones and assistive technology." In `_standards_findings`,
  when `playful and len(shouting) == 1 and not CAPS_RUN.search(q.text)`, skip the caps finding.
- [ ] **Step 4: Prompt.** Add to the judge rules: "If the survey type is community_pulse, emoji, exclamation marks and
  playful wording are part of the community voice; flag them only when they hide meaning." Bump the prompt version
  constant by one (cache keys must change).
- [ ] **Step 5: Persistence.** In `Repository.__init__` migration, add the column if missing:
  `ALTER TABLE surveys ADD COLUMN survey_type TEXT`. Replace `rename()` with
  `update(survey_id, title=None, survey_type=None)`; it raises `KeyError` for unknown ids. In `detail()`, read the
  override and set `data["survey_type"] = override or snapshot["survey_type"]` and `data["survey_type_chosen"] = bool(override)`.
  Pass `dict(data["snapshot"], survey_type=data["survey_type"])` to `project_review`, `screen_labels`
  and `enrich`. Leave `data["snapshot"]` itself raw.
- [ ] **Step 6: API.** Replace `TitleRequest` with
  `SurveyUpdate(title: str | None = Field(None, min_length=1, max_length=200), survey_type: SurveyType | None = None)`.
  Keep `extra="forbid"` and add a validator requiring at least one field.
- [ ] **Step 7: Jobs.** In `run_job`, validate `dict(detail["snapshot"], survey_type=detail["survey_type"])`.
- [ ] **Step 8: Commit:** `Add community survey style with voice-aware tone checks`

### Task 6: Plan curation (must-fix, quick wins, more ideas)

**Files:** create `surveycoach/server/plan.py`. Test: `tests/test_plan.py`.

- [ ] **Step 1: Tests**
  1. 12 findings with criterion 9.2 and headline "Question isn't in sentence case" on different questions become
     **one** `more` item with `count == 12` and `tier == "nice_to_have"`.
  2. Must-fix items are never grouped: two B2 findings give two `must_fix` items.
  3. `quick_wins` holds at most 6 `improve` items, sorted by rubric points (descending) and then by screen order. The rest go to `more`.
  4. Absorbed findings appear in no list.
  5. An item is `decided` when every member has a `pick`/`original` decision or a `keep` with a reason.
  6. Counts: `{"must_fix": n, "quick_wins": n, "more": n, "open_must_fix": n}`.
- [ ] **Step 2: Implement**

```python
"""Turn findings into a short plan: every must-fix, up to six quick wins, everything else grouped."""
from __future__ import annotations

QUICK_WIN_LIMIT = 6
NICE_TO_HAVE = {"9.1", "9.2"}


def _decided(decision: dict | None) -> bool:
    return bool(decision) and (decision.get("action") in {"pick", "original"}
                               or (decision.get("action") == "keep" and decision.get("reason", "").strip()))


def build_plan(findings: list[dict], decisions: dict, points: dict[str, float], screens: list[dict]) -> dict:
    order = {s["page_id"]: s["screen"] for s in screens}
    order.update({q["id"]: s["screen"] for s in screens for q in s["questions"]})
    where = lambda f: order.get(f.get("question_id")) or order.get(f.get("page_id")) or 0
    groups: dict[tuple, list[dict]] = {}
    for f in sorted((f for f in findings if not f.get("absorbed_by")), key=where):
        key = (f["fingerprint"],) if f["severity"] == "must_fix" else (f["criterion_id"], " ".join(f["headline"].lower().split()))
        groups.setdefault(key, []).append(f)
    items = []
    for members in groups.values():
        lead = members[0]
        tier = "must_fix" if lead["severity"] == "must_fix" else "nice_to_have" if lead["criterion_id"] in NICE_TO_HAVE else "improve"
        items.append({"id": lead["fingerprint"] if len(members) == 1 else f"pattern-{lead['fingerprint']}",
                      "fingerprints": [m["fingerprint"] for m in members], "criterion_id": lead["criterion_id"],
                      "headline": lead["headline"], "count": len(members), "tier": tier, "screen": where(lead),
                      "decided": all(_decided(decisions.get(m["fingerprint"])) for m in members)})
    must = [i for i in items if i["tier"] == "must_fix"]
    improve = sorted((i for i in items if i["tier"] == "improve"), key=lambda i: (-points.get(i["criterion_id"], 0), i["screen"]))
    quick, rest = improve[:QUICK_WIN_LIMIT], improve[QUICK_WIN_LIMIT:]
    more = rest + [i for i in items if i["tier"] == "nice_to_have"]
    return {"must_fix": must, "quick_wins": quick, "more": more,
            "counts": {"must_fix": len(must), "quick_wins": len(quick), "more": len(more),
                       "open_must_fix": sum(not i["decided"] for i in must)}}
```

- [ ] **Step 3: Commit:** `Curate findings into must-fix, quick wins and grouped ideas`

### Task 7: Experience signals, strengths, energy map, headline

**Files:** create `surveycoach/signals.py`. Test: `tests/test_signals.py`.

- [ ] **Step 1: Tests**
  1. An open B2 finding makes `honest` = `needs_work`, even when other honest criteria pass.
  2. A group with no assessed results and no findings is `unknown` with the label "Not checked yet". A group with no assessed
     results but some findings is `mixed`.
  3. The weighted ratio thresholds are ≥ 0.85 `strong`, ≥ 0.6 `mixed`, otherwise `needs_work`.
  4. Time: 13.5 estimated minutes for `community_pulse` (target 5/8) gives `needs_work` with the summary
     "About 13½ minutes (estimate). Community surveys aim for 5 minutes or less." When `path_uncertain`, the summary says
     "Branching makes the total uncertain." and the length rule is not applied.
  5. Strengths include only criteria with `fraction == 1.0`, `assessed`, `applies` and no findings, from `POSITIVES`;
     there are at most 3, sorted by points. Legacy reviews (AI results missing) produce no AI-criterion strengths.
  6. The energy map has one entry per screen with `seconds` (not cumulative), `zone` from `timing.estimate`, `worst`
     (`must_fix`/`worth_improving`/None, ignoring absorbed findings) and `heaviest` (top 3 page_ids).
  7. Headline: `"3 must-fixes before launch, then 6 quick wins"`. With no must-fixes:
     `"No must-fixes found in what we checked"`. Subline: `"About 13½ minutes for members (estimate). The heaviest moment is Q8–Q18."`
- [ ] **Step 2: Implement** (the key tables are fixed; write the helpers to satisfy the tests):

```python
SIGNALS = (
    ("time", "Time", {"B5", "1.4", "2.1", "2.2", "2.3", "2.4", "2.5"}),
    ("clarity", "Clarity", {"3.1", "3.2", "3.3", "3.4", "3.5"}),
    ("honest", "Honest answers", {"B1", "B2", "B6", "4.1", "4.2", "4.3", "4.4", "5.1", "5.2", "5.3", "5.4"}),
    ("energy", "Energy & flow", {"B3", "8.1", "8.2", "8.3", "8.4", "8.5", "8.6"}),
    ("tone", "Tone & fun", {"B4", "1.1", "1.2", "1.3", "9.1", "9.2", "10.1", "10.3"}),
    ("phone", "Phone comfort", {"B7", "6.1", "6.2", "6.3", "6.4", "6.5", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6"}),
)
STATE_LABELS = {"strong": "Looking good", "mixed": "Room to improve", "needs_work": "Needs attention",
                "unknown": "Not checked yet"}
STRONG_SUMMARY = {"clarity": "Questions read clearly in what we checked.",
                  "honest": "Every member can answer honestly in what we checked.",
                  "energy": "The flow keeps members engaged in what we checked.",
                  "tone": "Warm, community voice in what we checked.",
                  "phone": "Comfortable on a phone in what we checked."}
POSITIVES = {"3.4": "Clean grammar and spelling", "4.2": "Answer choices don't overlap",
             "6.2": "Short, tappable answers", "6.4": "Easy to tap with a thumb", "8.1": "An easy, on-topic opener",
             "8.2": "A nice mix of question types", "8.3": "An insider moment members will enjoy",
             "8.5": "A good energy curve", "9.1": "A warm, human voice", "10.1": "A genuine thank-you",
             "1.3": "Treats members as co-creators"}
TYPE_NAMES = {"community_pulse": "Community", "ihut": "Home-use test", "non_ihut_product": "Product test",
              "services_concept": "Concept", "market_research": "Market research"}
```

  Public API: `build_overview(snapshot: SurveySnapshot, review: dict, decisions: dict, screens: list, plan: dict,
  rubric: Rubric) -> dict` returning
  `{"headline", "subline", "signals": [{id, name, state, label, summary, findings, pages}], "strengths": [...],
  "energy": {"total_seconds", "path_uncertain", "screens": [...], "heaviest": [...]}}`.
  Kept-with-reason blockers do not force `needs_work`; a researcher's documented decision is respected.
  Format minutes with `_minutes(x)`: round to the nearest half; `1 → "1 minute"`, `13.5 → "13½ minutes"`.
- [ ] **Step 3: Commit:** `Add member experience signals, strengths and energy map`

### Task 8: One enrichment step for every payload

**Files:** add `enrich(data, rubric)` in `surveycoach/server/present.py`; call it from `Repository.detail` (after
decisions and carry-over are final), `demo_export.py` and `server/example.py`. Test: `tests/test_enrich_contract.py`.

- [ ] **Step 1: Test:** `GET /api/surveys/{id}` (sample survey via `POST /api/samples/boxer-briefs` in a temp DB) contains
  `screens`, `plan.counts`, `overview.headline`, and six `overview.signals`. Every finding has `also_covers`. The
  exported demo data (`build_demo_data`) has the same keys, so the public demo and local workspace share one contract.
- [ ] **Step 2: Implement:**

```python
def enrich(data: dict, rubric) -> dict:
    snapshot = SurveySnapshot.model_validate(dict(data["snapshot"], survey_type=data.get("survey_type") or data["snapshot"].get("survey_type", "non_ihut_product")))
    titles = {c.id: c.title for c in rubric.criteria} | {b.id: b.title for b in rubric.blockers}
    points = {c.id: c.points for c in rubric.criteria}
    data["screens"] = screen_labels(snapshot)
    if data.get("review"):
        data["review"]["findings"] = present_findings(data["review"]["findings"], titles)
        data["plan"] = build_plan(data["review"]["findings"], data.get("decisions", {}), points, data["screens"])
        data["overview"] = build_overview(snapshot, data["review"], data.get("decisions", {}), data["screens"], data["plan"], rubric)
    return data
```

  Remove the separate `data["screens"]` line from Task 1, Step 5 (enrich owns it now).
  **Ordering matters:** `compare_rounds` and `change_sheet` must receive findings *after* `present_findings`, so absorbed
  findings are excluded from change sheets (they have no independent change). Add a test for that.
- [ ] **Step 3: Commit:** `Attach screens, plan and overview to every review payload`

### Task 9: Downloadable stakeholder summary

**Files:** `server/__init__.py` (`summary` route), `server/report.py`. Test: `tests/test_summary_download.py`.

- [ ] **Step 1: Tests:** `GET .../summary?download=1` has
  `content-disposition: attachment; filename="surveycoach-<slug>-v<round>.html"`. The body contains
  `overview.headline`, each signal name with its state label, the decided changes, and "Kept on purpose" reasons. It contains no
  `<script>`, no external URLs, and no forbidden phrases. HTML-escaped user text stays escaped. Without `download`, the response is
  unchanged inline HTML.
- [ ] **Step 2: Implement:** self-contained HTML with inline CSS using the Part B light tokens (copy the values; this
  file is standalone by design). Sections: Headline → Member experience (six rows) → Changes chosen (word-level
  before/after as `<del>`/`<ins>`) → Kept on purpose (with reasons) → Still open → What we checked / not checked.
- [ ] **Step 3: Commit:** `Make the stakeholder summary a downloadable, self-contained file`

### Task 10: Forbidden-claims guard

**Files:** `tests/test_copy_guard.py`.

- [ ] **Step 1: Test:** scan `site/*.html`, `site/*.js` (excluding generated `data.js`), `surveycoach/server/report.py`
  and `surveycoach/signals.py` for
  `re.compile(r"actually finish|completion rate|drop-?off rate|will finish|guarantee|approved for launch|launch-ready", re.I)`.
  It fails today on `local.html` (the hero). Part B, Task 10 makes it pass. Mark it `xfail(strict=True)` until then and remove the marker in Part B.
- [ ] **Step 2: Commit:** `Guard product copy against outcome claims`

## Part A done when
- The full suite is green, with the new tests listed above.
- In the Halloween workspace (isolated DB copy): the welcome rewrite contains no "Next"; the B2 card shows 8.4 under
  `also_affects`; the rail, phone and card all say the same Q label; with style "Community & fun", the 12 emoji findings
  disappear; `plan.counts.quick_wins <= 6`.
- No stored row changed (verify with a checksum of `reviews` and `decisions` tables before and after browsing).
