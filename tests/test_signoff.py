"""Sign-off (brief 4.7): a named, local, append-only record per version, honest about what was still open."""
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from concept_fixture import concept_survey
from review_helpers import save_review
from surveycoach.server import create_app
from surveycoach.server.repository import Repository

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "signoff.db")
    yield repository
    repository.close()


def saved(repo, snapshot=None, survey_id=None):
    return save_review(repo, snapshot or concept_survey(), survey_id)


def close_all(repo, survey_id, version=1, skip=()):
    for item in repo.detail(survey_id, version)["overview"]["items"]:
        for fingerprint in item["fingerprints"]:
            if fingerprint not in skip:
                repo.save_decision(survey_id, version, fingerprint, {"action": "done"})


def test_a_new_survey_is_not_signed(repo):
    state = repo.detail(saved(repo))["signoff"]
    assert state["signed"] is False and state["signed_off_by"] is None and state["signed_off_at"] is None
    assert state["record"] is None and state["history"] == [] and state["version"] == 1


def test_ready_survey_signs_off_with_the_recorded_facts(repo):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    detail = repo.detail(survey_id)
    assert detail["overview"]["verdict"]["kind"] == "ready_for_signoff"
    state = repo.sign_off(survey_id, 1, "Priya Nair")
    record = state["record"]
    assert state["signed"] is True and state["signed_off_by"] == "Priya Nair" and ISO.match(state["signed_off_at"])
    assert record["name"] == "Priya Nair" and record["version"] == 1 and record["signed_at"] == state["signed_off_at"]
    assert record["verdict_kind"] == "ready_for_signoff" and record["headline"] == "Ready for sign-off"
    tiles = detail["overview"]["verdict"]["tiles"]
    assert record["counts"] == {**tiles, "done": detail["queue"]["counts"]["done"],
                                "total": detail["queue"]["counts"]["total"],
                                "unverified": detail["queue"]["counts"]["unverified"]}
    assert record["acknowledged_open"] is False and record["open_items"] == []
    assert repo.detail(survey_id)["signoff"]["signed_off_by"] == "Priya Nair"


def test_an_open_survey_is_refused_without_acknowledgement(repo):
    survey_id = saved(repo)
    with pytest.raises(ValueError, match="still open"):
        repo.sign_off(survey_id, 1, "Priya")
    assert repo.detail(survey_id)["signoff"]["signed"] is False


def test_acknowledging_records_every_open_item_verbatim_and_never_hides_them(repo):
    survey_id = saved(repo)
    detail = repo.detail(survey_id)
    state = repo.sign_off(survey_id, 1, "Priya", acknowledge_open=True)
    record = state["record"]
    open_items = [i for i in detail["overview"]["items"] if i["open"]]
    assert record["acknowledged_open"] is True and record["verdict_kind"] != "ready_for_signoff"
    assert [o["id"] for o in record["open_items"]] == [i["id"] for i in open_items]
    assert [(o["state"], o["headline"], o["location"]) for o in record["open_items"]] == [
        (i["state"], i["headline"], i["location"]) for i in open_items]
    assert record["counts"]["fix"] + record["counts"]["improve"] + record["counts"]["you_check"] == len(open_items)
    assert record["headline"] == detail["overview"]["verdict"]["headline"]


def test_acknowledging_a_ready_survey_records_nothing_was_open(repo):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    record = repo.sign_off(survey_id, 1, "Priya", acknowledge_open=True)["record"]
    assert record["acknowledged_open"] is False and record["open_items"] == []


def test_a_survey_with_no_finished_check_cannot_be_signed(repo):
    created = repo.submit(concept_survey(), ai=False)
    with pytest.raises(ValueError, match="nothing to sign off"):
        repo.sign_off(created["id"], 1, "Priya", acknowledge_open=True)
    with pytest.raises(KeyError):
        repo.sign_off("nope", 1, "Priya")
    with pytest.raises(KeyError):
        repo.sign_off(created["id"], 9, "Priya")


@pytest.mark.parametrize("name", ["", "   ", "\u200b\u202e", "x" * 81, None, 7])
def test_names_must_be_one_to_eighty_real_characters(repo, name):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    with pytest.raises(ValueError):
        repo.sign_off(survey_id, 1, name)
    assert repo.detail(survey_id)["signoff"]["signed"] is False


def test_names_are_cleaned_to_one_line_and_markup_is_stored_as_typed(repo):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    state = repo.sign_off(survey_id, 1, "  Priya\n\u202e  <b>N</b> ")
    assert state["signed_off_by"] == "Priya <b>N</b>"
    assert repo.sign_off(survey_id, 1, "x" * 80)["signed_off_by"] == "x" * 80


