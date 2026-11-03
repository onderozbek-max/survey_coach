from pathlib import Path

from fastapi.testclient import TestClient

from surveycoach.llm import FakeProvider
from surveycoach.judge.schemas import Answer
from surveycoach.server import create_app
from surveycoach.snapshot import SurveySnapshot

ROOT = Path(__file__).parent.parent


def test_ask_uses_only_finding_from_saved_review(tmp_path):
    provider = FakeProvider({"Answer": Answer(text="Use neutral wording. Copy it into RedJade yourself.")})
    with TestClient(create_app(tmp_path / "db.sqlite", provider=provider), base_url="http://localhost") as client:
        snapshot = SurveySnapshot.model_validate_json((ROOT / "fixtures/boxer-briefs.json").read_text()).model_dump(mode="json")
        created = client.post("/api/surveys", json={"snapshot": snapshot}).json()
        detail = client.get(f"/api/surveys/{created['id']}").json()
        fingerprint = detail["review"]["findings"][0]["fingerprint"]
        route = f"/api/surveys/{created['id']}/versions/1/ask"
        answer = client.post(route, json={"fingerprint": fingerprint, "question": "Why is this a problem?"})
        assert answer.status_code == 200
        assert "neutral" in answer.json()["answer"]
        assert client.post(route, json={"fingerprint": "invented", "question": "Why?"}).status_code == 404
        assert client.post(route, json={"fingerprint": fingerprint, "question": " "}).status_code == 422
