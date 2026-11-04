"""Standalone stakeholder packets: synthetic data and temporary databases only."""
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import re

import pytest
from fastapi.testclient import TestClient

from surveycoach.server import create_app
from surveycoach.server.report import summary_packet
from surveycoach.server.present import enrich
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot
from test_committee_rounds import detail, finding, snapshot


class PacketParser(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.tags = []
        self.attrs = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)


def packet_detail():
    findings = [finding(key) for key in ("picked", "kept", "open", "stale", "original")]
    findings[0]["suggested_text"] = "How do you like it?"
    data = detail(findings=findings, decisions={
        "picked": {"action": "pick", "picked_text": "How do you like it?"},
        "kept": {"action": "keep", "reason": 'Tracker <reason> & "history"'},
        "stale": {"action": "pick", "picked_text": "Obsolete choice"},
        "original": {"action": "original"},
    })
    data.update(title='Research <title> & "team"', total_seconds=120)
    return enrich(data, load_rubric())


def test_download_contains_ordered_member_story_and_only_explicit_changes():
    data = packet_detail()
    before = deepcopy(data)
    body = summary_packet(data, download=True)
    assert data == before
    assert escape(data["overview"]["headline"]) in body
    sections = ["Headline", "Member experience", "Changes chosen", "Kept on purpose",
                "Still open", "What we checked / not checked"]
    assert [body.index(f"<h2>{name}</h2>") for name in sections] == sorted(
        body.index(f"<h2>{name}</h2>") for name in sections)
    for signal in data["overview"]["signals"]:
        assert escape(signal["name"]) in body
        assert escape(signal["label"]) in body
    assert "<del>did</del>" in body and "<ins>do</ins>" in body
    assert "Obsolete choice" not in body
    assert escape('Tracker <reason> & "history"') in body
    assert 'Research &lt;title&gt; &amp; &quot;team&quot;' in body
    assert "2 findings still need a choice" in body
    assert "AI wording review was not requested" in body
    assert "Unvisited branches and uncaptured screens were not checked" in body
    assert "not launch approval" in body
    assert "estimate" in body
    for phrase in ("actually finish", "completion rate", "drop-off rate", "will finish",
                   "guarantee", "approved for launch", "launch-ready"):
        assert phrase not in body.lower()
    for token in ("#F7F8FA", "#FFFFFF", "#0F1B2D", "#5B6B80", "#0067A0"):
        assert token in body


def test_download_is_passive_escaped_and_self_contained():
    data = packet_detail()
    attack = '<script>alert("x")</script><img src="https://evil.test/pixel"> &'
    data["title"] = attack
    data["overview"]["headline"] = attack
    data["overview"]["signals"][0]["summary"] = attack
    data["decisions"]["kept"]["reason"] = attack
    body = summary_packet(data, download=True)
    parsed = PacketParser(body)
    assert not {"script", "img", "link", "iframe", "object", "embed", "a"} & set(parsed.tags)
    assert not any(name.lower().startswith("on") or name in {"src", "href"}
                   for name, _ in parsed.attrs)
    assert "&lt;script&gt;" in body
    # User URLs may remain escaped text, never active resources; no app URLs are added.
    assert "url(" not in body.lower() and "@import" not in body.lower()
    assert "https://" not in summary_packet(packet_detail(), download=True)


@pytest.mark.parametrize("title, slug", [
    ('A / Survey: "Team"', "a-survey-team"),
    ('../../evil\\name\r\nInjected: yes', "evil-name-injected-yes"),
    ("你好 ", "survey"),
    ("X" * 1000, "x" * 80),
])
def test_attachment_filename_is_bounded_ascii_and_inline_is_unchanged(tmp_path, title, slug):
    with TestClient(create_app(tmp_path / "test.db"), base_url="http://localhost") as client:
        created = client.post("/api/surveys", json={"snapshot": snapshot(title=title)}).json()
        url = f"/api/surveys/{created['id']}/versions/1"
        data = client.get(url).json()
        inline = client.get(url + "/summary")
        downloaded = client.get(url + "/summary?download=1")
        assert downloaded.status_code == 200
        assert downloaded.headers["content-disposition"] == (
            f'attachment; filename="surveycoach-{slug}-v1.html"')
        assert downloaded.headers["content-type"].startswith("text/html")
        assert "default-src 'none'" in downloaded.headers["content-security-policy"]
        assert "content-disposition" not in inline.headers
        assert inline.text == summary_packet(data)
        assert client.get(url + "/summary?download=0").text == inline.text
        assert "Member experience" in downloaded.text
        assert re.fullmatch(r'[ -~]+', downloaded.headers["content-disposition"])


def test_no_review_is_unknown_not_a_clean_bill_of_health(tmp_path):
    app = create_app(tmp_path / "test.db")
    created = app.state.repository.submit(
        SurveySnapshot.model_validate(snapshot()),
        ai=False)
    with TestClient(app, base_url="http://localhost") as client:
        body = client.get(f"/api/surveys/{created['id']}/versions/1/summary?download=1").text
        assert body.count("Not checked yet") >= 6
        assert "Review not available" in body
        assert "No must-fixes found" not in body


def test_add_answer_has_insertion_without_deleting_question():
    data = packet_detail()
    data["review"]["findings"][0].update(edit_kind="add_answer", structural=True)
    body = summary_packet(data, download=True)
    assert "Keep question:" in body and "Add answer option:" in body
    assert "<ins>How do you like it?</ins>" in body
    assert "<del>" not in body
    assert "not a verified text replacement" in body
