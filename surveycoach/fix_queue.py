"""The one ordered list of items behind the fix list, 'N of M done' and 'Next item'.

Built only from `items.build_items` output, so the tiles, cards, markers, verdict and this list can
never disagree. Order: Fix before launch, then Worth improving, then You check; inside a state,
screen order (whole-survey items last); ties keep the plan's order. Handled items stay in the list
(ticked), so M is the total and N the handled ones.
"""
from __future__ import annotations

from surveycoach.status import DONE, KEEP, STATES, USE

_NO_SCREEN = float("inf")


def _sort_key(item: dict) -> tuple:
    screens = item.get("screens") or []
    return STATES.index(item["state"]), screens[0] if screens else _NO_SCREEN


def _entry(item: dict) -> dict:
    """The fields a list row needs. Optional ones default so a bare item still projects."""
    pages, screens = item.get("pages") or [], item.get("screens") or []
    return {"id": item["id"], "fingerprints": item.get("fingerprints") or [item["id"]], "kind": item.get("kind"),
            "state": item["state"], "open": item["open"], "handled_kind": item.get("handled_kind"),
            "unverified": item.get("unverified", False), "keep_reason": item.get("keep_reason"),
            "screen": screens[0] if screens else None, "page_id": pages[0] if pages else None,
            "screens": screens, "pages": pages, "title": item.get("headline"), "location": item.get("location"),
            "action_kind": item.get("action_kind"), "has_paste": item.get("has_paste", False),
            "count": item.get("count", 1), "next_open_id": None}


def build_queue(items: list[dict]) -> dict:
    """Ordered entries (each with `next_open_id`) plus counts derived from them alone."""
    entries = [_entry(item) for item in sorted(items, key=_sort_key)]   # sorted() is stable
    upcoming = None
    for entry in reversed(entries):
        entry["next_open_id"] = upcoming
        if entry["open"]:
            upcoming = entry["id"]
    handled = [e for e in entries if not e["open"]]
    return {"items": entries, "first_open_id": upcoming,
            "counts": {"done": len(handled), "total": len(entries), "open": len(entries) - len(handled),
                       "unverified": sum(e["unverified"] for e in handled),
                       "by_kind": {kind: sum(e["handled_kind"] == kind for e in handled)
                                   for kind in (USE, DONE, KEEP)}}}
