"""D-Checklist: a curated You check list, each item only when the evidence calls for it."""
import re

import pytest

from builders import image, intro, page, question, survey
from concept_fixture import concept_survey
from surveycoach.labels import screen_labels
from surveycoach.recommendations import banned_words
from surveycoach.snapshot import Option
from surveycoach.timing import estimate
from surveycoach.you_check import MAX_ITEMS, build_you_checks

ORDER = ["images", "display_logic", "randomization", "required", "other_text", "timed_run"]


def items(snapshot, target_high=10):
    return build_you_checks(snapshot, screen_labels(snapshot), estimate(snapshot), target_high)


def ids(snapshot, **kw):
    return [item["id"] for item in items(snapshot, **kw)]


def test_concept_test_gets_all_six_in_theme_order_and_never_more():
    out = items(concept_survey())
    assert [i["id"] for i in out] == ORDER
    assert len(out) <= MAX_ITEMS == 6


def test_every_item_has_the_full_contract():
    for item in items(concept_survey()):
        assert re.fullmatch(rf"you-check:{item['id']}:[0-9a-f]{{8}}", item["fingerprint"])
        for key in ("theme", "title", "instruction", "where", "signal", "covers"):
            assert item[key], key
        assert isinstance(item["pages"], list) and isinstance(item["screens"], list)
        assert item["instruction"].count("?") == 1
        assert len(item["instruction"].split()) <= 40 and len(item["title"].split()) <= 8
        assert banned_words(" ".join([item["title"], item["instruction"], item["where"]])) == []


def test_fingerprints_are_stable_unique_and_track_the_evidence():
    first = {i["id"]: i["fingerprint"] for i in items(concept_survey())}
    assert first == {i["id"]: i["fingerprint"] for i in items(concept_survey())}
    assert len(set(first.values())) == 6
    other = concept_survey()   # a new place with an Other option changes only that item
    other.pages[1].questions[0].options.append(Option(id="w-other", label="Other"))
    changed = {i["id"]: i["fingerprint"] for i in items(other)}
    assert changed["other_text"] != first["other_text"]
    assert {k: v for k, v in changed.items() if k != "other_text"} == {
        k: v for k, v in first.items() if k != "other_text"}


def test_a_plain_survey_has_no_you_check_items():
    plain = survey(page(1, question(required=True)), page(2, question("q2", required=True)))
    assert items(plain) == []


# --- images ---------------------------------------------------------------------------------

def test_images_need_media_to_exist():
    assert "images" not in ids(survey(page(1, question(required=True)), page(2)))


def test_images_from_page_question_option_and_declared_media():
    q = question(required=True)
    q.media = [image()]
    assert ids(survey(page(1, q))) == ["images"]
    p = page(1, question(required=True))
    p.media = [image()]
    assert ids(survey(p)) == ["images"]
    q2 = question(required=True)
    q2.options[0].media = image()
    assert ids(survey(page(1, q2))) == ["images"]
    p3 = page(1, question(required=True))
    p3.declared_media = 2
    p3.visual_evidence = "definition_only"
    assert ids(survey(p3)) == ["images"]


def test_images_item_points_at_the_screens_with_images():
    out = {i["id"]: i for i in items(concept_survey())}["images"]
    assert out["screens"] == [13] and out["pages"] == ["p12"]
    assert "13" in out["instruction"] and "phone" in out["instruction"]
    assert out["signal"] == "phone"


# --- display logic --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("What about this tray has you saying 'Yes, please!'?", True),
    ("Why did you choose that brand?", True),
    ("You said you buy snacks. Which one do you buy most?", True),
    ("Based on your earlier answer, how often?", True),
    ("What is your age?", False),
    ("Do you want to say more?", False),
])
def test_display_logic_only_for_wording_that_assumes_an_earlier_answer(text, expected):
    s = survey(page(1, question("q1", required=True)), page(2, question("q2", text=text, required=True)))
    assert ("display_logic" in ids(s)) is expected


def test_display_logic_names_the_questions_and_screens():
    out = {i["id"]: i for i in items(concept_survey())}["display_logic"]
    assert out["questions"] == ["Q4", "Q6", "Q8"] and out["screens"] == [5, 7, 9]
    assert out["instruction"].startswith("Q4, Q6 and Q8")


