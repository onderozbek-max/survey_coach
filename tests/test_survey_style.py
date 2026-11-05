"""Survey style is mutable metadata; captured evidence is not."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from builders import context, intro, page, question, survey, thank_you
from surveycoach.checks.content import content_standards, emoji_rule
from surveycoach.judge.batches import BATCHES
from surveycoach.judge.cache import JudgeCache
from surveycoach.judge.prompts import PROMPT_VERSION, system_prompt
from surveycoach.judge.schemas import BatchOutput
from surveycoach.llm import FakeProvider
from surveycoach.rubric import load_rubric
from surveycoach.server import create_app
from surveycoach.server.repository import Repository, SCHEMA
from surveycoach.server.service import run_job


def snapshot(style="non_ihut_product", text="What did you do this Halloween? \U0001F383"):
    return survey(intro("Welcome \U0001F383\U0001F36C"), page(1, question(
        text=text, options=("Trick-or-treat \U0001F36C", "Stayed home"))), thank_you(), survey_type=style)


def test_community_emoji_with_words_is_allowed():
    assert emoji_rule(context(snapshot("community_pulse"))).findings == []


@pytest.mark.parametrize("label", ["\U0001F44D", " \U0001F44D !", "\U0001F44D\U0001F3FD"])
def test_community_emoji_only_answer_is_flagged(label):
    data = snapshot("community_pulse")
    data.pages[1].questions[0].options[0].label = label
    findings = emoji_rule(context(data)).findings
    assert len(findings) == 1
    assert findings[0].headline == "Answer is only an emoji"
    assert findings[0].explanation == (
        "Add a word next to the emoji so every member, and screen readers, get the same meaning.")
    assert findings[0].member_impact == "An emoji can look different on each phone."  # 1C: plain, <= 20 words
    assert findings[0].steps == ["Add a word next to the emoji in this answer."]


@pytest.mark.parametrize("text,flagged", [
    ("Which treats DIDN'T you like?", False),
    ("WHICH TREATS DID YOU LIKE", True),
    ("Which treats did you LOVE or HATE?", True),
])
def test_community_caps_emphasis(text, flagged):
    findings = content_standards(context(snapshot("community_pulse", text))).findings
    assert any("ALL CAPS" in f.headline for f in findings) is flagged


def test_default_tone_is_unchanged():
    assert len(emoji_rule(context(snapshot())).findings) == 3
    assert any("ALL CAPS" in f.headline for f in content_standards(
        context(snapshot(text="Which treats DIDN'T you like?"))).findings)


def stored(path):
    with sqlite3.connect(path) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in ("versions", "reviews", "decisions")}


def test_patch_projects_style_without_rewriting_history(tmp_path):
    path = tmp_path / "test.db"
    with TestClient(create_app(path), base_url="http://localhost") as client:
        created = client.post("/api/surveys", json={"snapshot": snapshot().model_dump()}).json()
        url = "/api/surveys/" + created["id"]
        before = client.get(url).json()
        finding = next(f for f in before["review"]["findings"] if f["criterion_id"] == "9.1")
        assert client.put(url + "/versions/1/decisions/" + finding["fingerprint"], json={
            "action": "keep", "reason": "Community voice"}).status_code == 200
        immutable = stored(path)
        response = client.patch(url, json={"survey_type": "community_pulse"})
        assert response.status_code == 200
        after = client.get(url).json()
        assert after["survey_type"] == "community_pulse"
        assert after["survey_type_chosen"] is True
        assert before["survey_type_chosen"] is False
        assert after["snapshot"] == before["snapshot"]
        assert not [f for f in after["review"]["findings"] if f["criterion_id"] == "9.1"]
        assert after["review"]["findings"] != before["review"]["findings"]
        assert client.get(url + "/versions/1").json()["review"] == after["review"]
        assert client.patch(url, json={"survey_type": "nonsense"}).status_code == 422
        assert client.patch(url, json={"title": "x"}).json()["title"] == "x"
        for body in ({}, {"title": None}, {"survey_type": None}, {"other": True},
                     {"title": " "}, {"title": 12}, {"title": "x\ny"}):
            assert client.patch(url, json=body).status_code == 422
        assert client.patch("/api/surveys/missing", json={"survey_type": "community_pulse"}).status_code == 404
        assert stored(path) == immutable


def test_list_uses_effective_type_for_score(tmp_path):
    repository = Repository(tmp_path / "test.db")
    try:
        data = snapshot(text="Which treats did you LOVE?")
        data.pages[1].questions.extend([
            question("q2", text="Which treats did you HATE?"),
            question("q3", text="Which treats did you LIKE?"),
        ])
        created = repository.submit(data, False)
        run_job(repository, created["job_id"])
        old_score = repository.list_surveys()[0]["methodology"]["score_checked"]
        repository.update(created["id"], survey_type="community_pulse")
        seen = repository.list_surveys()[0]
        card = repository.detail(created["id"])["review"]["scorecard"]
        assert seen["methodology"]["score_checked"] == [round(card["score"]), card["checked_points"]]
        assert seen["methodology"]["score_checked"] != old_score
        assert seen["survey_type"] == "community_pulse"
        assert seen["survey_type_chosen"] is True
    finally:
        repository.close()


def test_job_provider_gets_chosen_type(tmp_path, monkeypatch):
    monkeypatch.setenv("SURVEYCOACH_HOME", str(tmp_path / "home"))
    provider = FakeProvider({"BatchOutput": BatchOutput()})
    repository = Repository(tmp_path / "test.db")
    try:
        created = repository.submit(snapshot(), True)
        repository.update(created["id"], survey_type="community_pulse")
        run_job(repository, created["job_id"], provider)
        assert repository.job(created["job_id"])["status"] == "completed"
        assert provider.calls
        assert all("(type: community_pulse)" in data for _, data, _ in provider.calls)
        assert repository.detail(created["id"])["snapshot"]["survey_type"] == "non_ihut_product"
    finally:
        repository.close()


def test_prompt_and_cache_are_style_aware(tmp_path):
    rubric = load_rubric()
    assert rubric.length_targets_minutes["community_pulse"] == (5, 8)
    assert PROMPT_VERSION == "9"
    assert ("If the survey type is community_pulse, emoji, exclamation marks and playful wording are part of "
            "the community voice; flag them only when they hide meaning.") in system_prompt(BATCHES[0], rubric)
    cache = JudgeCache(tmp_path)
    assert cache.key(snapshot(), rubric, BATCHES[0]) != cache.key(snapshot("community_pulse"), rubric, BATCHES[0])


def test_migration_and_rename_compatibility(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute("ALTER TABLE surveys ADD COLUMN display_title TEXT")
    repository = Repository(path)
    created = repository.submit(snapshot(), False)
    assert repository.rename(created["id"], "Renamed")["title"] == "Renamed"
    repository.update(created["id"], title="Combined", survey_type="community_pulse")
    with pytest.raises(KeyError):
        repository.update("missing", survey_type="community_pulse")
    with pytest.raises(ValueError):
        repository.update(created["id"], survey_type="nonsense")
    repository.close()
    reopened = Repository(path)
    try:
        detail = reopened.detail(created["id"])
        assert detail["title"] == "Combined"
        assert detail["survey_type"] == "community_pulse"
        assert detail["snapshot"]["title"] != "Combined"
    finally:
        reopened.close()
