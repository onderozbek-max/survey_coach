"""Pure member-experience overview over a captured snapshot and assessed review.

No checks, providers or persistence run here. Missing evidence stays missing; the snapshot's
deterministic timing estimate is the only independently derived signal.

Every state comes from surveycoach.status and every count from one item list (surveycoach.items):
signals, tiles, screen markers and the verdict can not disagree about what an item means.
"""
from __future__ import annotations

from collections import defaultdict

from surveycoach.items import build_items, extra_items, solo_plan
from surveycoach.rubric import Rubric
from surveycoach.snapshot import SurveySnapshot
from surveycoach.status import (LOOKS_GOOD, NOT_CHECKED_LABEL, STATE_LABELS, STATES, is_decided, signal_state,
                                worst_state)
from surveycoach.timing import Timing, estimate
from surveycoach.verdict import TYPE_PHRASES, build_verdict, survey_story, time_info

# Time is duration only: welcome time/reward wording (1.4) is Tone; flow and typing live elsewhere.
SIGNALS = (
    ("time", "Time", {"B5", "2.1"}),
    ("clarity", "Clarity", {"2.3", "3.1", "3.2", "3.3", "3.4", "3.5"}),
    ("honest", "Honest answers", {"B1", "B2", "B6", "4.1", "4.2", "4.3", "4.4", "5.1", "5.2", "5.3", "5.4"}),
    ("energy", "Energy & flow", {"B3", "2.2", "2.5", "8.1", "8.2", "8.3", "8.4", "8.5", "8.6"}),
    ("tone", "Tone & fun", {"B4", "1.1", "1.2", "1.3", "1.4", "9.1", "9.2", "10.1", "10.3"}),
    ("phone", "Phone comfort", {"B7", "2.4", "6.1", "6.2", "6.3", "6.4", "6.5",
                                "7.1", "7.2", "7.3", "7.4", "7.5", "7.6"}),
)
SIGNAL_OF = {cid: sid for sid, _, ids in SIGNALS for cid in ids}
EMPTY_SUMMARY = "Not checked automatically."
GOOD_SUMMARY = "Nothing to fix here."
POSITIVES = {"3.4": "Clean grammar and spelling", "4.2": "Answer choices don't overlap",
             "6.2": "Short, tappable answers", "6.4": "Easy to tap with a thumb", "8.1": "An easy, on-topic opener",
             "8.2": "A nice mix of question types", "8.3": "An insider moment members will enjoy",
             "8.5": "A good energy curve", "9.1": "A warm, human voice", "10.1": "A genuine thank-you",
             "1.3": "Treats members as co-creators"}


def _assessed(result: dict) -> bool:
    # Do not apply model defaults to old/partial JSON and manufacture a pass.
    return (result.get("assessed") is True and result.get("applies") is True
            and result.get("fraction") is not None)


def _not_applicable(result: dict) -> bool:
    return result.get("assessed") is True and result.get("applies") is False


def _energy(timing: Timing, screens: list, items: list) -> dict:
    """Per-screen load, marked with the worst state among the OPEN items on that screen."""
    by_page = {page.page_id: page for page in timing.pages}
    marks = defaultdict(list)
    for item in items:
        if item["open"]:
            for page_id in item["pages"]:
                marks[page_id].append(item["state"])
    entries = [{"page_id": screen["page_id"], "screen": screen["screen"],
                "name": screen["name"], "seconds": by_page[screen["page_id"]].seconds,
                "zone": by_page[screen["page_id"]].fatigue,
                "state": worst_state(marks[screen["page_id"]])} for screen in screens]
    heaviest = sorted(entries, key=lambda entry: -entry["seconds"])[:3]
    return {"total_seconds": timing.total_seconds, "path_uncertain": timing.path_uncertain,
            "screens": entries, "heaviest": [entry["page_id"] for entry in heaviest]}


def _strengths(results: dict, findings: list, rubric: Rubric) -> list[str]:
    flagged = {finding["criterion_id"] for finding in findings}
    candidates = [c for c in rubric.criteria if c.active and c.id in POSITIVES
                  and c.id not in flagged and _assessed(results.get(c.id) or {})
                  and results[c.id]["fraction"] == 1.0 and not results[c.id].get("findings")]
    return [POSITIVES[c.id] for c in sorted(candidates, key=lambda c: (-c.points, c.id))[:3]]


