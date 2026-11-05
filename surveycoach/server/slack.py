"""The Slack post (brief 4.7): plain text in the team's channel convention, built only from stored data.

    Survey review: Quesadilla Tray concept test (v2)
    Verdict: Ready for sign-off · ~6 min
    Fixed since v1: 4 (Q1: Reading level is high; ...) · Kept on purpose: 1 (Q4: List length – Owner decided: ...)
    Checked by hand: Images load on a phone, Concept order is randomized
    Link: https://app.redjade.net/survey/...

Lines with nothing to say are left out, never written as "none". Everything a person or a vendor typed is
folded to one line and escaped for Slack, and any URL keeps its origin and path only: a query or fragment can
carry an access token, so it never leaves this module. Copy only; nothing here talks to Slack.
"""
from __future__ import annotations

import re
from urllib.parse import quote, urlsplit

from surveycoach.safe_text import one_line
from surveycoach.status import keep_text
from surveycoach.verdict import minutes_text

LIST_MAX = 3
_URL = re.compile(r"https?://[^\s<>\"'`)\]]+", re.I)
_MENTION = re.compile(r"@(?=(?:here|channel|everyone)\b)", re.I)
_PATH_SAFE = "/%:@!$&'()*+,;=-._~"


def public_link(url: str | None) -> str | None:
    """Origin and path only (no credentials, query or fragment), or None when it is not a usable web link."""
    try:
        parts = urlsplit((url or "").strip())
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host:
        return None
    host = f"[{host}]" if ":" in host else host
    return f"{parts.scheme}://{host}{f':{port}' if port else ''}{quote(parts.path, safe=_PATH_SAFE)}"


def scrub_urls(text: str) -> str:
    """Every URL inside free text, cut down to `public_link`."""
    return _URL.sub(lambda m: public_link(m.group()) or "(link removed)", text)


def slack_escape(value: str | None) -> str:
    """One line of Slack-safe text: no markup or mention can be smuggled in, no token can ride along."""
    text = scrub_urls(one_line(value))
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "'")
    return _MENTION.sub("@\u200b", text)


def _short(where: str | None) -> str:
    """'Q4 · Screen 5' -> 'Q4'; whole-survey and screen-only places stay as they are."""
    return (where or "Whole survey").split(" · ")[0]


def _listed(entries: list[str]) -> str:
    more = len(entries) - LIST_MAX
    return "; ".join(entries[:LIST_MAX]) + (f"; +{more} more" if more > 0 else "")


def _fixed(detail: dict) -> str | None:
    delta = detail.get("version_delta")
    fixed = (delta or {}).get("fixed") or []
    if not fixed:
        return None
    names = [f"{slack_escape(_short(f['location']))}: {slack_escape(f['headline'])}" for f in fixed]
    return f"Fixed since v{delta['from_version']}: {len(fixed)} ({_listed(names)})"


def _kept(detail: dict) -> str | None:
    items = [i for i in detail["overview"]["items"] if i.get("handled_kind") == "keep"]
    if not items:
        return None
    names = []
    for item in items:
        reason = keep_text((detail.get("decisions") or {}).get(item["fingerprints"][0]) or {})
        names.append(f"{slack_escape(_short(item['location']))}: {slack_escape(item['headline'])}"
                     + (f" – {slack_escape(reason)}" if reason else ""))
    return f"Kept on purpose: {len(items)} ({_listed(names)})"


def _checked(detail: dict) -> str | None:
    done = [i["headline"] for i in detail["overview"]["items"]
            if i["kind"] == "you_check" and i.get("handled_kind") == "done"]
    return "Checked by hand: " + ", ".join(slack_escape(t) for t in done) if done else None


def _time(verdict: dict) -> str:
    time = verdict["time"]
    text = minutes_text(time["minutes"]).replace(" minutes", " min").replace(" minute", " min")
    return f"~{text}" + (" (varies by route)" if time.get("path_uncertain") else "")


def slack_post(detail: dict) -> str | None:
    """The post for this version, or None before a check has finished (there is nothing to say yet)."""
    verdict = (detail.get("overview") or {}).get("verdict")
    if not verdict:
        return None
    link = public_link((detail.get("snapshot") or {}).get("source_url"))
    middle = " · ".join(part for part in (_fixed(detail), _kept(detail)) if part)
    lines = [f"Survey review: {slack_escape(detail['title'])} (v{detail['version']})",
             f"Verdict: {slack_escape(verdict['headline'])} · {_time(verdict)}",
             middle, _checked(detail) or "", f"Link: {link}" if link else ""]
    return "\n".join(line for line in lines if line)


def share_payload(detail: dict) -> dict:
    """What the Sign off page needs besides the sign-off itself: the post, the safe link, the download route."""
    return {"slack_post": slack_post(detail),
            "link": public_link((detail.get("snapshot") or {}).get("source_url")),
            "summary_url": f"/api/surveys/{detail['id']}/versions/{detail['version']}/summary?download=true"}
