"""Reading-level cards keep what the question measures (brief 6.1, Q1 and Q9 rows).

A rewrite may only change wording. The measured behavior, timeframe, category terms, examples and
qualifiers must survive, checked deterministically, with negative controls so the check can fail.
"""
import pytest
from builders import context, intro, one_question_survey, page, question, survey, thank_you

from surveycoach.checks import content
from surveycoach.checks.reading import hard_terms, lost_terms, reading_steps, simpler_question
from surveycoach.recommendations import banned_words

Q1 = ("How often do you purchase ready-to-heat or ready-to-cook meal solutions, such as prepared meals "
      "or meal kits, to enjoy at home?")
Q1_FIXED = ("How often do you buy ready-to-heat or ready-to-cook meals, like prepared meals or meal kits, "
            "to enjoy at home?")
# The rewrite the review called wrong: examples became the whole category and "enjoy" became "heat or cook".
Q1_OLD_REWRITE = "How often do you buy prepared meals or meal kits to heat or cook at home?"
HARD = ("To what extent do you consider that organizational responsibilities substantially influence your "
        "overall satisfaction with the comprehensive assortment of contemporary refrigerated alternatives?")


def test_q1_rewrite_keeps_the_verb_the_category_and_the_examples():
    assert simpler_question(Q1) == Q1_FIXED


@pytest.mark.parametrize("term", ["ready-to-heat", "ready-to-cook", "prepared meals", "meal kits", "at home",
                                  "enjoy", "how often"])
def test_the_rewrite_retains_each_key_term(term):
    assert term in simpler_question(Q1).lower()


def test_such_as_examples_stay_examples_not_the_whole_category():
    out = simpler_question(Q1)
    assert "ready-to-heat or ready-to-cook meals," in out      # the category is still named
    assert ", like prepared meals or meal kits," in out        # and the examples are still examples
    assert "heat or cook at home" not in out


def test_lost_terms_is_empty_for_the_fixed_rewrite():
    assert lost_terms(Q1, Q1_FIXED) == []


def test_negative_control_the_old_rewrite_loses_the_verb_the_category_and_the_qualifier():
    lost = lost_terms(Q1, Q1_OLD_REWRITE)
    assert {"enjoy", "ready-to-heat", "ready-to-cook"} <= set(lost)


def test_negative_control_dropping_a_timeframe_or_a_qualifier_is_caught():
    assert "30" in lost_terms("How often did you buy meals in the past 30 days?", "How often did you buy meals?")
    assert "organic" in lost_terms("Do you buy organic meals?", "Do you buy meals?")


def test_a_pattern_that_would_drop_a_key_term_is_never_offered(monkeypatch):
    from surveycoach.checks import reading
    monkeypatch.setattr(reading, "MEAL_EXAMPLES", reading.re.compile(
        r"ready-to-heat or ready-to-cook meal solutions, such as (?P<examples>prepared meals or meal kits), to enjoy at home",
        reading.re.I))
    monkeypatch.setattr(reading, "_MEAL_REPLACEMENT", r"\g<examples> to heat or cook at home")
    assert reading.simpler_question(Q1) is None


def test_unknown_categories_and_quotes_still_decline():
    assert simpler_question("How often do you purchase ready-to-eat snacks, such as chips or nuts, to enjoy at home?") \
        == "How often do you buy ready-to-eat snacks, such as chips or nuts, to enjoy at home?"
    assert simpler_question('Do you like the phrase "meal solutions"?') is None


# --- hard words, when no safe rewrite exists -----------------------------------------------------

def test_hard_terms_are_found_by_syllables_in_reading_order_at_most_four():
    terms = [word for word, _ in hard_terms(HARD)]
    assert terms == ["organizational", "responsibilities", "contemporary", "refrigerated"]


def test_a_vetted_synonym_is_offered_only_when_the_small_map_has_it():
    terms = dict(hard_terms("Where do you purchase organizational supplies, approximately weekly?"))
    assert terms["purchase"] == "buy" and terms["approximately"] == "about"
    assert terms["organizational"] is None


def test_wordy_phrases_come_first_with_their_plain_form():
    terms = hard_terms("In order to help us, what do you buy prior to a trip?")
    assert terms[0] == ("in order to", "to") and ("prior to", "before") in terms


def test_plain_text_has_no_hard_terms():
    assert hard_terms("How often do you shop for food at home?") == []


def test_steps_name_the_words_and_keep_the_meaning_and_hold_no_grade_numbers():
    steps = reading_steps(HARD)
    assert 1 <= len(steps) <= 3 and all(len(s.split()) <= 30 for s in steps)
    assert '"responsibilities"' in steps[0] and '"contemporary"' in steps[0]
    assert "grade" not in " ".join(steps).lower()
    assert banned_words(" ".join(steps)) == []
    assert "same" in " ".join(steps)   # topic, time frame and answers stay


def test_steps_with_nothing_to_name_still_give_an_action():
    steps = reading_steps("How often do you shop for food at home?")
    assert len(steps) == 2 and "Cut" in steps[0]


# --- the card itself -----------------------------------------------------------------------------

def card(text):
    snapshot = survey(intro(), page(1, question("q1", text, "text_short", options=())), thank_you())
    findings = content.plain_words(context(snapshot)).findings
    return findings[0]


def test_q1_card_is_a_paste_with_member_language_and_no_grade_in_the_card():
    f = card(Q1)
    assert f.action_kind == "paste" and f.suggested_text == Q1_FIXED
    assert f.headline == "Members may struggle to read this question"
    assert f.member_impact == "Long, technical wording slows people down and blurs answers."
    assert "grade" in f.explanation.lower()          # the number lives in details
    assert "grade" not in (f.headline + f.member_impact).lower()


def test_the_highlight_is_the_word_as_written_in_the_question():
    f = card("Organizational responsibilities substantially influence overall satisfaction with the comprehensive "
             "assortment of contemporary refrigerated alternatives, to what extent do you consider that?")
    assert f.highlight == "Organizational" and f.highlight in f.current_text


def test_q9_card_without_a_safe_rewrite_names_hard_words_in_steps():
    f = card(HARD)
    assert f.action_kind == "steps" and not f.suggested_text
    assert '"responsibilities"' in f.steps[0]
    assert f.highlight == "organizational"
    assert "grade" in f.explanation.lower()
    assert "grade" not in " ".join(f.steps).lower()