def _evidence_counts(ids: set, results: dict, flagged: set, rubric: Rubric) -> dict:
    """How much of a category was really checked. N/A checks leave the denominator."""
    criteria = [c for c in rubric.criteria if c.active and c.id in ids]
    not_applicable = [c for c in criteria if _not_applicable(results.get(c.id) or {})]
    applicable = [c for c in criteria if c not in not_applicable]
    checked = [c for c in applicable if _assessed(results.get(c.id) or {})]
    return {"criteria": criteria, "checked": checked, "not_applicable": not_applicable,
            "missing": [c for c in applicable if c not in checked], "applicable": len(applicable),
            # Partial credit with no finding to explain it is never a pass.
            "unexplained": any(results[c.id]["fraction"] < 1 and c.id not in flagged for c in checked)}


def _methodology(ids: set, counts: dict, results: dict, findings: list,
                 rubric: Rubric, decisions: dict) -> dict:
    """Expert detail for the methodology view: what ran, what credit it earned, what did not run."""
    checked, missing, not_applicable = counts["checked"], counts["missing"], counts["not_applicable"]
    total = len(counts["criteria"])
    details = [f"{len(checked)} of {total} checks assessed; states describe checked evidence only, "
               "not a full-survey pass."]
    if findings:
        details.append(f"{len(findings)} recorded {'finding' if len(findings) == 1 else 'findings'} in this dimension.")
        if any(is_decided(decisions.get(f.get("fingerprint"))) for f in findings):
            details.append("Chosen changes and kept risks are not verified fixes.")
        if any(f.get("absorbed_by") for f in findings):
            details.append("Grouped findings remain supporting evidence.")
    if checked:
        details.append("Assessed checks: " + "; ".join(
            f"{c.title} ({results[c.id]['fraction']:.0%} credit)" for c in checked))
    if missing:
        details.append("Not assessed: " + "; ".join(c.title for c in missing))
    if not_applicable:
        details.append("Not applicable: " + "; ".join(c.title for c in not_applicable))
    blockers = [b for b in rubric.blockers if b.id in ids]
    excluded = [b.title for b in blockers if _not_applicable(results.get(b.id) or {})]
    unchecked = [b.title for b in blockers if not _cleared(results.get(b.id) or {})]
    if excluded:
        details.append("Blocker not applicable: " + "; ".join(excluded))
    if unchecked:
        details.append("No complete blocker assessment: " + "; ".join(unchecked))
    return {"coverage": {"checked": len(checked), "total": total, "missing": [c.id for c in missing],
                         "not_applicable": [c.id for c in not_applicable]}, "details": details}


def _cleared(result: dict) -> bool:
    return result.get("assessed") is True and isinstance(result.get("applies"), bool)


def _navigation(related: list, all_findings: list, screens: list, plan: dict) -> dict | None:
    """Resolve grouped evidence to existing queue issues, never an empty filter."""
    by_fp = {f["fingerprint"]: f for f in all_findings}
    queued = {fp for group in ("must_fix", "quick_wins", "more")
              for item in plan.get(group, []) for fp in item["fingerprints"]}
    targets = []
    for finding in related:
        seen = set()
        while finding and finding.get("absorbed_by"):
            fp = finding["fingerprint"]
            if fp in seen:
                finding = None
                break
            seen.add(fp)
            finding = by_fp.get(finding["absorbed_by"])
        if finding and finding["fingerprint"] in queued and finding not in targets:
            targets.append(finding)
    if not targets:
        return None
    question_pages = {q["id"]: s["page_id"] for s in screens for q in s.get("questions", [])}
    page_ids = {s["page_id"] for s in screens}
    affected = {question_pages.get(f.get("question_id")) or f.get("page_id") for f in targets} & page_ids
    return {"fingerprints": [f["fingerprint"] for f in targets],
            "pages": [s["page_id"] for s in screens if s["page_id"] in affected]}


def _not_checked(results: dict, rubric: Rubric, extras: list) -> list[dict]:
    """Unassessed checks that no curated You check stands in for. Never a pass, never a blocker."""
    covered = {cid for extra in extras for cid in extra["covers"]}
    listed = []
    for check in [*(c for c in rubric.criteria if c.active), *rubric.blockers]:
        result = results.get(check.id) or {}
        done = _not_applicable(result) or (_cleared(result) and result.get("applies") is True and (
            result.get("fraction") is not None or check.id.startswith("B")))
        if not done and check.id not in covered:
            listed.append({"id": check.id, "title": check.title, "signal": SIGNAL_OF.get(check.id)})
    return listed


