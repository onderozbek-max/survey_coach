"""The per-survey reward answer (brief 4.8): None keeps the question, False stops the nagging, True checks the text."""
import pytest
from fastapi.testclient import TestClient

from builders import intro, page, question, survey, thank_you
from concept_fixture import concept_survey
from review_helpers import save_review
from surveycoach.checks import structure
from surveycoach.checks.registry import ReviewContext
from surveycoach.review import run_review
from surveycoach.reward import REWARD_TEXT_MAX, Reward
from surveycoach.rubric import load_rubric
from surveycoach.server import create_app
from surveycoach.server.repository import Repository

NO_REWARD_TEXT = "Thanks for helping! This takes about 1 minute."


def check(intro_text, reward=Reward(), **extra):
    snap = survey(intro(intro_text), page(1, question()), thank_you())
    return structure.time_and_reward(ReviewContext.build(snap, load_rubric(), reward, **extra))


def test_unanswered_keeps_the_question_as_a_you_check():
    result = check(NO_REWARD_TEXT)
    assert result.fraction == 0.5
    (found,) = result.findings
    assert found.headline == "Welcome doesn't mention a reward"
    assert found.you_check == "If members get a reward, is the exact reward in the welcome text?"


def test_no_reward_answer_stops_the_nagging_and_the_check_passes():
    result = check(NO_REWARD_TEXT, Reward(has_reward=False))
    assert result.findings == [] and result.fraction == 1.0


def test_no_reward_answer_does_not_hide_a_missing_time():
    result = check("Thanks for helping!", Reward(has_reward=False))
    (found,) = result.findings
    assert found.headline == "Welcome doesn't say how long it takes"
    assert "reward" not in (found.evidence + found.explanation + found.member_impact).lower()


def test_yes_with_text_only_checks_the_welcome_mentions_it():
    asked = check(NO_REWARD_TEXT, Reward(has_reward=True, text="500 bonus credits"))
    (found,) = asked.findings
    assert "500 bonus credits" in found.you_check and "welcome" in found.you_check.lower()
    assert "If members get" not in found.you_check
    said = check("Thanks! This takes about 1 minute and you earn 500 bonus credits.",
                 Reward(has_reward=True, text="500 bonus credits"))
    assert said.findings == [] and said.fraction == 1.0


def test_yes_is_satisfied_by_any_reward_wording_or_the_typed_text():
    assert check("About 1 minute. You'll earn points!", Reward(has_reward=True, text="a tote bag")).findings == []
    assert check("About 1 minute, then a tote bag is yours.", Reward(has_reward=True, text="A TOTE   bag")).findings == []


def test_yes_without_text_asks_what_the_reward_is():
    (found,) = check(NO_REWARD_TEXT, Reward(has_reward=True)).findings
    assert "reward" in found.you_check.lower() and "welcome" in found.you_check.lower()


def test_the_default_context_is_unanswered():
    snap = survey(intro(NO_REWARD_TEXT), page(1, question()), thank_you())
    assert ReviewContext.build(snap, load_rubric()).reward == Reward()
    assert run_review(snap).results["1.4"].findings


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "reward.db")
    yield repository
    repository.close()


def saved(repo, snapshot=None):
    return save_review(repo, snapshot or concept_survey())


def reward_findings(detail):
    return [f for f in detail["review"]["findings"] if f["criterion_id"] == "1.4"]


def test_detail_exposes_the_answer_and_it_steers_the_finding_and_verdict(repo):
    survey_id = saved(repo)
    first = repo.detail(survey_id)
    assert first["reward"] == {"has_reward": None, "text": ""}
    assert reward_findings(first)
    repo.set_reward(survey_id, False, "")
    answered = repo.detail(survey_id)
    assert answered["reward"] == {"has_reward": False, "text": ""}
    assert reward_findings(answered) == []
    assert answered["overview"]["verdict"]["tiles"]["you_check"] == first["overview"]["verdict"]["tiles"]["you_check"] - 1
    repo.set_reward(survey_id, True, "double points")
    asked = repo.detail(survey_id)
    (found,) = reward_findings(asked)
    assert "double points" in found["you_check"] and asked["reward"]["text"] == "double points"
    repo.set_reward(survey_id, None, "")
    assert repo.detail(survey_id)["reward"]["has_reward"] is None
    assert reward_findings(repo.detail(survey_id))


