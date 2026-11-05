"""Rules-only reading/list recommendations: useful without guessing research intent."""
from copy import deepcopy

import pytest

from builders import context, one_question_survey, question
from surveycoach.checks import content, phone
from surveycoach.checks.reading import simpler_question
from surveycoach.review import run_review


MEAL = ("How often do you purchase ready-to-heat or ready-to-cook meal solutions, "
        "such as prepared meals or meal kits, to enjoy at home?")
# Keeps the verb ("enjoy"), the category and the examples (brief 6.1, Q1 row).
REWRITE = ("How often do you buy ready-to-heat or ready-to-cook meals, like prepared meals or meal kits, "
           "to enjoy at home?")


def reading(text):
    return content.plain_words(context(one_question_survey(question(text=text)))).findings[0]


def test_grade_is_plain_english_and_explains_limits_not_a_scientific_pass():
    f = reading(MEAL)
    assert f.headline == "Members may struggle to read this question"
    details = f.explanation.lower()
    assert "automated" in details and "us school" in details
    assert "actual comprehension" in details and "not" in details
    assert "review cue" in details and "pass" in details
    assert "8" in details and "configured" in details
    assert f.current_text == MEAL and f.suggested_text == REWRITE
    assert f.options == [] and f.source == "auto"


@pytest.mark.parametrize("original,expected", [
    (MEAL.replace("How often", "Where"), REWRITE.replace("How often", "Where")),
    (MEAL.replace("prepared meals or meal kits", "meal kits or prepared meals"),
     REWRITE.replace("prepared meals or meal kits", "meal kits or prepared meals")),
    ("How often do you purchase refrigerated products for everyone in your household?",
     "How often do you buy refrigerated products for everyone in your household?"),
])
def test_bounded_swaps_preserve_other_words(original, expected):
    assert reading(original).suggested_text == expected


@pytest.mark.parametrize("text", [
    "How frequently is refrigeration necessary for maintaining the characteristics of this product?",
    "How frequently do you reconsider the purchase of an unfamiliar refrigerated product?",
    "How frequently do you purchase insurance policies for protection against accidental damage?",
    'How frequently do you interpret the phrase "do you purchase" in advertising communications?',
    "How frequently would you distinguish prepared meals from meal kits when considering refrigeration?",
])
def test_unknown_or_ambiguous_wording_gets_concrete_manual_steps_not_a_fake_rewrite(text):
    f = reading(text)
    # Insurance 'purchase' is a valid verb swap; it must not invent a meal question.
    if "insurance" in text:
        assert f.suggested_text == text.replace("purchase", "buy")
    else:
        assert f.suggested_text is None
        assert "Keep" in f.explanation and "answer choices" in f.explanation
        assert "Read" in f.explanation and "study owner" in f.explanation
    assert f.options == []


@pytest.mark.parametrize("original", [
    MEAL.replace("prepared meals or meal kits", "prepared meals, meal kits or frozen pizza"),
    MEAL.replace("meal kits,", "meal kits with organic ingredients,"),
    MEAL.replace("at home?", "at home during the past month?"),
    MEAL.replace("ready-to-heat or ready-to-cook", "ready-to-heat but not ready-to-cook"),
])
def test_restructure_declines_unknown_examples_qualifiers_and_preparation_changes(original):
    # The local verb swap is safe, but the rest must remain byte-for-byte intact.
    assert simpler_question(original) == original.replace("purchase", "buy")


@pytest.mark.parametrize("original", [
    "How often do you reconsider the purchase of meal kits?",
    'What does "do you purchase meal kits" mean to you?',
    "What does ‘do you purchase meal kits’ mean to you?",
])
def test_rewrite_is_never_a_generic_topic_based_question(original):
    assert simpler_question(original) is None


TRAYS = ("Larger tray", "Smaller tray", "Different filling", "More cheese", "Less cheese",
         "Different sauce", "Different packaging", "Lower price", "Other", "None of these")


def list_finding(options):
    q = question(text="What would you change?", options=options)
    before = deepcopy(q)
    result = phone.tappable_answers(context(one_question_survey(q)))
    assert q == before
    return next(f for f in result.findings if "choices" in f.headline)


def test_long_list_threshold_is_a_review_cue_and_groups_actual_options_without_deleting():
    f = list_finding(TRAYS)
    assert f.headline == "10 answer choices; review the phone layout"
    explanation = f.explanation.lower()
    assert "8" in explanation and "review cue" in explanation
    assert "configured" in explanation and "optimum" in explanation
    assert '"Larger tray"' in f.explanation and '"Smaller tray"' in f.explanation
    assert "heading" in explanation and "distinct" in explanation
    assert "order" in explanation and "random" in explanation
    assert "cut to" not in explanation and "alphabetize" not in explanation
    assert f.suggested_text is None and f.options == []


def test_no_obvious_group_gives_grounded_manual_guidance_without_inventing_categories():
    f = list_finding(("Avocado", "Bread", "Coffee", "Dates", "Eggs", "Fish", "Grapes", "Honey", "Ice", "Juice"))
    assert '"Avocado"' in f.explanation and '"Bread"' in f.explanation
    assert "study owner" in f.explanation and "distinct" in f.explanation
    assert f.suggested_text is None


def test_ordered_and_randomized_lists_never_get_sorting_or_removal_advice():
    f = list_finding(tuple(f"{n} times per month" for n in range(1, 11)))
    assert "preserve" in f.explanation.lower() and "order" in f.explanation.lower()
    assert "alphabetize" not in f.explanation.lower()
    assert f.suggested_text is None


def test_eight_choices_is_not_reported_as_a_list_problem():
    result = phone.tappable_answers(context(one_question_survey(question(options=TRAYS[:8]))))
    assert not result.findings


def test_rules_only_review_exposes_actionable_safe_rewrite_and_manual_list_guidance():
    snapshot = one_question_survey(question(text=MEAL, options=TRAYS))
    before = snapshot.model_dump()
    review = run_review(snapshot)
    reading_f = next(f for f in review.findings if f.criterion_id == "3.2")
    choices_f = next(f for f in review.findings if f.criterion_id == "6.2" and "choices" in f.headline)
    assert reading_f.suggested_text == REWRITE
    assert choices_f.suggested_text is None and "Larger tray" in choices_f.explanation
    assert all(f.source == "auto" for f in review.findings)
    assert snapshot.model_dump() == before
