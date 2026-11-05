"""Sign-off (brief 4.7): "I've reviewed this survey", recorded locally with a name and a server clock.

One record per sign-off, appended to a log nobody can edit, keyed by version. A version's state is its latest
record; a new version has none, so a recheck starts "not signed" and the earlier records stay in `history`.
A survey that still has open items can be signed only when the signer says so (`acknowledge_open`); the open
items are then written into the record verbatim and are never hidden. Nothing here proves a review happened:
the record says who said so, when, and what was open at that moment.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from surveycoach.safe_text import one_line
from surveycoach.status import keep_text

NAME_MAX = 80
READY = "ready_for_signoff"


def clean_name(value) -> str:
    if not isinstance(value, str):
        raise ValueError("Supply your name as text")
    name = one_line(value)
    if not name or len(name) > NAME_MAX:
        raise ValueError(f"Supply a name of 1 to {NAME_MAX} characters")
    return name


def now_iso() -> str:
    """The server's clock, never the client's."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_iso(sqlite_timestamp: str | None) -> str | None:
    """SQLite's 'YYYY-MM-DD HH:MM:SS' (UTC) in the same ISO form as `now_iso`."""
    return sqlite_timestamp.replace(" ", "T") + "Z" if sqlite_timestamp else None


class SignoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    acknowledge_open: StrictBool = False

    @model_validator(mode="after")
    def valid_name(self):
        self.name = clean_name(self.name)
        return self


def _counts(detail: dict) -> dict:
    """The numbers a sign-off stands on: open per state, done and total, and how many 'done' are unchecked."""
    queue = (detail.get("queue") or {}).get("counts", {})
    tiles = ((detail.get("overview") or {}).get("verdict") or {}).get("tiles", {})
    return {**tiles, "done": queue.get("done", 0), "total": queue.get("total", 0),
            "unverified": queue.get("unverified", 0)}


def _you_check(detail: dict, name: str, decided_at: dict) -> list[dict]:
    overview = detail["overview"]
    by_id = {item["id"]: item for item in overview["items"]}
    listed = []
    for check in overview.get("you_check", []):
        kind = (by_id.get(check["fingerprint"]) or {}).get("handled_kind")
        status = "done" if kind == "done" else "kept" if kind == "keep" else "open"
        decision = (detail.get("decisions") or {}).get(check["fingerprint"]) or {}
        listed.append({"id": check["id"], "fingerprint": check["fingerprint"], "title": check["title"],
                       "where": check["where"], "status": status,
                       "reason": keep_text(decision) if status == "kept" else None,
                       # There are no accounts: whoever signs vouches for the list, and the time is the decision's.
                       "who": name if status != "open" else None,
                       "at": decided_at.get(check["fingerprint"]) if status != "open" else None})
    return listed


def build_record(detail: dict, name: str, acknowledge_open: bool, decided_at: dict, signed_at: str) -> dict:
    """The record to store, or ValueError when this version cannot be signed yet."""
    overview = detail.get("overview") or {}
    verdict = overview.get("verdict")
    if not verdict:
        raise ValueError("There is nothing to sign off yet: the check has not finished for this version")
    open_items = [item for item in overview["items"] if item["open"]]
    if verdict["kind"] != READY and not acknowledge_open:
        many = len(open_items) != 1
        raise ValueError(f"This survey is not ready for sign-off: {len(open_items)} "
                         f"{'items are' if many else 'item is'} still open. Finish them, or sign off with them open.")
    return {"name": name, "signed_at": signed_at, "version": detail["version"], "verdict_kind": verdict["kind"],
            "headline": verdict["headline"], "counts": _counts(detail),
            "acknowledged_open": bool(open_items),
            "open_items": [{"id": i["id"], "state": i["state"], "headline": i["headline"], "location": i["location"]}
                           for i in open_items],
            "you_check": _you_check(detail, name, decided_at)}


def signoff_state(detail: dict, rows: list[dict]) -> dict:
    """What the page shows for this version. `rows` are every record of the survey, oldest first."""
    version = detail["version"]
    last = {row["version"]: index for index, row in enumerate(rows)}
    history = [{"version": row["version"], "name": row["name"], "signed_at": row["signed_at"],
                "verdict_kind": row["record"]["verdict_kind"],
                "acknowledged_open": row["record"]["acknowledged_open"], "latest": last[row["version"]] == index}
               for index, row in enumerate(rows)]
    mine = rows[last[version]] if version in last else None
    record = mine["record"] if mine else None
    return {"signed": bool(mine), "version": version,
            "signed_off_by": record["name"] if record else None,
            "signed_off_at": record["signed_at"] if record else None,
            "record": record,
            # Reopening or closing items after signing is shown, not hidden: the record keeps its old numbers.
            "changed_since": bool(record) and record["counts"] != _counts(detail),
            "history": history}
