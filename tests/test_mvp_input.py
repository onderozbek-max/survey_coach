import pytest
from fastapi.testclient import TestClient
from surveycoach.server import create_app


@pytest.mark.parametrize("pages", [[], [{"id": "p", "position": 0, "kind": "intro"}, {"id": "p", "position": 1, "kind": "intro"}]])
def test_empty_or_ambiguous_snapshots_are_rejected(tmp_path, pages):
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost") as client:
        response = client.post("/api/surveys", json={"snapshot": {"title": "Synthetic survey", "pages": pages}})
        assert response.status_code == 422
