"""Public local-Studio API contracts; every test uses a disposable SQLite file."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from surveycoach.llm import FakeProvider
from surveycoach.server import create_app
from surveycoach.snapshot import SurveySnapshot

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def snapshot():
    return json.loads((ROOT / "fixtures" / "boxer-briefs.json").read_text())


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "studio.sqlite3"), base_url="http://localhost") as client:
        yield client


def imported(client, snapshot, **kwargs):
    response = client.post("/api/surveys", json={"snapshot": snapshot, **kwargs})
    assert response.status_code == 202, response.text
    data = response.json()
    job = client.get(f"/api/jobs/{data['job_id']}").json()
    assert job["status"] == "completed", job
    return client.get(f"/api/surveys/{data['id']}/versions/{data['version']}").json()


def test_import_list_detail_and_restart(tmp_path, snapshot):
    path = tmp_path / "persistent.sqlite3"
    provider = FakeProvider({})
    with TestClient(create_app(path, provider), base_url="http://localhost") as client:
        data = imported(client, snapshot)
        assert provider.calls == []  # Pasted content must not leave the machine by default.
        assert data["version"] == 1 and data["title"] == snapshot["title"]
        assert SurveySnapshot.model_validate(data["snapshot"]) == SurveySnapshot.model_validate(snapshot)
        assert data["review"]["ai"] is None and data["review"]["unchecked"]
        assert data["review"]["scorecard"]["readiness"] != "ready"
        assert data["timeline"] and data["total_seconds"] > 0
        findings = data["review"]["findings"]
        assert findings and all(len(f["fingerprint"]) == 12 for f in findings)
        assert client.get("/api/surveys").json()["surveys"][0]["id"] == data["id"]
        metadata = client.get("/api/metadata").json()
        assert metadata["criteria"]["B1"]["dimension"] == "blocker"
        assert metadata["dimensions"] and metadata["ai_batches"]
    with TestClient(create_app(path), base_url="http://localhost") as client:
        restored = client.get(f"/api/surveys/{data['id']}").json()
        assert restored["snapshot"] == data["snapshot"]
        assert restored["review"] == data["review"]
        assert restored["versions"][0]["version"] == 1


def test_recheck_deduplicates_content_but_not_changed_content(client, snapshot):
    first = imported(client, snapshot)
    url = f"/api/surveys/{first['id']}/recheck"
    same = client.post(url, json={"snapshot": snapshot}).json()
    assert same["version"] == 1 and same["deduplicated"] is True
    changed = json.loads(json.dumps(snapshot))
    changed["title"] = "A genuinely new version"
    second = client.post(url, json={"snapshot": changed}).json()
    assert second["version"] == 2 and second["deduplicated"] is False
    detail = client.get(f"/api/surveys/{first['id']}").json()
    assert len(detail["versions"]) == 2
    old = client.get(f"/api/surveys/{first['id']}/versions/1").json()
    assert old["snapshot"] == first["snapshot"] and old["review"] == first["review"]
    repeated = client.post(url, json={"snapshot": snapshot}).json()
    assert repeated["version"] == 1  # Deduplication works against ALL historic versions.
    assert client.get(f"/api/surveys/{first['id']}").json()["version"] == 2


def test_version_scoped_decisions_and_escaped_packet(client, snapshot):
    data = imported(client, snapshot)
    finding = data["review"]["findings"][0]
    url = f"/api/surveys/{data['id']}/versions/1/decisions/{finding['fingerprint']}"
    decision = {"action": "keep", "picked_text": None,
                "reason": "<script>evil()</script><img src=x onerror=evil()>", "manual_done": True}
    response = client.put(url, json=decision)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["picked_text"] == decision["picked_text"] and saved["manual_done"]
    assert saved["original"] == (finding.get("current_text") or finding["evidence"])
    detail = client.get(f"/api/surveys/{data['id']}/versions/1").json()
    assert detail["decisions"][finding["fingerprint"]] == saved
    packet = client.get(f"/api/surveys/{data['id']}/versions/1/summary").text
    assert "&lt;script&gt;" in packet and "<script>evil()" not in packet
    assert "&lt;img" in packet and "Manual" in packet
    changed = {**snapshot, "title": "Version two"}
    client.post(f"/api/surveys/{data['id']}/recheck", json={"snapshot": changed})
    carried = client.get(f"/api/surveys/{data['id']}/versions/2").json()["decisions"]
    assert carried[finding["fingerprint"]]["reason"] == decision["reason"]
    assert carried[finding["fingerprint"]]["carried_from_round"] == 1
    assert carried[finding["fingerprint"]]["manual_done"] is False
    assert client.put(url, json={"action": "keep", "reason": ""}).status_code == 422
    assert client.put(url, json={"action": "original"}).json()["picked_text"] is None
    assert client.put(url.replace(finding["fingerprint"], "not-a-finding"), json=decision).status_code == 404


def test_unknown_records_and_no_url_reader(client):
    assert client.get("/api/surveys/missing").status_code == 404
    assert client.get("/api/jobs/missing").status_code == 404
    assert client.post("/api/surveys", json={"url": "http://redjade.example"}).status_code == 422
    assert client.get("/api/unknown").status_code == 404
    response = client.get("/")
    assert response.status_code == 200 and "SurveyCoach" in response.text
    assert client.get("/app.js").status_code == 200
