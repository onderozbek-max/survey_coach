"""One reading of a finished review for every place that summarises it (3E).

The Sign off card, the Slack post and the downloadable summary each used to pick their own facts out of the detail,
so they could disagree: the card listed three "checked by hand" items where the post listed one, and a survey called
"Surveys" was "Untitled survey" on one and "Surveys" on the other. They now all start from `review_facts(detail)`:
name, version, verdict, what is open, what was checked by hand, what is still to check, what was kept on purpose and
what was fixed. Nothing here is written for one surface; each surface only chooses how to lay the same facts out.
"""
from __future__ import annotations

from surveycoach.reader.naming import is_generic_title
from surveycoach.status import keep_text

UNTITLED = "Untitled survey"
_OPEN_WORDS = (("fix", "to fix"), ("improve", "to improve"), ("you_check", "to check"))


def survey_name(title: str | None) -> str:
    """The survey's own name, or the plain placeholder when all there is is RedJade's page title ("Surveys")."""
    text = (title or "").strip()
    return UNTITLED if is_generic_title(text) or text.casefold() == "untitled" else text


def open_text(tiles: dict | None) -> str:
    """'1 to improve · 8 to check'; zero everywhere means nothing is left."""
    parts = [f"{tiles[key]} {words}" for key, words in _OPEN_WORDS if (tiles or {}).get(key, 0) > 0]
    return " · ".join(parts) or "Nothing open"


def _signed_check_rows(detail: dict) -> dict:
    record = (detail.get("signoff") or {}).get("record") or {}
    return {row["fingerprint"]: row for row in record.get("you_check") or []}


def _checked(items: list[dict], signed: dict) -> list[dict]:
    rows = []
    for item in items:
        if item.get("kind") != "you_check" or item.get("handled_kind") != "done":
            continue
        who = signed.get(item["id"]) or {}
        rows.append({"title": item["headline"], "where": item.get("location"),
                     "who": who.get("who"), "at": who.get("at")})
    return rows


def _kept(detail: dict, items: list[dict]) -> list[dict]:
    decisions = detail.get("decisions") or {}
    return [{"where": item.get("location"), "headline": item["headline"],
             "reason": keep_text(decisions.get(item["fingerprints"][0]) or {})}
            for item in items if item.get("handled_kind") == "keep"]


def _fixed(detail: dict) -> dict | None:
    delta = detail.get("version_delta")
    fixed = (delta or {}).get("fixed") or []
    if not fixed:
        return None
    return {"from_version": delta["from_version"],
            "items": [{"where": f["location"], "headline": f["headline"]} for f in fixed]}


def review_facts(detail: dict) -> dict | None:
    """The shared facts for this version, or None before a check has finished (there is nothing to say yet)."""
    overview = detail.get("overview") or {}
    verdict = overview.get("verdict")
    if not verdict:
        return None
    items = overview.get("items") or []
    progress = verdict.get("progress") or {}
    return {"name": survey_name(detail.get("title")), "version": detail["version"],
            "verdict": {"kind": verdict["kind"], "headline": verdict["headline"]},
            "open": {**{key: verdict["tiles"][key] for key, _ in _OPEN_WORDS}, "text": open_text(verdict["tiles"]),
                     "handled": progress.get("done"), "total": progress.get("total")},
            "checked_by_hand": _checked(items, _signed_check_rows(detail)),
            "still_to_check": [{"title": i["headline"], "where": i.get("location")} for i in items
                               if i.get("kind") == "you_check" and i.get("open")],
            "kept": _kept(detail, items), "fixed": _fixed(detail)}
