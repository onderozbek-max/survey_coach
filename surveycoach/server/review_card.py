"""The "Review summary" card at the top of the downloadable summary (brief 4.7): the audit trail in one place.

Survey, link, version, verdict, what was open, time, when it was checked, who signed off, and the completed
You check list with who and when. Everything is escaped and nothing is fetched: inline text only. The link is
shown as plain text, origin and path only.
"""
from __future__ import annotations

from html import escape

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


def _checks(detail: dict) -> list[str]:
    state = detail.get("signoff") or {}
    listed = (state.get("record") or {}).get("you_check")
    if listed is None:
        # Not signed yet: the same list, read live (nobody has vouched for it, so no name).
        by_id = {i["id"]: i for i in (detail.get("overview") or {}).get("items", [])}
        listed = [{"title": c["title"], "where": c["where"], "who": None, "at": None,
                   "status": {"done": "done", "keep": "kept"}.get((by_id.get(c["fingerprint"]) or {}).get("handled_kind"), "open")}
                  for c in (detail.get("overview") or {}).get("you_check", [])]
    if not listed:
        return []
    rows = []
    for check in listed:
        who = f" · {_text(check['who'])}" if check.get("who") else ""
        when = f" · {_text(check['at'])}" if check.get("at") else ""
        rows.append(f"<li><strong>{_text(check['title'])}</strong> ({_text(check['where'])}) · "
                    f"{_text(check['status'].capitalize())}{who}{when}</li>")
    return ["<h3>Checked by hand</h3><ul>", *rows, "</ul>"]


def review_card(detail: dict) -> list[str]:
    """HTML lines for the card; empty when there is no finished review to summarise."""
    verdict = (detail.get("overview") or {}).get("verdict")
    if not verdict:
        return []
    tiles = verdict["tiles"]
    link = public_link((detail.get("snapshot") or {}).get("source_url"))
    finished = utc_iso(((detail.get("job") or {}).get("finished_at")))
    rows = [("Survey", detail["title"]), ("Version", f"Version {detail['version']}"),
            *([("Link", link)] if link else []), ("Verdict", verdict["headline"]),
            ("Open", f"Fix {tiles['fix']} · Improve {tiles['improve']} · You check {tiles['you_check']}"),
            ("Time", verdict["time"]["label"]), *([("Checked", finished)] if finished else [])]
    lines = ["<section><h2>Review summary</h2><dl>",
             *(f"<dt>{_text(name)}</dt><dd>{_text(value)}</dd>" for name, value in rows),
             f"<dt>Sign-off</dt><dd>{_signoff_line(detail.get('signoff'))}</dd></dl>", *_checks(detail)]
    delta = detail.get("version_delta")
    if delta and delta["fixed"]:
        lines += [f"<h3>Fixed since v{_text(delta['from_version'])}</h3><ul>",
                  *(f"<li>{_text(f['location'])}: {_text(f['headline'])}</li>" for f in delta["fixed"]), "</ul>"]
    return [*lines, "</section>"]
