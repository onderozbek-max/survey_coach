"""Local service protections and explicit AI consent."""
from fastapi.testclient import TestClient

from surveycoach.judge.batches import BATCHES
from surveycoach.judge.schemas import BatchOutput, BlockerCall, Verdict
from surveycoach.llm import FakeProvider
from surveycoach.server import create_app


SNAPSHOT = {"title": "Local only", "pages": [{"id": "p1", "position": 1, "kind": "intro",
             "intro_text": "Welcome. This survey takes 2 minutes."}]}


def test_explicit_ai_and_pollable_job(tmp_path):
    def answer(system, data):
        batch = next(b for b in BATCHES if f"Your job in this call: {b.title}" in system)
        return BatchOutput(verdicts=[Verdict(criterion_id=c, fraction=1) for c in batch.criteria],
                           blockers=[BlockerCall(blocker_id=b, triggered=False) for b in batch.blockers])
    provider = FakeProvider({"BatchOutput": answer})
    with TestClient(create_app(tmp_path / "db", provider), base_url="http://localhost") as client:
        response = client.post("/api/surveys", json={"snapshot": SNAPSHOT, "ai": True})
        assert response.status_code == 202
        job = client.get("/api/jobs/" + response.json()["job_id"]).json()
        assert job["status"] == "completed" and job["ai_requested"] is True
        detail = client.get("/api/surveys/" + response.json()["id"]).json()
        assert set(detail["review"]["ai"]["checked"]) == {b.id for b in BATCHES}
        assert len(provider.calls) == 3


def test_failed_provider_remains_unchecked(tmp_path):
    with TestClient(create_app(tmp_path / "db", FakeProvider({})), base_url="http://localhost") as client:
        created = client.post("/api/surveys", json={"snapshot": SNAPSHOT, "ai": True}).json()
        data = client.get("/api/surveys/" + created["id"]).json()
        assert data["review"]["ai"]["failed"]
        assert data["review"]["scorecard"]["readiness"] != "ready"
        assert data["review"]["unchecked"]


def test_host_origin_and_body_limits(tmp_path):
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost") as client:
        body = {"snapshot": SNAPSHOT}
        assert client.post("/api/surveys", json=body, headers={"origin": "https://evil.test"}).status_code == 403
        assert client.post("/api/surveys", json=body, headers={"sec-fetch-site": "cross-site"}).status_code == 403
        assert client.post("/api/surveys", json=body, headers={"origin": "http://localhost:9999"}).status_code == 403
        assert client.post("/api/surveys", json=body, headers={"origin": "null"}).status_code == 403
        assert client.post("/api/surveys", json=body, headers={"origin": "http://localhost"}).status_code == 202
        assert client.get("/api/surveys", headers={"host": "evil.test"}).status_code == 400
        assert client.post("/api/surveys", content=b"x" * (1024 * 1024 + 1),
                           headers={"content-type": "application/json"}).status_code == 413
        assert client.post("/api/surveys", json={**body, "ai": "yes"}).status_code == 422


def test_import_rejects_local_file_paths(tmp_path):
    snapshot = {**SNAPSHOT, "pages": [{**SNAPSHOT["pages"][0], "media": [{"asset_path": "/etc/passwd"}]}]}
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost") as client:
        assert client.post("/api/surveys", json={"snapshot": snapshot}).status_code == 422
