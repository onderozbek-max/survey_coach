"""D6 at the API: the user's name wins, a generic stored title is projected not rewritten."""
import pytest
from fastapi.testclient import TestClient

from surveycoach.server import create_app
from tests.builders import intro, page, question, survey, thank_you

URL = "https://app.redjade.net/take/InsightsHMSQuesadillaTray"


@pytest.fixture
def client():
    with TestClient(create_app(":memory:"), base_url="http://localhost") as client:
        yield client


def import_survey(client, title="Surveys", url=URL):
    snapshot = survey(intro(), page(1, question()), thank_you(), title=title)
    snapshot.source_url = url
    created = client.post("/api/surveys", json={"snapshot": snapshot.model_dump(mode="json")}).json()
    return created["id"]


def test_generic_stored_title_is_presented_as_the_slug_without_rewriting_history(client):
    survey_id = import_survey(client)
    detail = client.get(f"/api/surveys/{survey_id}").json()
    assert detail["title"] == "Quesadilla Tray"
    assert detail["snapshot_title"] == "Surveys"
    assert detail["versions"][0]["title"] == "Surveys"
    assert detail["snapshot"]["title"] == "Surveys"
    assert detail["title_confirmed"] is False and detail["title_generic"] is False
    row = client.app.state.repository.db.execute("SELECT title FROM versions WHERE survey_id=?", (survey_id,)).fetchone()
    assert row["title"] == "Surveys"


def test_users_own_name_beats_every_derived_name(client):
    survey_id = import_survey(client)
    client.patch(f"/api/surveys/{survey_id}", json={"title": "Q4 tray study"})
    detail = client.get(f"/api/surveys/{survey_id}").json()
    assert detail["title"] == "Q4 tray study"
    assert detail["title_confirmed"] is True


def test_specific_stored_title_is_untouched(client):
    survey_id = import_survey(client, title="Spring concept study")
    assert client.get(f"/api/surveys/{survey_id}").json()["title"] == "Spring concept study"


def test_unnameable_survey_stays_generic_and_says_so(client):
    survey_id = import_survey(client, url="https://app.redjade.net/take/preview")
    detail = client.get(f"/api/surveys/{survey_id}").json()
    assert detail["title"] == "Surveys"
    assert detail["title_generic"] is True and detail["title_confirmed"] is False


def test_home_list_uses_the_same_presented_title(client):
    import_survey(client)
    assert client.get("/api/surveys").json()["surveys"][0]["title"] == "Quesadilla Tray"
