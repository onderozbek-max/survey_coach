"""Offline contracts for exact reading deduplication and grounded welcome advice."""
from dataclasses import replace

import pytest

from builders import context, page, question, survey
from surveycoach.checks import structure
from surveycoach.snapshot import Option, Page, Question, SurveySnapshot
from surveycoach.timing import TimingConstants, estimate


WELCOME = ("We're cooking up some new meal ideas, and we'd love your input! "
           "Today we're exploring quesadilla meal kits.")


def captured_question():
    return Question(id="q1", text="How often do you buy meal kits?", kind="single_choice",
                    help_text="Choose one answer.", options=[
                        Option(id="a", label="About once a week"),
                        Option(id="b", label="Never"),
                    ])


def timed_page(raw="", intro="", questions=None):
    return estimate(SurveySnapshot(title="Meal kits", pages=[
        Page(id="p1", position=0, kind="question", text=raw, intro_text=intro,
             questions=[captured_question()] if questions is None else questions)
    ])).total_seconds


def test_full_raw_capture_and_structured_only_have_identical_reading_cost():
    q = captured_question()
    raw = "\n".join([q.text, q.help_text, *[o.label for o in q.options]])
    assert timed_page(raw) == timed_page()


def test_exact_dedup_preserves_unique_concept_stimulus():
    prose = "A family meal kit with smoky chicken and freshly made salsa."
    q = captured_question()
    raw = "\n".join([prose, q.text, q.help_text, *[o.label for o in q.options]])
    expected = timed_page() + len(prose.split()) * TimingConstants().seconds_per_word
    assert timed_page(raw) == pytest.approx(round(expected, 1))


def test_exact_dedup_tolerates_capture_whitespace_but_not_semantic_paraphrases():
    q = captured_question()
    assert timed_page("How often\n do you buy\tmeal kits?") == timed_page()
    paraphrase = "How frequently do you purchase meal kits?"
    expected = timed_page() + len(paraphrase.split()) * TimingConstants().seconds_per_word
    assert timed_page(paraphrase) == pytest.approx(round(expected, 1))


def test_short_labels_do_not_remove_substrings_from_stimulus():
    q = Question(id="q", text="Choose a meal", kind="single_choice",
                 options=[Option(id="a", label="No")])
    prose = "Noodles make a quick meal. Nobody needs extra equipment."
    assert timed_page(prose, questions=[q]) == pytest.approx(
        round(timed_page(questions=[q]) + len(prose.split()) * 0.3, 1))


def test_repeated_question_on_different_pages_counts_on_each_page():
    q = captured_question()
    raw = "\n".join([q.text, q.help_text, *[o.label for o in q.options]])
    snapshot = SurveySnapshot(title="Meal kits", pages=[
        Page(id=f"p{i}", position=i, kind="question", text=raw, questions=[q]) for i in range(2)
    ])
    assert estimate(snapshot).total_seconds == pytest.approx(2 * timed_page())


def test_option_word_inside_unique_stimulus_is_not_erased():
    prose = "Never heat this meal in its plastic tray."
    assert timed_page(prose) == pytest.approx(round(timed_page() + len(prose.split()) * 0.3, 1))


def test_extra_exact_occurrence_is_not_globally_erased():
    q = captured_question()
    expected = timed_page() + len(q.text.split()) * 0.3
    assert timed_page(q.text + "\n" + q.text) == pytest.approx(round(expected, 1))


def test_intro_copied_into_raw_capture_is_read_only_once():
    assert timed_page(WELCOME, intro=WELCOME, questions=[]) == timed_page(intro=WELCOME, questions=[])


@pytest.mark.parametrize("text", [WELCOME, WELCOME.replace("we'd", "we’d").replace("We're", "We’re"),
    "Today we're exploring quesadilla meal kits. We'd like your feedback.",
])
def test_purpose_and_input_invitation_at_opening_is_a_welcome(text):
    opening = page(0, kind="info", text=text)
    snapshot = survey(opening, page(1, question()))
    assert snapshot.page_role(opening) == "intro"
    assert not structure.no_intro(context(snapshot)).findings
    assert opening.kind == "info"


@pytest.mark.parametrize("text", [
    "We're cooking up some new meal ideas.",
    "We'd love your input!",  # no grounded topic
    "Loading... " + WELCOME,
    "Welcome! Loading the survey.",
    "Please read each question and select one answer.",
    "We'd love your input! Please click Next to continue.",
])
def test_non_welcomes_remain_info(text):
    opening = page(0, kind="info", text=text)
    assert survey(opening, page(1, question())).page_role(opening) == "info"


def test_middle_concept_and_answerable_opening_are_not_inferred_as_welcome():
    middle = page(1, kind="info", text=WELCOME)
    opening = page(0, question(), kind="info", text=WELCOME)
    snapshot = survey(opening, middle, page(2, question("q2")))
    assert snapshot.page_role(opening) == "info"
    assert snapshot.page_role(middle) == "info"


def test_missing_welcome_has_scoped_draft_without_unverified_promises():
    snapshot = survey(page(0, question()))
    snapshot.title = "Quesadilla meal kits"
    f = structure.no_intro(context(snapshot)).findings[0]
    assert f.suggested_text
    assert "Quesadilla meal kits" in f.suggested_text
    assert "input" in f.suggested_text.lower()
    assert not any(term in f.suggested_text.lower() for term in ("minute", "reward", "points", "[", "]"))
    assert "verify" in f.explanation.lower()


def test_missing_welcome_does_not_expose_unknown_title_as_placeholder():
    snapshot = survey(page(0, question()))
    snapshot.title = "Untitled survey"
    f = structure.no_intro(context(snapshot)).findings[0]
    assert f.suggested_text and "Untitled" not in f.suggested_text
    assert "[" not in f.suggested_text


def test_length_advice_explains_estimate_and_configured_guideline():
    ctx = context(survey(page(0, question())))
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"total_seconds": 474}))
    f = structure.length_fits_type(ctx).findings[0]
    copy = " ".join((f.headline, f.evidence, f.explanation, f.member_impact)).lower()
    for phrase in ("estimated member completion", "configured", "survey-type guideline", "uncalibrated",
                   "timed pilot", "not crawl", "load time"):
        assert phrase in copy
    assert "goodwill" not in copy and "costs completions" not in copy


@pytest.mark.parametrize("intro_text", ["Welcome!", "Welcome! This takes 1 minute."])
def test_uncalibrated_time_advice_never_drafts_a_member_time_promise(intro_text):
    opening = page(0, kind="intro", intro_text=intro_text)
    ctx = context(survey(opening, page(1, question())))
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"total_seconds": 600}))
    f = structure.time_and_reward(ctx).findings[0]
    assert f.suggested_text is None
    assert "timed" in f.explanation.lower()
    assert "it takes about" not in f.headline.lower()


def test_calibrated_verified_time_advice_retains_time_rewrite():
    ctx = context(survey(page(0, kind="intro", intro_text="Welcome!"), page(1, question())))
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"calibrated": True}))
    assert structure.time_and_reward(ctx).findings[0].suggested_text


def test_uncertain_route_still_suppresses_length_advice_and_time_blocker():
    ctx = context(survey(page(0, question(conditional=True))))
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"total_seconds": 1200}))
    assert not structure.length_fits_type(ctx).findings
    assert not structure.broken_time_promise(ctx).assessed
