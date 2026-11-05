"""Decisions: use / done / keep (with a reason chip). Offline, temp repository, synthetic survey."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from concept_fixture import concept_survey
from surveycoach.review import run_review
from surveycoach.server import create_app
from surveycoach.server.repository import Repository


def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "decisions.db")
    snapshot = concept_survey()
    created = app.state.repository.submit(snapshot, ai=False)
    app.state.repository.finish(created["job_id"], encoded(snapshot))
    with TestClient(app, base_url="http://localhost") as http:
        http.survey_id = created["id"]
        http.repository = app.state.repository
        yield http


def url(client, fingerprint, version=1):
    return f"/api/surveys/{client.survey_id}/versions/{version}/decisions/{fingerprint}"


def detail(client):
    return client.get(f"/api/surveys/{client.survey_id}").json()


def a_solo_finding(client):
    """A finding that is its own card (grouped cards close only when every member is handled)."""
    found = detail(client)
    solo = {i["fingerprints"][0] for i in found["overview"]["items"] if i["kind"] == "finding" and i["count"] == 1}
    return next(f for f in found["review"]["findings"] if f["fingerprint"] in solo)


def a_you_check(client):
    return detail(client)["overview"]["you_check"][0]["fingerprint"]


# --- done ------------------------------------------------------------------------------------

def test_done_is_a_decision_on_a_finding_and_closes_its_item(client):
    finding = a_solo_finding(client)
    saved = client.put(url(client, finding["fingerprint"]), json={"action": "done"})
    assert saved.status_code == 200 and saved.json()["action"] == "done"
    after = detail(client)
    item = next(i for i in after["overview"]["items"] if finding["fingerprint"] in i["fingerprints"])
    assert after["decisions"][finding["fingerprint"]]["action"] == "done"
    assert item["decided"] is True and item["open"] is False


def test_done_ignores_a_stray_rewrite_text(client):
    finding = a_solo_finding(client)
    saved = client.put(url(client, finding["fingerprint"]), json={"action": "done", "picked_text": "invented"})
    assert saved.json()["picked_text"] is None


def test_you_check_items_accept_done_and_keep(client):
    first, second = (c["fingerprint"] for c in detail(client)["overview"]["you_check"][:2])
    assert first.startswith("you-check:")
    assert client.put(url(client, first), json={"action": "done"}).status_code == 200
    kept = client.put(url(client, second), json={"action": "keep", "keep_reason": "not_applicable"})
    assert kept.status_code == 200
    progress = detail(client)["overview"]["verdict"]["progress"]
    assert progress["done"] == 2


# --- keep reason chip ------------------------------------------------------------------------

@pytest.mark.parametrize("chip", ["intentional", "owner_decided", "not_applicable", "other"])
def test_every_reason_chip_is_a_stated_reason_on_its_own(client, chip):
    fingerprint = a_you_check(client)
    saved = client.put(url(client, fingerprint), json={"action": "keep", "keep_reason": chip})
    assert saved.status_code == 200 and saved.json()["keep_reason"] == chip
    item = next(i for i in detail(client)["overview"]["items"] if i["id"] == fingerprint)
    assert item["decided"] is True


def test_a_chip_can_carry_a_short_note(client):
    saved = client.put(url(client, a_you_check(client)),
                       json={"action": "keep", "keep_reason": "owner_decided", "reason": "Priya signed off"})
    assert saved.json()["reason"] == "Priya signed off"


def test_an_unknown_chip_is_a_clear_422(client):
    response = client.put(url(client, a_you_check(client)), json={"action": "keep", "keep_reason": "lazy"})
    assert response.status_code == 422
    assert "intentional" in json.dumps(response.json()) and "owner_decided" in json.dumps(response.json())


def test_an_unknown_action_is_a_clear_422(client):
    response = client.put(url(client, a_you_check(client)), json={"action": "shrug"})
    assert response.status_code == 422 and "done" in json.dumps(response.json())


def test_a_note_next_to_a_chip_is_capped_at_200_characters(client):
    fingerprint = a_you_check(client)
    ok = client.put(url(client, fingerprint), json={"action": "keep", "keep_reason": "other", "reason": "x" * 200})
    too_long = client.put(url(client, fingerprint), json={"action": "keep", "keep_reason": "other", "reason": "x" * 201})
    assert ok.status_code == 200 and too_long.status_code == 422
    assert "200" in json.dumps(too_long.json())


def test_a_chip_only_makes_sense_on_keep(client):
    response = client.put(url(client, a_you_check(client)), json={"action": "done", "keep_reason": "other"})
    assert response.status_code == 422 and "keep" in json.dumps(response.json())


def test_keep_still_needs_some_reason_chip_or_text(client):
    assert client.put(url(client, a_you_check(client)), json={"action": "keep"}).status_code == 422


def test_legacy_keep_with_only_free_text_still_works(client):
    saved = client.put(url(client, a_you_check(client)), json={"action": "keep", "reason": "Checked on my phone " * 20})
    assert saved.status_code == 200 and "keep_reason" in saved.json()   # the new field is simply empty
    assert saved.json()["keep_reason"] is None


# --- sanitised on read -------------------------------------------------------------------------

def test_text_is_stripped_of_control_and_direction_characters_on_read(client):
    fingerprint = a_you_check(client)
    # a hand-edited row, as an older or hostile writer could leave it
    client.repository.db.execute(
        "INSERT INTO decisions(survey_id,version,fingerprint,data) VALUES (?,?,?,?)",
        (client.survey_id, 1, fingerprint, json.dumps(
            {"action": "keep", "reason": "ok\x00\x1b[31m\u202egnirts", "keep_reason": "bogus", "fingerprint": fingerprint})))
    client.repository.db.commit()
    stored = detail(client)["decisions"][fingerprint]
    assert stored["reason"] == "ok[31mgnirts" and stored["keep_reason"] == "other"
    summary = client.get(f"/api/surveys/{client.survey_id}/versions/1/summary").text
    assert "\x1b" not in summary and "\u202e" not in summary


def test_markup_in_a_note_is_escaped_in_the_share_page(client):
    fingerprint = a_you_check(client)
    client.put(url(client, fingerprint), json={"action": "keep", "keep_reason": "other", "reason": "<script>alert(1)</script>"})
    summary = client.get(f"/api/surveys/{client.survey_id}/versions/1/summary").text
    assert "<script>alert(1)</script>" not in summary


def test_stored_decisions_without_the_new_fields_load_unchanged(client):
    fingerprint = a_you_check(client)
    legacy = {"action": "keep", "reason": "Checked by phone", "fingerprint": fingerprint, "revision": 0}
    client.repository.db.execute(
        "INSERT INTO decisions(survey_id,version,fingerprint,data) VALUES (?,?,?,?)",
        (client.survey_id, 1, fingerprint, json.dumps(legacy)))
    client.repository.db.commit()
    assert detail(client)["decisions"][fingerprint] == legacy


# --- durable, history never rewritten ------------------------------------------------------------

def test_decisions_survive_a_restart(client, tmp_path):
    fingerprint = a_you_check(client)
    client.put(url(client, fingerprint), json={"action": "keep", "keep_reason": "intentional"})
    reopened = Repository(tmp_path / "decisions.db")
    try:
        assert reopened.detail(client.survey_id)["decisions"][fingerprint]["keep_reason"] == "intentional"
    finally:
        reopened.close()


def test_every_change_of_mind_is_kept_in_the_history(client):
    fingerprint = a_you_check(client)
    client.put(url(client, fingerprint), json={"action": "done"})
    client.put(url(client, fingerprint), json={"action": "keep", "keep_reason": "other"})
    client.put(url(client, fingerprint), json={"action": "open"})
    history = client.repository.decision_history(client.survey_id, 1, fingerprint)
    assert [event["action"] for event in history] == ["done", "keep", "open"]
    assert detail(client)["decisions"][fingerprint]["action"] == "open"      # the live row is the latest


def test_a_replayed_request_does_not_add_history(client):
    fingerprint = a_you_check(client)
    body = {"action": "done", "client_id": "tab-1", "revision": 1}
    client.put(url(client, fingerprint), json=body)
    client.put(url(client, fingerprint), json=body)
    assert len(client.repository.decision_history(client.survey_id, 1, fingerprint)) == 1


def test_done_is_never_carried_into_the_next_version_and_old_rows_stay_put(client):
    fingerprint = a_you_check(client)
    client.put(url(client, fingerprint), json={"action": "done"})
    snapshot = concept_survey().model_copy(deep=True)
    snapshot.title = "Quesadilla tray concept test, edited"
    snapshot.pages[1].questions[0].text = snapshot.pages[1].questions[0].text + " today"
    again = client.repository.submit(snapshot, ai=False, survey_id=client.survey_id)
    client.repository.finish(again["job_id"], encoded(snapshot))
    v2 = client.get(f"/api/surveys/{client.survey_id}/versions/2").json()
    assert fingerprint not in v2["decisions"]                                 # unverified until Check again
    v1 = client.get(f"/api/surveys/{client.survey_id}/versions/1").json()
    assert v1["decisions"][fingerprint]["action"] == "done"


def still_open(client):
    page = client.get(f"/api/surveys/{client.survey_id}/versions/1/summary?download=true").text
    return int(re.search(r"(\d+) findings still need a choice", page).group(1)), page


def test_the_share_page_counts_done_as_handled_and_shows_a_chip_only_keep(client):
    first, second = [f for f in detail(client)["review"]["findings"] if not f.get("absorbed_by")][:2]
    start, _ = still_open(client)
    client.put(url(client, first["fingerprint"]), json={"action": "done"})
    assert still_open(client)[0] == start - 1
    client.put(url(client, second["fingerprint"]), json={"action": "keep", "keep_reason": "owner_decided"})
    count, page = still_open(client)
    assert count == start - 2 and "Reason: Owner decided" in page
