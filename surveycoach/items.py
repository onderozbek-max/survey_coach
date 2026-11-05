"""One list of things to act on, shared by signals, tiles, screen markers and the verdict.

An item is a plan group of findings (identical findings across a repeated block are one card),
a curated You check item, or the duration item. Each is counted once, carries one state from
surveycoach.status, and is `open` until an explicit decision closes it. Nothing downstream
recomputes states from findings.
"""
from __future__ import annotations

import hashlib

from surveycoach.labels import QUESTION_LABEL, finding_label, group_label, join_names
from surveycoach.recommendations import action_kind_of
from surveycoach.status import (DONE, IMPROVE, KEEP, USE, YOU_CHECK, finding_state, handled_kind, worst_state)
from surveycoach.you_check import build_you_checks

TIERS = ("must_fix", "quick_wins", "more")


def _page_of(finding: dict, question_pages: dict, page_ids: set) -> str | None:
    page_id = question_pages.get(finding.get("question_id")) or finding.get("page_id")
    return page_id if page_id in page_ids else None


def duration_extra(minutes: float, target_high: float, phrase: str, survey_type: str, findings: list) -> dict | None:
    """Over target and not already explained by a length finding: a decidable improvement."""
    if minutes <= target_high or any(f.get("criterion_id") == "2.1" for f in findings):
        return None
    digest = hashlib.sha1(f"{survey_type}|{target_high}".encode()).hexdigest()[:8]
    headline = f"Longer than {phrase} usually take"
    return {"fingerprint": f"time:over-target:{digest}", "kind": "time", "state": IMPROVE,
            "title": headline, "theme": "Timing", "signal": "time", "covers": [],
            "instruction": f"Can you shorten it from about {round(minutes)} minutes to {target_high:g} or fewer?",
            "where": "Whole survey", "pages": [], "screens": [], "questions": []}


def extra_items(snapshot, screens: list, timing, target_high: float, phrase: str, survey_type: str,
                findings: list, coverage: dict | None = None) -> list[dict]:
    """Finding-like items that are not findings, each decidable through the ordinary decisions API.

    The curated images check stands down when a finding already asks about those images.
    """
    findings = [f for f in findings if not f.get("absorbed_by")]   # only what the user can see explains anything
    checks = build_you_checks(snapshot, screens, timing, target_high, coverage)
    if any(f.get("criterion_id") == "B7" and finding_state(f) == YOU_CHECK for f in findings):
        checks = [c for c in checks if c["id"] != "images"]
    extras = [dict(c, kind="you_check", state=YOU_CHECK) for c in checks]
    duration = duration_extra(timing.total_seconds / 60, target_high, phrase, survey_type, findings)
    extras += [duration] if duration and snapshot.pages and not timing.path_uncertain else []
    for extra in extras:   # finding-like, so decisions can restore "what it was"
        extra["evidence"] = extra["instruction"]
        extra["current_text"] = None
    return extras


def solo_plan(findings: list[dict]) -> dict:
    """No grouping available (no plan given): each visible finding is its own card."""
    return {"quick_wins": [{"id": f["fingerprint"], "fingerprints": [f["fingerprint"]]} for f in findings]}


def _group_instruction(members: list[dict], screens: list[dict]) -> dict:
    """One action line for a grouped you-check card, naming every question it covers ("Scroll Q4, Q6 and Q8 ...").

    Only a you-check line carries question labels; paste and steps are identical across the group by construction.
    """
    lead = members[0]
    names = [q["label"] for s in screens for q in s.get("questions", []) for m in members if q["id"] == m.get("question_id")]
    if len(members) < 2 or lead.get("action_kind") != "you_check" or not QUESTION_LABEL.search(lead.get("you_check") or ""):
        return {}
    return {"instruction": QUESTION_LABEL.sub(join_names(names), lead["you_check"], count=1)}


def _handling(decisions: list[dict | None]) -> dict:
    """How the author closed a card. Open until every member is handled; a mix reports the weakest evidence:
    `done` (their word, unverified until Check again), then `keep`, then `use` (our change accepted)."""
    kinds = [handled_kind(d) for d in decisions]
    if not kinds or None in kinds:
        return {"open": True, "decided": False, "handled_kind": None, "unverified": False, "keep_reason": None}
    kind = next(k for k in (DONE, KEEP, USE) if k in kinds)
    chip = next((d.get("keep_reason") for d, k in zip(decisions, kinds) if k == KEEP and d.get("keep_reason")), None)
    return {"open": False, "decided": True, "handled_kind": kind, "unverified": kind == DONE, "keep_reason": chip}


def _where(pages: list[str], screens: list[int]) -> dict:
    return {"pages": pages, "screens": screens, "page_id": pages[0] if pages else None,
            "screen": screens[0] if screens else None}


def build_items(findings: list[dict], plan: dict, decisions: dict, extras: list[dict], screens: list[dict],
                signal_of: dict) -> list[dict]:
    """Plan groups first (in plan order), then curated extras. Absorbed findings stay evidence only."""
    by_fp = {f["fingerprint"]: f for f in findings if not f.get("absorbed_by")}
    page_ids = {s["page_id"] for s in screens}
    number = {s["page_id"]: s["screen"] for s in screens}
    question_pages = {q["id"]: s["page_id"] for s in screens for q in s.get("questions", [])}
    items = []
    for tier in TIERS:
        for group in plan.get(tier, []):
            members = [by_fp[fp] for fp in group["fingerprints"] if fp in by_fp]
            if not members:
                continue
            pages = list(dict.fromkeys(p for m in members if (p := _page_of(m, question_pages, page_ids))))
            pages.sort(key=number.get)
            lead = members[0]
            kind = action_kind_of(lead)
            items.append({"id": group["id"], "kind": "finding",
                          "state": worst_state(finding_state(m) for m in members),
                          **_handling([decisions.get(m["fingerprint"]) for m in members]),
                          "action_kind": kind,
                          "has_paste": kind == "paste" and bool(lead.get("suggested_text") or lead.get("options")),
                          "headline": members[0]["headline"],
                          "location": group_label(members, screens),
                          "signal": signal_of.get(members[0]["criterion_id"]),
                          "criterion_id": members[0]["criterion_id"],
                          "fingerprints": [m["fingerprint"] for m in members], "count": len(members),
                          **_where(pages, [number[p] for p in pages]),
                          **_group_instruction(members, screens)})
    for extra in extras:
        items.append({"id": extra["fingerprint"], "kind": extra["kind"], "state": extra["state"],
                      **_handling([decisions.get(extra["fingerprint"])]), "action_kind": "you_check",
                      "has_paste": False, "headline": extra["title"],
                      "location": extra["where"], "signal": extra["signal"], "criterion_id": None,
                      "instruction": extra["instruction"], "fingerprints": [extra["fingerprint"]],
                      "count": 1, **_where(list(extra["pages"]), list(extra["screens"]))})
    return items
