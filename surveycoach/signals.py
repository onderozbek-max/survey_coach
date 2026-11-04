"""Pure member-experience overview over a captured snapshot and assessed review.

No checks, providers or persistence run here. Missing evidence stays missing; the
snapshot's deterministic timing estimate is the only independently derived signal.
"""
from __future__ import annotations

from math import floor

from surveycoach.rubric import Rubric
from surveycoach.snapshot import SurveySnapshot
from surveycoach.timing import Timing, estimate

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
_STATE_ORDER = {"unknown": -1, "strong": 0, "mixed": 1, "needs_work": 2}


def _minutes(value: float) -> str:
    """Nearest half minute, with ties rounded up rather than to even."""
    halves = floor(value * 2 + .5)
    whole, half = divmod(halves, 2)
    number = (str(whole) if whole or not half else "") + ("½" if half else "")
    return f"{number} {'minute' if halves in (1, 2) else 'minutes'}"


def _assessed(result: dict) -> bool:
    # Do not apply model defaults to old/partial JSON and manufacture a pass.
    return (result.get("assessed") is True and result.get("applies") is True
            and result.get("fraction") is not None)


def _ratio_state(ratio: float) -> str:
    return "strong" if ratio >= .85 else "mixed" if ratio >= .6 else "needs_work"


def _open(finding: dict, decisions: dict) -> bool:
    decision = decisions.get(finding.get("fingerprint")) or {}
    return not (decision.get("action") in {"pick", "original"} or (
        decision.get("action") == "keep" and bool(decision.get("reason", "").strip())))


def _page_id(finding: dict, question_pages: dict, page_ids: set) -> str | None:
    page_id = question_pages.get(finding.get("question_id")) or finding.get("page_id")
    return page_id if page_id in page_ids else None


def _energy(timing: Timing, screens: list, findings: list) -> dict:
    by_page = {page.page_id: page for page in timing.pages}
    page_ids = {screen["page_id"] for screen in screens}
    question_pages = {q["id"]: screen["page_id"]
                      for screen in screens for q in screen.get("questions", [])}
    worst = {}
    for finding in findings:
        page_id = _page_id(finding, question_pages, page_ids)
        severity = finding.get("severity")
        if page_id and severity in {"must_fix", "worth_improving"}:
            if worst.get(page_id) != "must_fix":
                worst[page_id] = severity
    entries = [{"page_id": screen["page_id"], "screen": screen["screen"],
                "name": screen["name"], "seconds": by_page[screen["page_id"]].seconds,
                "zone": by_page[screen["page_id"]].fatigue,
                "worst": worst.get(screen["page_id"])} for screen in screens]
    heaviest = sorted(entries, key=lambda entry: -entry["seconds"])[:3]
    return {"total_seconds": timing.total_seconds, "path_uncertain": timing.path_uncertain,
            "screens": entries, "heaviest": [entry["page_id"] for entry in heaviest]}


def _signal_state(ids: set, results: dict, findings: list, decisions: dict,
                  rubric: Rubric) -> str:
    if any(f["severity"] == "must_fix" and _open(f, decisions) for f in findings):
        return "needs_work"
    assessed = [(c.points, results[c.id]["fraction"]) for c in rubric.criteria
                if c.active and c.id in ids and _assessed(results.get(c.id) or {})]
    if not assessed:
        return "mixed" if findings else "unknown"
    return _ratio_state(sum(points * fraction for points, fraction in assessed)
                        / sum(points for points, _ in assessed))


def _time_summary(snapshot: SurveySnapshot, timing: Timing, rubric: Rubric) -> str:
    summary = f"About {_minutes(timing.total_seconds / 60)} (estimate)."
    if timing.path_uncertain:
        return summary + " Branching makes the total uncertain."
    target = rubric.length_targets_minutes[snapshot.survey_type][0]
    return (summary + f" {TYPE_NAMES[snapshot.survey_type]} surveys aim for "
            f"{_minutes(target)} or less.")


def _strengths(results: dict, findings: list, rubric: Rubric) -> list[str]:
    flagged = {finding["criterion_id"] for finding in findings}
    candidates = [c for c in rubric.criteria if c.active and c.id in POSITIVES
                  and c.id not in flagged and _assessed(results.get(c.id) or {})
                  and results[c.id]["fraction"] == 1.0 and not results[c.id].get("findings")]
    return [POSITIVES[c.id] for c in sorted(candidates, key=lambda c: (-c.points, c.id))[:3]]


def build_overview(snapshot: SurveySnapshot, review: dict, decisions: dict,
                   screens: list, plan: dict, rubric: Rubric) -> dict:
    """Project six signals and a per-screen energy map, without changing inputs.

    Findings/pages are ordered fingerprint/page-ID lists for navigation. Absorbed
    findings remain evidence against strengths but do not duplicate screen markers.
    Ratios describe checked evidence only, never an inferred pass for missing AI.
    """
    timing = estimate(snapshot)
    results = review.get("results") or {}
    all_findings = review.get("findings", [])
    findings = [f for f in all_findings if not f.get("absorbed_by")]
    energy = _energy(timing, screens, findings)
    question_pages = {q["id"]: s["page_id"] for s in screens for q in s.get("questions", [])}
    page_ids = {s["page_id"] for s in screens}
    signals = []
    for sid, name, ids in SIGNALS:
        # A retained length verdict is not a route estimate when paths branch.
        assessed_ids = ids - {"2.1"} if sid == "time" and timing.path_uncertain else ids
        related = [f for f in findings if f["criterion_id"] in assessed_ids]
        state = _signal_state(assessed_ids, results, related, decisions, rubric)
        if sid == "time":
            summary = _time_summary(snapshot, timing, rubric)
            if snapshot.pages and not timing.path_uncertain:
                low, high = rubric.length_targets_minutes[snapshot.survey_type]
                minutes = timing.total_seconds / 60
                length_state = "strong" if minutes <= low else "mixed" if minutes <= high else "needs_work"
                state = max((state, length_state), key=_STATE_ORDER.get)
        elif state == "strong":
            summary = STRONG_SUMMARY[sid]
        elif state == "unknown":
            summary = "Not checked yet."
        else:
            summary = "There is room to improve in what we checked."
        affected = {_page_id(f, question_pages, page_ids) for f in related}
        signals.append({"id": sid, "name": name, "state": state, "label": STATE_LABELS[state],
                        "summary": summary,
                        "findings": list(dict.fromkeys(f["fingerprint"] for f in related)),
                        "pages": [s["page_id"] for s in screens if s["page_id"] in affected]})
    counts = plan.get("counts", {})
    must = counts.get("open_must_fix", 0)
    quick = counts.get("quick_wins", 0)
    headline = (f"{must} must-{'fix' if must == 1 else 'fixes'} before launch, "
                f"then {quick} quick {'win' if quick == 1 else 'wins'}" if must
                else "No must-fixes found in what we checked")
    subline = f"About {_minutes(timing.total_seconds / 60)} for members (estimate)."
    if timing.path_uncertain:
        subline += " Branching makes the total uncertain."
    if energy["heaviest"]:
        name = next(s["name"] for s in screens if s["page_id"] == energy["heaviest"][0])
        subline += f" The heaviest moment is {name}."
    return {"headline": headline, "subline": subline, "signals": signals,
            "strengths": _strengths(results, all_findings, rubric), "energy": energy}
