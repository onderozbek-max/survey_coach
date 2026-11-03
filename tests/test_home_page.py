"""Home page ("launch pad") contracts: list summary data and rendered states. Synthetic only."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from surveycoach.server import create_app
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio

ROOT = Path(__file__).resolve().parents[1]


def test_survey_list_summarises_latest_review(tmp_path):
    snapshot = json.loads((ROOT / "fixtures" / "boxer-briefs.json").read_text())
    with TestClient(create_app(tmp_path / "home.sqlite3"), base_url="http://localhost") as client:
        assert client.get("/api/surveys").json()["surveys"] == []
        created = client.post("/api/surveys", json={"snapshot": snapshot}).json()
        detail = client.get(f"/api/surveys/{created['id']}").json()
        card = detail["review"]["scorecard"]
        listed = client.get("/api/surveys").json()["surveys"][0]
        assert listed["readiness"] == card["readiness"]
        assert listed["must_fix"] == sum(f["severity"] == "must_fix" for f in detail["review"]["findings"])
        assert listed["score_checked"] == [round(card["score"] - card["unchecked_points"]), 100 - card["unchecked_points"]]


def test_home_renders_cards_example_and_toned_errors(browser, studio):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(studio + "/local.html")
    # Empty state points at the hero instead of duplicating the sample button.
    page.get_by_text("Nothing reviewed yet", exact=False).wait_for()
    assert page.locator("#sample-start").count() == 1
    assert page.get_by_role("img", name="Example review result", exact=False).count() == 1
    page.get_by_label("RedJade preview link").fill("not-a-url")
    page.get_by_role("button", name="Start review", exact=True).click()
    status = page.locator("#import-status")
    page.wait_for_function("document.querySelector('#import-status').dataset.tone === 'error'")
    assert "valid HTTPS RedJade test link" in status.inner_text()
    page.get_by_label("Survey snapshot file (.json)").set_input_files(str(ROOT / "fixtures/boxer-briefs.json"))
    page.get_by_role("button", name="Start review", exact=True).click()
    page.wait_for_url("**/review.html?**", timeout=30000)
    page.goto(studio + "/local.html")
    survey_card = page.locator("#survey-list a.survey-card").first
    survey_card.wait_for()
    assert survey_card.locator(".chip").inner_text().strip()
    assert "must fix" in survey_card.inner_text().lower()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    context.close()
