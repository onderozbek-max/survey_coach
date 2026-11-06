"""One review, one story (3E): the Sign off card, the Slack post, the downloadable summary and the Verdict headline
are built from the same detail, so they must agree on name, version, verdict, open counts, what was checked by hand
and what was kept on purpose. A REAL review in a temporary database: decisions, You check ticks, a keep reason and
a sign-off are all made through the server's own routes. Offline; the page is the real site served by the real app.

Root cause this guards (see .superpowers/sdd/impl-3e-signoff.md): the card, the post and the summary each picked
their own facts. Real divergences were the survey name ("Surveys" vs "Untitled survey") and the Checked by hand
list (the card listed every You check row, the post only the ticked ones).
"""
import html as htmllib
import re
import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from concept_fixture import concept_survey
from review_helpers import save_review
from surveycoach.server import create_app
from tests.test_site_e2e import browser

LINK = "https://app.redjade.net/s/sunrise?token=SECRET123"
NUMERIC_LINK = "https://app.redjade.net/s/12345?token=SECRET123"
REASON = "Checked in the editor"
CASES = {"named-v1": ("Sunrise Skillet Concept Test", 1), "generic-title-v1": ("Surveys", 1),
         "named-v2": ("Sunrise Skillet Concept Test", 2)}


def snapshot(title):
    # A numeric address gives the server nothing to name the survey from, so "Surveys" stays the stored title.
    link = NUMERIC_LINK if title == "Surveys" else LINK
    return concept_survey().model_copy(update={"title": title, "source_url": link})


def decide(client, survey_id, version, fingerprint, body):
    response = client.put(f"/api/surveys/{survey_id}/versions/{version}/decisions/{fingerprint}", json=body)
    assert response.status_code == 200, response.text


def build(db, title, version):
    """A saved review with two You check items ticked, one kept with a reason, one finding kept, the rest open, signed."""
    app = create_app(db)
    with TestClient(app, base_url="http://localhost") as client:
        survey_id = save_review(app.state.repository, snapshot(title))
        if version == 2:
            assert save_review(app.state.repository, snapshot(title + " revised"), survey_id) == survey_id
        items = client.get(f"/api/surveys/{survey_id}/versions/{version}").json()["overview"]["items"]
        checks = [i for i in items if i["kind"] == "you_check"]
        finding = next(i for i in items if i["kind"] != "you_check" and i["state"] == "worth_improving")
        assert len(checks) >= 4
        for check in checks[:2]:
            decide(client, survey_id, version, check["id"], {"action": "done"})
        decide(client, survey_id, version, checks[2]["id"], {"action": "keep", "keep_reason": "owner_decided", "reason": REASON})
        for fingerprint in finding["fingerprints"]:            # a grouped card is handled when every finding in it is
            decide(client, survey_id, version, fingerprint,
                   {"action": "keep", "keep_reason": "owner_decided", "reason": "Matches last wave"})
        response = client.post(f"/api/surveys/{survey_id}/versions/{version}/signoff", json={"name": "Priya N", "acknowledge_open": True})
        assert response.status_code == 201, response.text
        return survey_id


@pytest.fixture(params=list(CASES), ids=list(CASES))
def served(request, tmp_path):
    title, version = CASES[request.param]
    db = tmp_path / "consistency.sqlite3"
    survey_id = build(db, title, version)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(create_app(db), log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.03)
    yield f"http://127.0.0.1:{sock.getsockname()[1]}", survey_id, version, title
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()


def expected(detail, title):
    """What the story must be, read straight from the stored detail and the title that was saved: no code under test."""
    items = detail["overview"]["items"]
    shown_title = "Untitled survey" if title == "Surveys" else title + (" revised" if detail["version"] == 2 else "")
    checked = [i["headline"] for i in items if i["kind"] == "you_check" and i.get("handled_kind") == "done"]
    kept = [i["headline"] for i in items if i.get("handled_kind") == "keep"]
    assert len(checked) == 2 and len(kept) == 2          # the scenario: 2 ticked by hand, 2 kept on purpose
    tiles = detail["overview"]["verdict"]["tiles"]
    words = [f"{tiles[k]} {w}" for k, w in (("fix", "to fix"), ("improve", "to improve"), ("you_check", "to check")) if tiles[k]]
    return {"name": shown_title, "version": detail["version"], "headline": detail["overview"]["verdict"]["headline"],
            "checked": checked, "kept": kept, "open": " · ".join(words) or "Nothing open"}


