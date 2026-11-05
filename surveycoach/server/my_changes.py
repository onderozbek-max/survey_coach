"""'My changes': the accepted text changes, in the order a researcher meets them in RedJade.

One source for what the screen lists and what 'Copy all' puts on the clipboard: both come from the
items built here (`copy_all_text` is the items' own `copy_text`, joined). Only a `pick` decision is
a change: kept, marked-done and merely previewed suggestions are never listed.
Supersedes the browser-side change sheet text; the browser must show this and not rebuild it.
"""
from __future__ import annotations

from surveycoach.server.rounds import FIELD_ORDER, NEW_ANSWER, decided_findings, field_location, field_part

UNKNOWN_BEFORE = "(not found in the saved survey)"
NEW_ANSWER_BEFORE = "(nothing: this adds a new answer)"
_LAST = float("inf")


def _change(finding: dict, decision: dict, place: dict | None, wording: str | None, screens: list[dict]) -> dict:
    screen = next((s for s in screens if place and s["page_id"] == place["page_id"]), None)
    question = (place or {}).get("question")
    label = next((q["label"] for q in (screen or {}).get("questions", []) if question and q["id"] == question["id"]), None)
    adds = finding.get("edit_kind") == "add_answer"
    field, number = (NEW_ANSWER, 0) if adds and question else field_part(place, wording)
    before = None if adds or place is None else wording
    after = decision["picked_text"]
    where = finding.get("field_location") or field_location(finding, place, screens) or "RedJade > Survey overall"
    shown = NEW_ANSWER_BEFORE if adds else UNKNOWN_BEFORE if before is None else before
    return {"fingerprint": finding["fingerprint"], "headline": finding.get("headline"),
            "screen": screen["screen"] if screen else None, "page_id": place["page_id"] if place else None,
            "page_label": screen["name"] if screen else None,
            "screen_label": place["screen_label"] if place else "Survey overall",
            "question_id": question["id"] if question else None, "question_label": label,
            "field": field, "field_location": where, "before": before, "after": after,
            "edit_kind": finding.get("edit_kind", "rewrite"),
            "copy_text": f"{where}\nBefore: {shown}\nAfter: {after}",
            "_order": (screen["screen"] if screen else _LAST, -1 if place and place["slot"] is None else
                       (place or {}).get("slot", _LAST), FIELD_ORDER.index(field), number)}


def build_my_changes(detail: dict) -> dict:
    """Accepted changes (screen order, then question, then question text, help text, answers) and copy-all text."""
    screens = detail.get("screens") or []
    changes = [_change(f, d, place, wording, screens)
               for f, d, place, wording in decided_findings(detail, {"pick"}) if (d.get("picked_text") or "").strip()]
    changes.sort(key=lambda change: change["_order"])
    for change in changes:
        del change["_order"]
    return {"items": changes, "count": len(changes),
            "copy_all_text": "\n\n".join(change["copy_text"] for change in changes)}
