from fastapi.testclient import TestClient

from surveycoach.server import create_app


def test_sample_import_requires_no_file_and_no_model(tmp_path):
    with TestClient(create_app(tmp_path / "studio.db"), base_url="http://localhost") as client:
        response = client.post("/api/samples/boxer-briefs", json={})
        assert response.status_code == 202
        job = client.get(f"/api/jobs/{response.json()['job_id']}").json()
        assert job["status"] == "completed" and not job["ai_requested"]
        detail = client.get(f"/api/surveys/{job['survey_id']}").json()
        assert detail["review"]["findings"] and detail["review"]["ai"] is None
        assert client.post("/api/samples/not-real", json={}).status_code == 404
