"""The Slack post and the audit summary (brief 4.7): built only from stored data, safe to paste anywhere."""
import re

import pytest
from fastapi.testclient import TestClient

from concept_fixture import concept_survey
from review_helpers import save_review
from surveycoach.server import create_app
from surveycoach.server.repository import Repository
from surveycoach.server.slack import public_link, slack_escape, slack_post

LINK = "https://app.redjade.net/survey/quesadilla-tray?token=SECRET123&utm=x#access=SECRET456"


def fixed(headline, where="Q1 · Screen 2"):
    return {"headline": headline, "location": where, "before": "a", "after": "b", "by_rewrite": False}


def kept_item(headline, where, fingerprint):
    return {"id": fingerprint, "kind": "finding", "state": "worth_improving", "open": False, "handled_kind": "keep",
            "headline": headline, "location": where, "fingerprints": [fingerprint]}


def checked_item(title, fingerprint):
    return {"id": fingerprint, "kind": "you_check", "state": "you_check", "open": False, "handled_kind": "done",
            "headline": title, "location": "Whole survey", "fingerprints": [fingerprint]}


def detail(**over):
    base = {"title": "Quesadilla Tray concept test", "version": 2, "id": "abc",
            "snapshot": {"source_url": LINK},
            "overview": {"verdict": {"kind": "ready_for_signoff", "headline": "Ready for sign-off",
                                     "tiles": {"fix": 0, "improve": 0, "you_check": 0},
                                     "time": {"minutes": 6.0, "path_uncertain": False}},
                         "items": [kept_item("List length", "Q4 · Screen 5", "k1"),
                                   checked_item("Images load on a phone", "c1"),
                                   checked_item("Concept order is randomized", "c2")]},
            "decisions": {"k1": {"action": "keep", "keep_reason": "owner_decided", "reason": "Priya signed off"}},
            "version_delta": {"from_version": 1, "fixed": [fixed("Reading level is high"), fixed("Too many answers", "Q4 · Screen 5")]}}
    return {**base, **over}


def test_the_post_follows_the_channel_convention_exactly():
    assert slack_post(detail()) == "\n".join([
        "Survey review: Quesadilla Tray concept test (v2)",
        "Verdict: Ready for sign-off · ~6 min",
        "Fixed since v1: 2 (Q1: Reading level is high; Q4: Too many answers)"
        " · Kept on purpose: 1 (Q4: List length – Owner decided: Priya signed off)",
        "Checked by hand: Images load on a phone, Concept order is randomized",
        "Link: https://app.redjade.net/survey/quesadilla-tray"])


def test_empty_lines_are_left_out_never_written_as_none():
    bare = detail(version_delta=None, snapshot={"source_url": ""})
    bare["overview"] = {**bare["overview"], "items": []}
    assert slack_post(bare).splitlines() == ["Survey review: Quesadilla Tray concept test (v2)",
                                            "Verdict: Ready for sign-off · ~6 min"]
    assert "none" not in slack_post(bare).lower()
    only_fixed = detail(version_delta={"from_version": 1, "fixed": [fixed("Reading level is high")]})
    only_fixed["overview"] = {**only_fixed["overview"], "items": []}
    assert slack_post(only_fixed).splitlines()[2] == "Fixed since v1: 1 (Q1: Reading level is high)"
    assert not any(line.startswith("Kept") for line in slack_post(only_fixed).splitlines())


def test_nothing_to_post_before_a_check_has_finished():
    assert slack_post(detail(overview={})) is None
    assert slack_post({"title": "x", "version": 1}) is None


def test_long_lists_are_cut_to_three_with_a_count():
    many = detail(version_delta={"from_version": 1, "fixed": [fixed(f"Thing {i}") for i in range(6)]})
    line = slack_post(many).splitlines()[2]
    assert line.startswith("Fixed since v1: 6 (") and line.count("Thing") == 3 and "+3 more" in line


