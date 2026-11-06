"""The "Review summary" card at the top of the downloadable summary (brief 4.7): the audit trail in one place.

Survey, link, version, verdict, what was open, time, when it was checked, who signed off, what was checked by hand,
what is still to check and what was kept on purpose. All of it is laid out from `review_facts` (the same facts the
Sign off card and the Slack post use). Everything is escaped and nothing is fetched: inline text only. The link is
shown as plain text, origin and path only.
"""
from __future__ import annotations

from html import escape

from surveycoach.server.review_facts import review_facts
from surveycoach.server.signoff import utc_iso
from surveycoach.server.slack import public_link


def _text(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _signoff_line(state: dict) -> str:
    if not state or not state.get("signed"):
        return "Not signed off yet"
    record = state["record"]
    line = f"Signed off by {_text(record['name'])} on {_text(record['signed_at'])}"
    if record["acknowledged_open"]:
        line += f", with {len(record['open_items'])} open item(s) acknowledged"
    return line + (". Changed since." if state["changed_since"] else ".")


def _list(heading: str, rows: list[str]) -> list[str]:
    return [f"<h3>{heading}</h3><ul>", *(f"<li>{row}</li>" for row in rows), "</ul>"] if rows else []


def _checked(row: dict) -> str:
    who = f" · {_text(row['who'])}" if row.get("who") else ""
    when = f" · {_text(row['at'])}" if row.get("at") else ""
    return f"<strong>{_text(row['title'])}</strong> ({_text(row['where'])}) · Done{who}{when}"


def _lists(facts: dict) -> list[str]:
    fixed = facts["fixed"]
    return [*_list("Checked by hand", [_checked(r) for r in facts["checked_by_hand"]]),
            *_list("Still to check", [f"<strong>{_text(r['title'])}</strong> ({_text(r['where'])})" for r in facts["still_to_check"]]),
            *_list("Kept on purpose", [f"<strong>{_text(k['headline'])}</strong> ({_text(k['where'])})"
                                       + (f" · {_text(k['reason'])}" if k["reason"] else "") for k in facts["kept"]]),
            *(_list(f"Fixed since v{_text(fixed['from_version'])}",
                    [f"{_text(f['where'])}: {_text(f['headline'])}" for f in fixed["items"]]) if fixed else [])]


def review_card(detail: dict) -> list[str]:
    """HTML lines for the card; empty when there is no finished review to summarise."""
    facts = review_facts(detail)
    if not facts:
        return []
    verdict = detail["overview"]["verdict"]
    link = public_link((detail.get("snapshot") or {}).get("source_url"))
    finished = utc_iso(((detail.get("job") or {}).get("finished_at")))
    opened = facts["open"]
    handled = f" · {opened['handled']} of {opened['total']} handled" if opened["total"] else ""
    rows = [("Survey", facts["name"]), ("Version", f"Version {facts['version']}"),
            *([("Link", link)] if link else []), ("Verdict", facts["verdict"]["headline"]),
            ("Open", opened["text"] + handled), ("Time", verdict["time"]["label"]),
            *([("Checked", finished)] if finished else [])]
    return ["<section><h2>Review summary</h2><dl>",
            *(f"<dt>{_text(name)}</dt><dd>{_text(value)}</dd>" for name, value in rows),
            f"<dt>Sign-off</dt><dd>{_signoff_line(detail.get('signoff'))}</dd></dl>", *_lists(facts), "</section>"]