def slack_surface(post):
    lines = post.splitlines()
    name, version = re.fullmatch(r"Survey review: (.*) \(v(\d+)\)", lines[0]).groups()
    headline = lines[1].removeprefix("Verdict: ").rsplit(" · ~", 1)[0]
    checked = next(l for l in lines if l.startswith("Checked by hand: ")).removeprefix("Checked by hand: ").split(", ")
    kept_line = next(l for l in lines if "Kept on purpose: " in l).split("Kept on purpose: ", 1)[1]
    entries = re.fullmatch(r"(\d+) \((.*)\)", kept_line).group(2).split("; ")
    return {"name": name, "version": int(version), "headline": headline, "checked": checked,
            "kept": [e.split(": ", 1)[1].split(" – ")[0] for e in entries]}, [e.split(" – ")[1] for e in entries]


def _list_after(html, heading):
    block = re.search(rf"<h3>{heading}</h3><ul>(.*?)</ul>", html, re.S)
    return [htmllib.unescape(t) for t in re.findall(r"<strong>(.*?)</strong>", block.group(1))] if block else []


def html_surface(html):
    card = html[html.index("<h2>Review summary</h2>"):]
    facts = {htmllib.unescape(k): htmllib.unescape(v) for k, v in re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", card)}
    return {"name": facts["Survey"], "version": int(facts["Version"].removeprefix("Version ")), "headline": facts["Verdict"],
            "checked": _list_after(card, "Checked by hand"), "kept": _list_after(card, "Kept on purpose")}, facts


def card_surface(page):
    rows = page.locator("#review-card dl").evaluate("dl => [...dl.querySelectorAll('dt')].map(dt => [dt.textContent, dt.nextElementSibling.textContent])")
    facts = dict(rows)
    texts = lambda label: page.locator(f'#review-card [aria-label="{label}"] li strong').all_inner_texts()
    return {"name": facts["Survey"], "version": int(facts["Version"].removeprefix("v")),
            "headline": page.locator("#review-card .headline").inner_text(),
            "checked": texts("Checked by hand"), "kept": texts("Kept on purpose")}, facts


def test_every_surface_tells_the_same_story(browser, served):
    base, survey_id, version, title = served
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{base}/review.html?id={survey_id}&version={version}#share")
    page.wait_for_function("SC.reviewReady === true")
    detail = page.evaluate(f"fetch('/api/surveys/{survey_id}/versions/{version}').then(r => r.json())")
    want = expected(detail, title)
    post = detail["share"]["slack_post"]

    card, card_facts = card_surface(page)
    assert page.locator("#slack-post").inner_text() == post                      # the preview is the post, not a rebuild
    slack, reasons = slack_surface(post)
    summary = page.evaluate(f"fetch('{detail['share']['summary_url']}').then(r => r.text())")
    html, html_facts = html_surface(summary)

    for surface_name, surface in (("card", card), ("slack post", slack), ("html summary", html)):
        for key in ("name", "version", "headline", "checked", "kept"):
            assert surface[key] == want[key], f"{surface_name} disagrees on {key}: {surface[key]!r} != {want[key]!r}"
    assert all(REASON in r or "Matches last wave" in r for r in reasons)
    assert card_facts["Open"].startswith(want["open"]) and html_facts["Open"].startswith(want["open"])
    assert page.locator("#signoff-open").inner_text() == f"Open now: {want['open']}" or want["open"] == "Nothing open"
    assert "SECRET123" not in summary and "SECRET123" not in post

    page.goto(f"{base}/review.html?id={survey_id}&version={version}#overview")     # the Verdict page says the same headline
    page.wait_for_function("SC.reviewReady === true")
    assert page.locator("#overview-h").inner_text() == want["headline"]
    assert not errors
    context.close()
