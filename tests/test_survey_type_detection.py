"""Survey type auto-detection: deterministic rules, a confidence the UI can show, never a choice."""
import pytest
from fastapi.testclient import TestClient

from surveycoach.reader.survey_type import apply_detection, detect_survey_type
from surveycoach.server import create_app
from surveycoach.snapshot import Option, Page, Question, SurveySnapshot
from tests.builders import intro, thank_you

# Invented copy only.
IDEA = ("Alright, here is our idea.\nAcme Widget Tray\nImagine a tray of widgets that snap together in "
        "seconds, ready for any weeknight dinner without any mess at all.")
PLAIN_DESCRIPTION = " ".join(["The Acme Widget Tray is a sturdy tray with six compartments and a clear lid"] * 5)
INTENT = "How likely are you to buy the Acme Widget Tray?"
SCALE = ["Definitely would buy", "Probably would buy", "Would not buy"]
RATING = "How would you rate the taste of the Acme Widget you tried at home?"


def screen(position, body, text=INTENT, options=SCALE):
    q = Question(id=f"q{position}", text=text, kind="single_choice",
                 options=[Option(id=f"o{position}{i}", label=label) for i, label in enumerate(options)])
    raw = (body + "\n" if body else "") + text + "\n" + "\n".join(options) + "\nNext"
    return Page(id=f"p{position}", position=position, kind="question", questions=[q], text=raw)


def snapshot(*pages, survey_type="non_ihut_product"):
    return SurveySnapshot(title="Acme", survey_type=survey_type, pages=list(pages))


def test_concept_description_then_purchase_intent_is_a_concept_test():
    detection = detect_survey_type(snapshot(intro(), screen(1, IDEA), thank_you()))
    assert detection.type == "services_concept"
    assert 0.6 <= detection.confidence <= 1.0
    assert detection.label in {"medium", "high"}
    assert detection.reasons


def test_description_without_cue_words_counts_when_it_is_substantial():
    assert detect_survey_type(snapshot(screen(1, PLAIN_DESCRIPTION))).type == "services_concept"


def test_description_on_an_info_page_before_the_intent_question_counts():
    info = Page(id="i", position=1, kind="info", text=IDEA)
    assert detect_survey_type(snapshot(intro(), info, screen(2, ""))).type == "services_concept"


def test_repeated_concept_cells_raise_confidence():
    one = detect_survey_type(snapshot(screen(1, IDEA)))
    two = detect_survey_type(snapshot(screen(1, IDEA), screen(2, IDEA.replace("Widget", "Gadget"))))
    assert two.type == one.type == "services_concept"
    assert two.confidence > one.confidence


# Negative controls: each of these must stay a plain product test.
def plain_product_test():
    return snapshot(intro(), screen(1, "", RATING, ["Dislike", "Neutral", "Like"]), thank_you())


def test_plain_product_test_stays_non_ihut_product():
    detection = detect_survey_type(plain_product_test())
    assert detection.type == "non_ihut_product"
    assert detection.confidence <= 0.5 and detection.label == "low"


def test_purchase_intent_without_a_concept_description_stays_product():
    assert detect_survey_type(snapshot(screen(1, ""))).type == "non_ihut_product"


def test_welcome_copy_is_not_a_concept_description():
    welcome = intro("Welcome! " + "Thanks for helping us with this study, we really value your time. " * 3)
    assert detect_survey_type(snapshot(welcome, screen(1, ""))).type == "non_ihut_product"


def test_instructions_are_not_a_concept_description():
    instructions = "Please read each statement carefully and answer as honestly as you can, there are no right or wrong answers."
    assert detect_survey_type(snapshot(screen(1, instructions))).type == "non_ihut_product"


def test_description_after_the_intent_question_does_not_count():
    later = screen(2, IDEA, RATING, ["Dislike", "Neutral", "Like"])
    assert detect_survey_type(snapshot(screen(1, ""), later)).type == "non_ihut_product"


def test_description_with_only_non_intent_questions_stays_product():
    assert detect_survey_type(snapshot(screen(1, IDEA, RATING, ["Dislike", "Like"]))).type == "non_ihut_product"


def test_apply_detection_sets_only_a_default_type():
    concept = snapshot(screen(1, IDEA))
    assert apply_detection(concept).type == "services_concept"
    assert concept.survey_type == "services_concept"
    other = snapshot(screen(1, IDEA), survey_type="ihut")
    apply_detection(other)
    assert other.survey_type == "ihut"
    plain = plain_product_test()
    apply_detection(plain)
    assert plain.survey_type == "non_ihut_product"


def test_empty_snapshot_is_safe():
    assert detect_survey_type(snapshot()).type == "non_ihut_product"


@pytest.fixture
def client():
    with TestClient(create_app(":memory:"), base_url="http://localhost") as client:
        yield client


def imported(client, snap):
    return client.post("/api/surveys", json={"snapshot": snap.model_dump(mode="json")}).json()["id"]


def test_detail_exposes_detection_but_auto_detected_is_not_chosen(client):
    detail = client.get(f"/api/surveys/{imported(client, snapshot(intro(), screen(1, IDEA), thank_you()))}").json()
    detection = detail["survey_type_detection"]
    assert detection["type"] == "services_concept" and 0.6 <= detection["confidence"] <= 1.0
    assert detection["label"] in {"medium", "high"} and detection["reasons"]
    assert detail["survey_type_chosen"] is False


def test_choosing_a_type_sets_chosen_and_keeps_the_suggestion(client):
    survey_id = imported(client, snapshot(intro(), screen(1, IDEA), thank_you()))
    client.patch(f"/api/surveys/{survey_id}", json={"survey_type": "services_concept"})
    detail = client.get(f"/api/surveys/{survey_id}").json()
    assert detail["survey_type_chosen"] is True and detail["survey_type"] == "services_concept"
    assert detail["survey_type_detection"]["type"] == "services_concept"


def test_plain_product_survey_detail_stays_product_and_unchosen(client):
    detail = client.get(f"/api/surveys/{imported(client, plain_product_test())}").json()
    assert detail["survey_type"] == "non_ihut_product" and detail["survey_type_chosen"] is False
    assert detail["survey_type_detection"]["type"] == "non_ihut_product"
    assert detail["survey_type_detection"]["label"] == "low"


def test_home_list_carries_the_detection_too(client):
    imported(client, snapshot(intro(), screen(1, IDEA), thank_you()))
    assert client.get("/api/surveys").json()["surveys"][0]["survey_type_detection"]["type"] == "services_concept"
