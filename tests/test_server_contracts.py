"""Focused trust contracts. Failures reproduce review findings; no live AI/network.

Run: .venv/bin/python -m pytest tests/test_server_contracts.py -q
These are desired-behavior assertions, intentionally red while defects remain.
"""
import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from surveycoach.llm import FakeProvider
from surveycoach.server import create_app
from surveycoach.server.repository import Repository
from surveycoach.server.service import run_job
from surveycoach.snapshot import SurveySnapshot
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return json.loads((ROOT / "fixtures" / "boxer-briefs.json").read_text())


def import_sample(client):
    created = client.post("/api/surveys", json={"snapshot": sample()})
    assert created.status_code == 202
    return client.get("/api/surveys/" + created.json()["id"]).json()


def test_picked_text_must_be_one_of_saved_finding_choices(tmp_path):
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost") as client:
        detail = import_sample(client)
        finding = next(f for f in detail["review"]["findings"] if f.get("suggested_text") or f.get("options"))
        response = client.put(
            f"/api/surveys/{detail['id']}/versions/1/decisions/{finding['fingerprint']}",
            json={"action": "pick", "picked_text": "Invented text which this review never recommended", "manual_done": True},
        )
        # UI says "chosen fixes" and has no custom-edit mode. Unknown text cannot
        # silently masquerade as a saved suggestion (or restore correctly in either UI).
        assert response.status_code == 422, response.json()


def test_review_relevant_metadata_changes_create_a_new_snapshot(tmp_path):
    original = sample()
    changed = copy.deepcopy(original)
    # Same wording/choices, but the previously broken image has now loaded.
    def images(value):
        if isinstance(value, dict):
            if "loaded" in value and value["loaded"] is False:
                value["loaded"] = True
            for item in value.values():
                images(item)
        elif isinstance(value, list):
            for item in value:
                images(item)
    images(changed)
    assert original != changed
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost") as client:
        first = client.post("/api/surveys", json={"snapshot": original}).json()
        second = client.post(f"/api/surveys/{first['id']}/recheck", json={"snapshot": changed}).json()
        detail = client.get(f"/api/surveys/{first['id']}").json()
        assert (second["version"], second["deduplicated"]) == (2, False), {
            "response": second,
            "still_reports_broken_image": any(f["criterion_id"] == "B7" for f in detail["review"]["findings"]),
            "stored_snapshot_is_old": detail["snapshot"] == SurveySnapshot.model_validate(original).model_dump(),
        }


def test_declared_hash_cannot_spoof_server_computed_identity(tmp_path):
    # Negative control: no issue with a caller-supplied hash itself; it is ignored.
    snapshot = sample()
    snapshot["content_hash"] = "attacker-chosen"
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost") as client:
        response = client.post("/api/surveys", json={"snapshot": snapshot})
        detail = client.get("/api/surveys/" + response.json()["id"]).json()
        assert detail["content_hash"] == SurveySnapshot.model_validate(snapshot).content_hash
        assert detail["content_hash"] != "attacker-chosen"


def test_older_ai_job_cannot_replace_newer_completed_local_review(tmp_path):
    repository = Repository(tmp_path / "db")
    try:
        snapshot = SurveySnapshot.model_validate(sample())
        earlier_ai = repository.submit(snapshot, True)
        newer_local = repository.submit(snapshot, False, earlier_ai["id"])
        assert earlier_ai["job_id"] != newer_local["job_id"]
        # Force a valid interleaving: the later local task finishes before slower AI.
        run_job(repository, newer_local["job_id"], FakeProvider({}))
        assert repository.detail(earlier_ai["id"])["review"]["ai"] is None
        run_job(repository, earlier_ai["job_id"], FakeProvider({}))
        detail = repository.detail(earlier_ai["id"])
        assert detail["job"]["id"] == newer_local["job_id"]
        assert detail["job"]["ai_requested"] is False
        assert detail["review"]["ai"] is None, "Latest job says local-only, but older AI review overwrote it"
    finally:
        repository.close()


def test_summary_packet_distinguishes_earned_and_unchecked_points(tmp_path):
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost") as client:
        detail = import_sample(client)
        card = detail["review"]["scorecard"]
        assert card["unchecked_points"] > 0
        earned = card["score"] if "checked_points" in card else card["score"] - card["unchecked_points"]
        checked = card.get("checked_points", 100 - card["unchecked_points"])
        packet = client.get(f"/api/surveys/{detail['id']}/versions/1/summary").text
        assert f"{earned:g} of {checked} checked points" in packet, {
            "score_includes_unchecked_credit": card["score"],
            "actually_earned": earned, "unchecked_points": card["unchecked_points"],
        }


def test_local_root_has_an_entry_to_the_private_workspace(browser, studio):
    page = browser.new_page()
    try:
        page.goto(studio + "/")
        page.get_by_role('button', name='Check survey', exact=True).wait_for()
        # Check rendered DOM, not only source HTML (navigation might be JS-built).
        assert page.locator("#import-form, a[href='local.html']").count() > 0
    finally:
        page.close()


def test_rapid_choice_changes_cannot_save_the_older_pick_last(browser, studio):
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(studio + "/local.html")
        page.get_by_label("Survey snapshot file (.json)").set_input_files(str(ROOT / "fixtures/boxer-briefs.json"))
        page.get_by_role("button", name="Check survey").click()
        page.wait_for_url("**/review.html?**", timeout=30000)
        page.locator('#chapter-nav [data-chapter=improve]').click()
        from tests.test_workspace_decisions import finding_with, focus_finding, keep_mine
        finding = finding_with(page, True)
        focus_finding(page, finding)
        held, completed = [], []

        def reorder(route):
            if not held:
                held.append(route)  # Delay first pick while user changes their mind.
            else:
                response = route.fetch()
                route.fulfill(response=response)
                completed.append(True)

        page.route("**/decisions/*", reorder)
        page.locator('#coach .issue-rewrite .btn').first.click()
        page.wait_for_timeout(100)
        assert held
        focus_finding(page, finding)
        keep_mine(page, 'Required wording')
        assert completed
        response = held[0].fetch()
        held[0].fulfill(response=response)  # Old pick arrives after the keep decision.
        page.wait_for_timeout(100)
        assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
        page.reload()
        page.locator('#stage .phone-screen').wait_for()
        focus_finding(page, finding)
        assert page.get_by_label('Reason for keeping', exact=False).input_value() == 'Required wording'
        assert 'accepted risk' in page.locator('.accepted-risk').inner_text(), 'Reload must not restore the stale suggestion'
        assert page.locator('#copy-all').is_disabled()
    finally:
        context.close()
