"""Reader job integration with an injected controlled reader, never a live vendor."""
from pathlib import Path

from fastapi.testclient import TestClient

from surveycoach.reader.models import Coverage, ReadResult
from surveycoach.server import create_app
from surveycoach.snapshot import SurveySnapshot

ROOT = Path(__file__).parent.parent


def test_link_read_is_explicit_and_coverage_reaches_review(tmp_path):
    app = create_app(tmp_path / "studio.sqlite")
    calls = []
    def controlled(url, **kwargs):
        calls.append((url, kwargs))
        return ReadResult(snapshot=SurveySnapshot.model_validate_json((ROOT / "fixtures/coffee-pods.json").read_text()),
                          coverage=Coverage(pages_captured=3, stop_reason="final_control"), capture_dir=tmp_path)
    app.state.reader = controlled
    with TestClient(app, base_url="http://localhost") as client:
        bad = client.post("/api/reader/jobs", json={"url": "https://example.redjade.net/test", "approval": False})
        assert bad.status_code == 422 and not calls
        bad = client.post("/api/reader/jobs", json={"url": "http://127.0.0.1/", "approval": True})
        assert bad.status_code == 422 and not calls
        created = client.post("/api/reader/jobs", json={"url": "https://example.redjade.net/test", "approval": True}).json()
        job = client.get(f"/api/jobs/{created['job_id']}").json()
        assert job["status"] == "completed"
        detail = client.get(f"/api/surveys/{job['survey_id']}").json()
        assert not detail["coverage"]["full_branching_coverage"]
        assert detail["review"]["scorecard"]["readiness"] != "ready"
        assert len(calls) == 1
        assert calls[0][1]["test_session"] is False  # off unless the operator enables it
        summary = client.get(f"/api/surveys/{job['survey_id']}/versions/1/summary").text
        assert "one deterministic path" in summary


def test_operator_setting_enables_one_test_participant_start(tmp_path, monkeypatch):
    monkeypatch.setenv("SURVEYCOACH_ALLOW_TEST_SESSION", "1")
    app = create_app(tmp_path / "studio.sqlite")
    calls = []
    def controlled(url, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("stop after recording arguments")
    app.state.reader = controlled
    with TestClient(app, base_url="http://localhost") as client:
        client.post("/api/reader/jobs", json={"url": "https://example.redjade.net/test", "approval": True})
    assert calls == [{"approval": True, "test_session": True}]
