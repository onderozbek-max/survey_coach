"""Job lifecycle, review-attempt preservation, and snapshot identity invariants."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient

from surveycoach.llm import FakeProvider
from surveycoach.server import create_app
from surveycoach.server.repository import Repository
from surveycoach.snapshot import SurveySnapshot

SNAPSHOT = {"title": "Private survey", "pages": [{"id": "p0", "position": 0, "kind": "intro", "intro_text": "Welcome to the synthetic survey."}]}


def test_running_job_is_pollable_before_ai_finishes(tmp_path):
    entered, release = Event(), Event()

    def answer(system, data):
        entered.set()
        assert release.wait(timeout=10)
        from surveycoach.llm import LlmUnavailable
        raise LlmUnavailable("Offline for this test")

    app = create_app(tmp_path / "db", FakeProvider({"BatchOutput": answer}))
    with TestClient(app, base_url="http://localhost") as client, ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, "/api/surveys", json={"snapshot": SNAPSHOT, "ai": True})
        try:
            assert entered.wait(timeout=5)
            survey_id = client.get("/api/surveys").json()["surveys"][0]["id"]
            detail = client.get(f"/api/surveys/{survey_id}").json()
            assert detail["review"] is None
            job = client.get("/api/jobs/" + detail["job"]["id"]).json()
            assert job["status"] == "running"
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 202
        assert client.get("/api/jobs/" + job["id"]).json()["status"] == "completed"


def test_failed_job_preserves_previous_review_and_does_not_leak_exception(tmp_path, monkeypatch):
    app = create_app(tmp_path / "db")
    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/surveys", json={"snapshot": SNAPSHOT}).json()
        url = "/api/surveys/" + created["id"]
        before = client.get(url).json()

        def broken(*args, **kwargs):
            raise RuntimeError("secret token /Users/private")

        monkeypatch.setattr("surveycoach.server.service.run_review", broken)
        retry = client.post(url + "/recheck", json={"snapshot": SNAPSHOT}).json()
        job = client.get("/api/jobs/" + retry["job_id"]).json()
        assert job["status"] == "failed" and "secret" not in job["error"]
        after = client.get(url).json()
        assert after["review"] == before["review"] and after["version"] == 1


def test_startup_marks_interrupted_jobs_failed(tmp_path):
    path = tmp_path / "db"
    repository = Repository(path)
    pending = repository.submit(SurveySnapshot.model_validate(SNAPSHOT), False)
    repository.start(pending["job_id"])
    repository.close()
    with TestClient(create_app(path), base_url="http://localhost") as client:
        job = client.get("/api/jobs/" + pending["job_id"]).json()
        assert job["status"] == "failed" and job["finished_at"]


def test_simultaneous_rechecks_make_one_version_and_one_active_job(tmp_path):
    repository = Repository(tmp_path / "db")
    snapshot = SurveySnapshot.model_validate(SNAPSHOT)
    original = repository.submit(snapshot, False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: repository.submit(snapshot, False, original["id"]), range(8)))
    assert {j["version"] for j in jobs} == {1}
    assert {j["job_id"] for j in jobs} == {original["job_id"]}
    assert all(j["deduplicated"] for j in jobs)
    repository.close()


def test_decision_fingerprint_survives_recheck_and_is_version_scoped(tmp_path):
    snapshot = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "boxer-briefs.json").read_text())
    app = create_app(tmp_path / "db")
    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/surveys", json={"snapshot": snapshot}).json()
        url = "/api/surveys/" + created["id"]
        detail = client.get(url).json()
        fingerprints = [f["fingerprint"] for f in detail["review"]["findings"]]
        decision_url = url + "/versions/1/decisions/" + fingerprints[0]
        assert client.put(decision_url, json={"action": "keep", "reason": "Intentional research design"}).status_code == 200
        client.post(url + "/recheck", json={"snapshot": snapshot})
        checked = client.get(url).json()
        assert fingerprints == [f["fingerprint"] for f in checked["review"]["findings"]]
        assert checked["decisions"][fingerprints[0]]["reason"] == "Intentional research design"
        with app.state.repository.transaction() as db:
            assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 2
            assert db.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == 1