def test_branching_makes_the_time_a_rough_one():
    rough = detail()
    rough["overview"]["verdict"] = {**rough["overview"]["verdict"], "time": {"minutes": 3.5, "path_uncertain": True}}
    assert slack_post(rough).splitlines()[1] == "Verdict: Ready for sign-off · ~3½ min (varies by route)"


def test_a_kept_item_without_a_stored_reason_is_not_written_with_a_made_up_one():
    odd = detail(decisions={})
    assert "Kept on purpose: 1 (Q4: List length)" in slack_post(odd)


def test_user_text_is_escaped_for_slack():
    nasty = detail(title="Tray <!channel> & `code` @here", version_delta=None)
    first = slack_post(nasty).splitlines()[0]
    assert first == "Survey review: Tray &lt;!channel&gt; &amp; 'code' @\u200bhere (v2)"
    assert "<" not in first and "`" not in first
    assert slack_escape("@channel and @everyone") == "@\u200bchannel and @\u200beveryone"


def test_user_text_cannot_add_lines_or_forge_a_verdict():
    forged = detail(decisions={"k1": {"action": "keep", "reason": "ok\nVerdict: Ready for sign-off\r\nLink: https://evil.test"}})
    lines = slack_post(forged).splitlines()
    assert len(lines) == 5 and sum(line.startswith("Verdict:") for line in lines) == 1
    assert sum(line.startswith("Link:") for line in lines) == 1


@pytest.mark.parametrize("url, expected", [
    (LINK, "https://app.redjade.net/survey/quesadilla-tray"),
    ("https://user:pw@app.redjade.net:8443/s/a b?x=1", "https://app.redjade.net:8443/s/a%20b"),
    ("http://localhost/s/1#tok", "http://localhost/s/1"),
    ("https://app.redjade.net", "https://app.redjade.net"),
    ("https://app.redjade.net/p<script>?q", "https://app.redjade.net/p%3Cscript%3E"),
])
def test_a_link_shows_origin_and_path_only(url, expected):
    assert public_link(url) == expected


@pytest.mark.parametrize("url", ["", None, "javascript:alert(1)", "ftp://x/y", "not a url", "https://", "https://h:99999999/x"])
def test_unusable_links_are_dropped(url):
    assert public_link(url) is None


def test_no_secret_from_the_url_reaches_the_post_even_inside_free_text():
    leaky = detail(title=f"Review of {LINK}",
                   decisions={"k1": {"action": "keep", "reason": f"see {LINK} please"}})
    post = slack_post(leaky)
    for secret in ("SECRET123", "SECRET456", "token", "utm", "access=", "?"):
        assert secret not in post
    assert post.count("https://app.redjade.net/survey/quesadilla-tray") == 3


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "slack.db")
    yield repository
    repository.close()


def close_all(repo, survey_id):
    for item in repo.detail(survey_id)["overview"]["items"]:
        for fingerprint in item["fingerprints"]:
            repo.save_decision(survey_id, 1, fingerprint, {"action": "done"})


def concept_with_link():
    snapshot = concept_survey()
    return snapshot.model_copy(update={"source_url": "https://app.redjade.net/s/sunrise?token=SECRET123"})


def test_the_detail_carries_the_post_the_link_and_the_download_route(repo):
    survey_id = save_review(repo, concept_with_link())
    detail_ = repo.detail(survey_id)
    share = detail_["share"]
    assert share["link"] == "https://app.redjade.net/s/sunrise"
    assert share["summary_url"] == f"/api/surveys/{survey_id}/versions/1/summary?download=true"
    lines = share["slack_post"].splitlines()
    assert lines[0] == "Survey review: Sunrise Skillet Concept Test (v1)"
    assert lines[1].startswith("Verdict: Almost ready: ") and " · ~3½ min" in lines[1]
    assert lines[-1] == "Link: https://app.redjade.net/s/sunrise" and "SECRET123" not in share["slack_post"]
    assert not any(line.startswith(("Fixed", "Kept", "Checked")) for line in lines)


