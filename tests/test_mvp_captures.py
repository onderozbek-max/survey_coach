from pathlib import Path

from fastapi.testclient import TestClient

from surveycoach.reader.models import Capture, Coverage, ReadResult
from surveycoach.server import create_app
from surveycoach.snapshot import SurveySnapshot

ROOT = Path(__file__).parent.parent


def test_only_reader_owned_saved_capture_is_served(tmp_path):
    image = tmp_path / "page.png"
    image.write_bytes(b"synthetic-png-test")
    observation = tmp_path / "page.json"
    observation.write_text("{}")
    app = create_app(tmp_path / "db")
    app.state.reader = lambda *args, **kwargs: ReadResult(
        snapshot=SurveySnapshot.model_validate_json((ROOT / "fixtures/coffee-pods.json").read_text()),
        coverage=Coverage(pages_captured=1), capture_dir=tmp_path,
        captures=[Capture(page_id="p0", viewport_png=image, observation_json=observation)])
    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/reader/jobs", json={"url": "https://sample.redjade.net/test", "approval": True}).json()
        job = client.get(f"/api/jobs/{created['job_id']}").json()
        detail = client.get(f"/api/surveys/{job['survey_id']}").json()
        assert "viewport_png" not in str(detail)
        route = f"/api/surveys/{job['survey_id']}/versions/1/captures/0"
        assert client.get(route).content == image.read_bytes()
        assert client.get(route[:-1] + "99").status_code == 404