# --- randomization --------------------------------------------------------------------------

def test_randomization_needs_repeated_concept_blocks_not_just_repeats():
    q = lambda n: question(f"r{n}", "Would you buy this?", options=("Yes", "No"), required=True)
    plain = survey(page(1, q(1)), page(2, q(2)))
    assert "randomization" not in ids(plain)
    one = survey(page(1, q(1), text="A kit with eggs and peppers.\nWould you buy this?\nYes\nNo"))
    assert "randomization" not in ids(one)


def test_randomization_lists_each_repeated_concept_screen():
    out = {i["id"]: i for i in items(concept_survey())}["randomization"]
    assert out["pages"] == ["p3", "p5", "p7"] and out["screens"] == [4, 6, 8]
    assert out["instruction"].startswith("Are the 3 ")
    assert out["signal"] == "honest"


# --- required (tri-state) -------------------------------------------------------------------

def test_required_asks_only_when_requiredness_is_unknown_or_verified_optional():
    assert "required" not in ids(survey(page(1, question(required=True))))
    assert "required" in ids(survey(page(1, question(required=None))))
    assert "required" in ids(survey(page(1, question(required=False))))


def test_open_text_and_conditional_follow_ups_are_not_key_questions():
    s = survey(page(1, question("q1", kind="text_long", options=(), required=None)),
               page(2, question("q2", text="You said yes. Why did you choose it?", required=None)),
               page(3, question("q3", required=None, conditional=True)))
    assert "required" not in ids(s)


def test_required_item_names_the_key_questions():
    out = {i["id"]: i for i in items(concept_survey())}["required"]
    assert out["questions"] == ["Q1", "Q2", "Q3", "Q5", "Q7", "Q9", "Q10"]
    assert "Q1" in out["instruction"] and "more" in out["instruction"]
    assert out["signal"] == "honest"


# --- other (please specify) -----------------------------------------------------------------

def test_other_text_box_only_when_an_other_option_has_no_confirmed_text_box():
    def with_other(flag, label="Other (please specify)"):
        q = question(options=("A", "B"), required=True)
        q.options.append(Option(id="o", label=label, is_other_with_text=flag))
        return survey(page(1, q))
    assert "other_text" in ids(with_other(None))
    assert "other_text" in ids(with_other(False))
    assert "other_text" not in ids(with_other(True))
    assert "other_text" not in ids(survey(page(1, question(required=True))))
    assert "other_text" not in ids(with_other(None, label="Otherwise"))
    assert "other_text" in ids(with_other(None, label="Something else"))


def test_other_text_item_quotes_the_option_and_lists_other_questions():
    out = {i["id"]: i for i in items(concept_survey())}["other_text"]
    assert out["questions"] == ["Q4", "Q6", "Q8"]
    assert "Something else (please specify)" in out["instruction"] and "Q6" in out["instruction"]


# --- timed run ------------------------------------------------------------------------------

def test_timed_run_for_branching_or_a_promise_but_not_for_length_alone():
    plain = survey(page(1, question(required=True)))
    assert "timed_run" not in ids(plain)
    branching = survey(page(1, question(required=True, conditional=True)))
    assert "timed_run" in ids(branching)
    promised = survey(intro("Welcome! This takes 3 minutes."), page(1, question(required=True)))
    assert "timed_run" in ids(promised)
    long_one = survey(page(1, question(required=True), text="word " * 2000))
    assert "timed_run" not in ids(long_one, target_high=5)   # over target is the duration item's job


def test_timed_run_instruction_quotes_the_promise_or_the_estimate():
    promised = survey(intro("Welcome! This takes 3 minutes."), page(1, question(required=True)))
    out = items(promised)[0]
    assert "3 minutes" in out["instruction"] and out["screens"] == [] and out["signal"] == "time"
    branching = survey(page(1, question(required=True, conditional=True)))
    assert "about 1 minute" in items(branching)[0]["instruction"]


def test_items_never_mutate_the_snapshot():
    s = concept_survey()
    before = s.model_dump()
    items(s)
    assert s.model_dump() == before