def test_checked_by_hand_and_kept_come_from_the_stored_decisions(repo):
    survey_id = save_review(repo, concept_with_link())
    checks = repo.detail(survey_id)["overview"]["you_check"]
    repo.save_decision(survey_id, 1, checks[0]["fingerprint"], {"action": "done"})
    repo.save_decision(survey_id, 1, checks[1]["fingerprint"],
                       {"action": "keep", "keep_reason": "owner_decided", "reason": "Checked in the editor"})
    lines = repo.detail(survey_id)["share"]["slack_post"].splitlines()
    assert f"Checked by hand: {checks[0]['title']}" in lines
    kept = next(line for line in lines if line.startswith("Kept on purpose: 1"))
    assert checks[1]["title"] in kept and kept.endswith("– Owner decided: Checked in the editor)")


def test_a_survey_with_no_finished_check_has_no_post(repo):
    created = repo.submit(concept_survey(), ai=False)
    assert repo.detail(created["id"])["share"]["slack_post"] is None


@pytest.fixture
def http(tmp_path):
    app = create_app(tmp_path / "summary.db")
    with TestClient(app, base_url="http://localhost") as client:
        yield client, app.state.repository


def summary(client, survey_id, version=1):
    return client.get(f"/api/surveys/{survey_id}/versions/{version}/summary", params={"download": "true"})


def test_the_html_summary_has_the_review_card_with_signoff_and_the_you_check_list(http):
    client, repo = http
    survey_id = save_review(repo, concept_with_link())
    close_all(repo, survey_id)
    repo.sign_off(survey_id, 1, "Priya <b>N</b>")
    response = summary(client, survey_id)
    html = response.text
    assert response.status_code == 200 and "attachment" in response.headers["content-disposition"]
    assert "Review summary" in html and "Sunrise Skillet Concept Test" in html and "Version 1" in html
    assert "Signed off by Priya &lt;b&gt;N&lt;/b&gt;" in html and "<b>N</b>" not in html
    assert "https://app.redjade.net/s/sunrise" in html and "SECRET123" not in html and "token=" not in html
    assert "Images load on a phone" in html and "Checked by hand" in html


def test_the_html_summary_makes_no_outside_requests_and_runs_no_scripts(http):
    client, repo = http
    survey_id = save_review(repo, concept_with_link())
    html = summary(client, survey_id).text
    assert not re.search(r"<script|<link|<img|<iframe|src=|href=|@import|url\(", html, re.I)
    assert "Not signed off yet" in html


def test_the_on_screen_summary_carries_the_same_card(http):
    client, repo = http
    survey_id = save_review(repo, concept_with_link())
    html = client.get(f"/api/surveys/{survey_id}/versions/1/summary").text
    assert "Review summary" in html and "SECRET123" not in html


@pytest.fixture
def app_client(tmp_path):
    def make(**kwargs):
        app = create_app(tmp_path / "dev.db", **kwargs)
        return TestClient(app, base_url="http://localhost")
    return make


def test_the_developer_snapshot_import_is_off_unless_the_server_says_so(app_client, monkeypatch):
    monkeypatch.delenv("SURVEYCOACH_DEVELOPER", raising=False)
    with app_client() as client:
        assert client.get("/api/metadata").json()["developer"] is False
        assert "SURVEYCOACH_DEVELOPER" not in client.get("/environment.js").text
    with app_client(developer=True) as client:
        assert client.get("/api/metadata").json()["developer"] is True
        assert "window.SURVEYCOACH_DEVELOPER = true;" in client.get("/environment.js").text
    monkeypatch.setenv("SURVEYCOACH_DEVELOPER", "1")
    with app_client() as client:
        assert client.get("/api/metadata").json()["developer"] is True
    with app_client(developer=False) as client:
        assert client.get("/api/metadata").json()["developer"] is False