def test_a_decision_on_the_reward_item_survives_only_while_the_item_stays_the_same(repo):
    survey_id = saved(repo)
    fingerprint = reward_findings(repo.detail(survey_id))[0]["fingerprint"]
    repo.save_decision(survey_id, 1, fingerprint, {"action": "done"})
    repo.set_reward(survey_id, False, "")
    assert repo.detail(survey_id)["decisions"].get(fingerprint) is None      # the item is gone, so is its decision


def test_the_answer_applies_to_earlier_versions_of_the_same_survey(repo):
    survey_id = saved(repo)
    repo.set_reward(survey_id, False, "")
    changed = concept_survey().model_copy(deep=True)
    changed.pages[1].questions[0].text = "How often do you make breakfast at home?"
    save_review(repo, changed, survey_id)
    assert reward_findings(repo.detail(survey_id, 1)) == [] and reward_findings(repo.detail(survey_id, 2)) == []


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "http.db")
    with TestClient(app, base_url="http://localhost") as client:
        yield client, app.state.repository


def url(survey_id):
    return f"/api/surveys/{survey_id}/reward"


def test_http_sets_and_reads_back_the_answer(client):
    http, repository = client
    survey_id = saved(repository)
    saved_answer = http.put(url(survey_id), json={"has_reward": True, "text": "  Earn\n 50   points \u202e "})
    assert saved_answer.status_code == 200
    assert saved_answer.json()["reward"] == {"has_reward": True, "text": "Earn 50 points"}
    assert http.get(f"/api/surveys/{survey_id}").json()["reward"] == {"has_reward": True, "text": "Earn 50 points"}
    assert http.put(url(survey_id), json={"has_reward": False}).json()["reward"] == {"has_reward": False, "text": ""}
    assert http.put(url(survey_id), json={"has_reward": None}).json()["reward"] == {"has_reward": None, "text": ""}


@pytest.mark.parametrize("body", [
    {}, {"text": "points"}, {"has_reward": "yes"}, {"has_reward": 1},
    {"has_reward": True, "text": "x" * (REWARD_TEXT_MAX + 1)},
    {"has_reward": False, "text": "points"}, {"has_reward": None, "text": "points"},
    {"has_reward": True, "text": 5}, {"has_reward": True, "extra": 1}, {"has_reward": True, "text": "x" * 5000},
])
def test_http_rejects_bad_input_with_422(client, body):
    http, repository = client
    survey_id = saved(repository)
    assert http.put(url(survey_id), json=body).status_code == 422
    assert http.get(f"/api/surveys/{survey_id}").json()["reward"] == {"has_reward": None, "text": ""}


def test_http_accepts_exactly_the_maximum_and_404s_an_unknown_survey(client):
    http, repository = client
    survey_id = saved(repository)
    assert http.put(url(survey_id), json={"has_reward": True, "text": "x" * REWARD_TEXT_MAX}).status_code == 200
    assert http.put(url("nope"), json={"has_reward": False}).status_code == 404


def test_markup_is_stored_as_typed_and_never_interpreted(client):
    http, repository = client
    survey_id = saved(repository)
    http.put(url(survey_id), json={"has_reward": True, "text": "<b>50</b> & more"})
    assert http.get(f"/api/surveys/{survey_id}").json()["reward"]["text"] == "<b>50</b> & more"


def test_detected_type_carries_a_confidence_label_and_a_confirmed_flag(repo):
    survey_id = saved(repo)
    detail = repo.detail(survey_id)
    detection = detail["survey_type_detection"]
    assert detection["label"] in {"high", "medium", "low"} and 0 <= detection["confidence"] <= 1
    assert detection["confirmed"] is False and detail["survey_type_chosen"] is False
    repo.update(survey_id, survey_type="community_pulse")
    again = repo.detail(survey_id)
    assert again["survey_type_detection"]["confirmed"] is True and again["survey_type_chosen"] is True
    home = next(s for s in repo.list_surveys() if s["id"] == survey_id)
    assert home["survey_type_detection"]["confirmed"] is True and home["reward"] == again["reward"]


def test_the_time_target_follows_the_confirmed_type(repo):
    survey_id = saved(repo, concept_survey("non_ihut_product"))
    unconfirmed = repo.detail(survey_id)["overview"]["verdict"]["time"]
    repo.update(survey_id, survey_type="community_pulse")
    confirmed = repo.detail(survey_id)["overview"]["verdict"]["time"]
    assert confirmed["type_source"] == "confirmed" and confirmed["survey_type"] == "community_pulse"
    rubric = load_rubric()
    assert (confirmed["target_low"], confirmed["target_high"]) == tuple(rubric.length_targets_minutes["community_pulse"])
    assert unconfirmed["type_source"] != "confirmed"