def _signal(sid: str, name: str, ids: set, ctx: dict) -> dict:
    items = [i for i in ctx["items"] if i["signal"] == sid]
    open_items = [i for i in items if i["open"]]
    counted = ids - {"2.1"} if sid == "time" and ctx["timing"].path_uncertain else ids
    counts = _evidence_counts(counted, ctx["results"], ctx["flagged"], ctx["rubric"])
    if sid == "time":
        # Like every card, Time follows its open items; a within-target duration, or an item the user
        # has dealt with (kept on purpose, or timed themselves), settles it. Unknown stays unknown.
        state = worst_state(i["state"] for i in open_items) or (
            LOOKS_GOOD if ctx["time"]["state"] == LOOKS_GOOD or items else None)
    else:
        state = signal_state([i["state"] for i in open_items], assessed=len(counts["checked"]),
                             applicable=counts["applicable"], unexplained=counts["unexplained"])
    lead = min(open_items, key=lambda i: STATES.index(i["state"]), default=None)
    summary = (ctx["time"]["summary"] if sid == "time" else
               f"{lead['location']}: {lead['headline']}" if lead else
               GOOD_SUMMARY if state else EMPTY_SUMMARY)
    related = [f for f in ctx["all_findings"] if f["criterion_id"] in counted]
    methodology = _methodology(counted, counts, ctx["results"], related, ctx["rubric"], ctx["decisions"])
    if sid == "time":
        methodology["details"].insert(0, "Timing is estimated from captured reading and interaction effort; "
                                      "it is not observed member completion time.")
    return {"id": sid, "name": name, "state": state, "label": STATE_LABELS.get(state, NOT_CHECKED_LABEL),
            "summary": summary,
            "items": [{"id": i["id"], "kind": i["kind"], "state": i["state"], "open": i["open"],
                       "headline": i["headline"]} for i in items],
            "lead": {"headline": lead["headline"], "location": lead["location"]} if lead else None,
            "navigation": _navigation(related, ctx["all_findings"], ctx["screens"], ctx["plan"]),
            "findings": list(dict.fromkeys(fp for i in items if i["kind"] == "finding" for fp in i["fingerprints"])),
            "pages": [s["page_id"] for s in ctx["screens"]
                      if s["page_id"] in {p for i in items for p in i["pages"]}],
            "methodology": methodology}


def build_overview(snapshot: SurveySnapshot, review: dict, decisions: dict,
                   screens: list, plan: dict, rubric: Rubric, *,
                   survey_type: str | None = None, type_source: str = "default") -> dict:
    """Project signals, one item list, the verdict and a per-screen energy map, without changing inputs.

    `survey_type` is the confirmed or detected type whose length target applies (default: the
    snapshot's own). Absorbed findings remain evidence against strengths but are not items.
    Ratios describe checked evidence only, never an inferred pass for missing AI.
    """
    timing = estimate(snapshot)
    survey_type = survey_type or snapshot.survey_type
    results = review.get("results") or {}
    all_findings = review.get("findings", [])
    findings = [f for f in all_findings if not f.get("absorbed_by")]
    targets = rubric.length_targets_minutes[survey_type]
    extras = extra_items(snapshot, screens, timing, targets[1], TYPE_PHRASES[survey_type], survey_type, findings)
    plan = plan if "must_fix" in plan else solo_plan(findings)
    items = build_items(findings, plan, decisions, extras, screens, SIGNAL_OF)
    time = time_info(snapshot, timing, targets, survey_type, type_source)
    ctx = {"items": items, "results": results, "timing": timing, "time": time, "rubric": rubric,
           "all_findings": all_findings, "screens": screens, "plan": plan, "decisions": decisions,
           # Credit is explained only by an item the user can see; an absorbed child proves nothing here.
           "flagged": {f["criterion_id"] for f in findings}}
    verdict = build_verdict(items, evidence=any(_assessed(r) for r in results.values()),
                            story=survey_story(snapshot), time=time)
    curated = [dict(e, **{k: v for k, v in item.items() if k in ("open", "decided")})
               for e in extras if e["kind"] == "you_check"
               for item in items if item["id"] == e["fingerprint"]]
    return {"headline": verdict["headline"] if verdict else "Not checked yet",
            "subline": verdict["story"] if verdict else "",
            "verdict": verdict, "signals": [_signal(sid, name, ids, ctx) for sid, name, ids in SIGNALS],
            "strengths": _strengths(results, all_findings, rubric), "energy": _energy(timing, screens, items),
            "items": items, "you_check": curated,
            "not_checked_automatically": _not_checked(results, rubric, extras)}
