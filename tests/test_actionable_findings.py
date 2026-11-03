"""Findings must be actionable: a problem-first headline, and paste-ready text wherever a check can produce it."""
from pathlib import Path

import pytest

from surveycoach.checks.structure import fixed_intro
from surveycoach.checks.text import limit_emoji, plural, sentence_case, swap_word
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def flawed():
    return run_review(SurveySnapshot.model_validate_json((FIXTURES / "boxer-briefs.json").read_text()))


def by_criterion(review, criterion_id):
    return [f for f in review.findings if f.criterion_id == criterion_id]


def test_every_finding_has_a_problem_first_headline_not_the_rubric_title(flawed):
    rubric = load_rubric()
    titles = {c.title for c in rubric.criteria} | {b.title for b in rubric.blockers}
    for f in flawed.findings:
        assert f.headline.strip() and len(f.headline) <= 75, f.headline
        assert f.headline not in titles, f"{f.criterion_id} headline is just the rubric title"


def test_overlapping_ranges_name_the_answer_and_lower_its_top_number(flawed):
    (f,) = by_criterion(flawed, "4.2")
    assert "overlap" in f.headline.lower()
    assert (f.current_text, f.suggested_text) == ("1 to 5 years", "1 to 4 years")


def test_missing_select_all_gets_the_instruction_appended(flawed):
    (f,) = by_criterion(flawed, "3.3")
    assert f.suggested_text == f"{f.current_text} Select all that apply."


def test_click_becomes_tap_and_the_word_is_highlighted(flawed):
    f = next(f for f in by_criterion(flawed, "6.4") if f.highlight == "Click")
    assert f.current_text == "Click the one you like best."
    assert f.suggested_text == "Tap the one you like best."


def test_one_intro_finding_fixes_time_without_inventing_reward_terms(flawed):
    (f,) = by_criterion(flawed, "1.4")
    assert "3 min" in f.headline and "reward" in f.headline
    assert f.suggested_text == "Welcome to the Boxer Briefs Survey! This takes about 4 minutes."


def test_jargon_is_highlighted_and_removed_from_the_suggestion(flawed):
    (f,) = by_criterion(flawed, "3.2")
    assert f.highlight.lower() == "aforementioned"
    assert "aforementioned" not in f.suggested_text and "about the boxer briefs." in f.suggested_text


def test_unlabeled_scale_end_gets_a_matching_label(flawed):
    f = next(f for f in by_criterion(flawed, "4.4") if f.question_id == "q11")
    assert f.current_text == "Not at all likely ... (no label)"
    assert f.suggested_text == "Not at all likely ... Extremely likely"


def test_broken_image_names_the_image_and_costs_renders_cleanly_credit_without_a_duplicate_finding(flawed):
    (blocker,) = by_criterion(flawed, "B7")
    assert "Relaxed fit" in blocker.headline and blocker.element_id == "img3"
    assert by_criterion(flawed, "6.5") == []
    assert "Stays put and renders cleanly" not in flawed.scorecard.strengths


def test_the_time_overrun_is_reported_even_though_it_is_below_the_blocker_threshold(flawed):
    assert not by_criterion(flawed, "B5") and flawed.est_minutes > flawed.promised_minutes * 1.25
    assert any("takes about 4" in f.headline for f in by_criterion(flawed, "1.4"))


def test_intro_fixer_keeps_what_is_right():
    assert fixed_intro("Hi! This takes 5 minutes.", 5.2, fix_time=False, add_reward=True) == "Hi! This takes 5 minutes."
    assert fixed_intro("Hi!", 2.2, fix_time=True, add_reward=False) == "Hi! This takes about 2 minutes."


def test_text_helpers():
    assert plural(1, "answer") == "1 answer" and plural(2, "answer") == "2 answers"
    assert sentence_case("How Do You Like Member's Mark Boxer Briefs?") == "How do you like Member's Mark boxer briefs?"
    assert swap_word("Click here, then click Next.", "click", "tap") == "Tap here, then tap Next."
    assert limit_emoji("Hi \U0001F600 there \U0001F389", keep=1) == "Hi \U0001F600 there"


def test_a_strength_never_sits_next_to_a_finding_in_the_same_area(flawed):
    flagged = {c.title for c in load_rubric().criteria if c.id in {f.criterion_id for f in flawed.findings}}
    assert not flagged & set(flawed.scorecard.strengths)
