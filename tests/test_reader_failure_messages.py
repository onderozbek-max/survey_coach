"""Failure diagnostics must help the owner without leaking preview links or tokens."""
from fastapi.testclient import TestClient
from types import SimpleNamespace
from surveycoach.snapshot import SurveySnapshot, Page

from surveycoach.reader.policy import UnsafeSurveyURL
from surveycoach.server import create_app


def test_dns_failure_is_actionable_and_does_not_leak_link(tmp_path):
    app = create_app(tmp_path / "db")
    def unavailable(*args, **kwargs):
        raise UnsafeSurveyURL("Survey host could not be safely resolved.")
    app.state.reader = unavailable
    with TestClient(app, base_url="http://localhost") as client:
        started = client.post("/api/reader/jobs", json={"url": "https://sample.redjade.net/private-preview", "approval": True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert job["status"] == "failed"
        assert "connect" in job["error"].lower()
        assert "VPN" in job["error"]
        assert "private-preview" not in job["error"]
        assert "previous review" not in job["error"]  # no previous survey exists


def test_loading_only_page_is_not_a_completed_review(tmp_path):
    app = create_app(tmp_path / "db")
    app.state.reader = lambda *a, **k: SimpleNamespace(coverage=SimpleNamespace(warnings=[]), snapshot=SurveySnapshot(title="Survey", pages=[Page(id="loading", position=0, kind="info", text="Loading")]))
    with TestClient(app, base_url="http://localhost") as client:
        started = client.post("/api/reader/jobs", json={"url": "https://sample.redjade.net/test", "approval": True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert job["status"] == "failed"
        assert "startup" in job["error"].lower()
        assert client.get("/api/surveys").json()["surveys"] == []


def test_unexpected_failure_exposes_only_reference_not_exception(tmp_path):
    app = create_app(tmp_path / "db")
    def broken(*args, **kwargs):
        raise RuntimeError("sensitive local path and survey text")
    app.state.reader = broken
    with TestClient(app, base_url="http://localhost") as client:
        started = client.post("/api/reader/jobs", json={"url": "https://sample.redjade.net/test", "approval": True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert "reference" in job["error"].lower()
        assert "sensitive" not in job["error"]