def test_the_you_check_list_says_who_and_when_from_the_decision_times(repo):
    survey_id = saved(repo)
    checks = repo.detail(survey_id)["overview"]["you_check"]
    done, kept, left = checks[0]["fingerprint"], checks[1]["fingerprint"], checks[2]["fingerprint"]
    repo.save_decision(survey_id, 1, done, {"action": "original"})
    repo.save_decision(survey_id, 1, kept, {"action": "keep", "keep_reason": "owner_decided", "reason": "Checked on my phone"})
    state = repo.sign_off(survey_id, 1, "Priya", acknowledge_open=True)
    listed = {c["fingerprint"]: c for c in state["record"]["you_check"]}
    assert len(listed) == len(checks)
    events = {e["fingerprint"]: e["recorded_at"] for e in repo.decision_history(survey_id, 1)}
    expected = events[done].replace(" ", "T") + "Z"
    assert (listed[done]["status"], listed[done]["who"], listed[done]["at"]) == ("done", "Priya", expected)
    assert listed[done]["title"] == checks[0]["title"] and listed[done]["where"] == checks[0]["where"]
    assert (listed[kept]["status"], listed[kept]["reason"]) == ("kept", "Owner decided: Checked on my phone")
    assert (listed[left]["status"], listed[left]["who"], listed[left]["at"]) == ("open", None, None)


def test_signing_again_appends_and_the_latest_wins(repo):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    repo.sign_off(survey_id, 1, "Priya")
    repo.sign_off(survey_id, 1, "Sam")
    state = repo.detail(survey_id)["signoff"]
    assert state["signed_off_by"] == "Sam"
    assert [(h["name"], h["latest"]) for h in state["history"]] == [("Priya", False), ("Sam", True)]


def test_the_log_cannot_be_edited_or_deleted(repo):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    repo.sign_off(survey_id, 1, "Priya")
    with pytest.raises(sqlite3.IntegrityError):
        repo.db.execute("UPDATE signoffs SET name='Mallory'")
    with pytest.raises(sqlite3.IntegrityError):
        repo.db.execute("DELETE FROM signoffs")
    assert repo.detail(survey_id)["signoff"]["signed_off_by"] == "Priya"


def test_reopening_after_sign_off_is_flagged_not_hidden(repo):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    repo.sign_off(survey_id, 1, "Priya")
    assert repo.detail(survey_id)["signoff"]["changed_since"] is False
    fingerprint = repo.detail(survey_id)["overview"]["items"][0]["fingerprints"][0]
    repo.save_decision(survey_id, 1, fingerprint, {"action": "open"})
    state = repo.detail(survey_id)["signoff"]
    assert state["signed"] is True and state["changed_since"] is True


def test_a_new_version_starts_unsigned_and_keeps_the_old_record_in_history(repo):
    survey_id = saved(repo)
    close_all(repo, survey_id)
    repo.sign_off(survey_id, 1, "Priya")
    changed = concept_survey().model_copy(deep=True)
    changed.pages[1].questions[0].text = "How often do you make breakfast at home?"
    saved(repo, changed, survey_id)
    v2 = repo.detail(survey_id, 2)["signoff"]
    assert v2["signed"] is False and v2["version"] == 2 and v2["signed_off_by"] is None
    assert [(h["version"], h["name"]) for h in v2["history"]] == [(1, "Priya")]
    v1 = repo.detail(survey_id, 1)["signoff"]
    assert v1["signed"] is True and v1["signed_off_by"] == "Priya"


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "http.db")
    with TestClient(app, base_url="http://localhost") as client:
        yield client, app.state.repository


def url(survey_id, version=1):
    return f"/api/surveys/{survey_id}/versions/{version}/signoff"


def test_http_signs_off_and_exposes_the_state(client):
    http, repository = client
    survey_id = saved(repository)
    refused = http.post(url(survey_id), json={"name": "Priya"})
    assert refused.status_code == 422 and "still open" in refused.json()["detail"]
    done = http.post(url(survey_id), json={"name": "Priya", "acknowledge_open": True})
    assert done.status_code == 201
    body = done.json()
    assert body["signed"] is True and body["signed_off_by"] == "Priya" and ISO.match(body["signed_off_at"])
    assert http.get(f"/api/surveys/{survey_id}").json()["signoff"]["signed_off_by"] == "Priya"


@pytest.mark.parametrize("body", [
    {}, {"name": ""}, {"name": "x" * 81}, {"name": 5}, {"name": "Priya", "acknowledge_open": "yes"},
    {"name": "Priya", "signed_at": "2020-01-01T00:00:00Z"}, {"name": "Priya", "version": 3},
])
def test_http_rejects_bad_requests_and_never_trusts_a_client_clock(client, body):
    http, repository = client
    survey_id = saved(repository)
    assert http.post(url(survey_id), json={"acknowledge_open": True, **body}).status_code == 422
    assert http.get(f"/api/surveys/{survey_id}").json()["signoff"]["signed"] is False


def test_http_unknown_survey_or_version_is_404(client):
    http, repository = client
    survey_id = saved(repository)
    assert http.post(url("nope"), json={"name": "Priya"}).status_code == 404
    assert http.post(url(survey_id, 9), json={"name": "Priya"}).status_code == 404
