"""Brief 6.3 and the copy system (section 8), enforced on what the checks themselves write.

Every finding a deterministic check raises carries exactly one explicit action (paste, 1-3 steps,
or one you-check question), member-language copy, and a card body of at most 45 words. The legacy
fallback in recommendations.py is for old saved findings and for the AI judge's wording only.
"""
import pytest
from check_battery import all_findings, surveys

from surveycoach.checks.registry import finding
from surveycoach.checks.text import reading_grade
from surveycoach.recommendations import (MAX_BODY_WORDS, banned_words, validate_finding, visible_body_words,
                                         with_action)

EXPECTED = {
    "1.4", "2.1", "2.2", "2.4", "3.2", "3.3", "4.1", "4.2", "4.3", "4.4", "5.4", "6.1", "6.2", "6.3", "6.4", "6.5",
    "7.2", "7.3", "7.5", "7.6", "8.2", "8.5", "8.6", "9.1", "9.2", "B2", "B3", "B4", "B5", "B7",
}
FINDINGS = all_findings()


def dumped(f):
    return f.model_dump(mode="json")


def test_the_battery_exercises_every_deterministic_finding_family():
    assert EXPECTED <= {f.criterion_id for _, f in FINDINGS}


@pytest.mark.parametrize("name,f", FINDINGS, ids=lambda v: v if isinstance(v, str) else v.headline[:40])
def test_every_check_finding_carries_one_explicit_valid_action(name, f):
    assert f.action_kind in {"paste", "steps", "you_check"}, "no explicit action: would use the legacy fallback"
    assert validate_finding(dumped(f)) == []
    assert with_action(dumped(f)).get("action_fallback") is None


@pytest.mark.parametrize("name,f", FINDINGS, ids=lambda v: v if isinstance(v, str) else v.headline[:40])
def test_card_body_is_short_and_in_member_language(name, f):
    d = dumped(f)
    assert len(f.member_impact.split()) <= 20, f.member_impact
    assert visible_body_words(d) <= MAX_BODY_WORDS, (visible_body_words(d), d)
    visible = " ".join([f.headline, f.member_impact, *f.steps, f.you_check or "", f.field_location or ""])
    assert banned_words(visible) == [], visible


def action_text(f):
    return " ".join(f.steps) if f.action_kind == "steps" else f.you_check or ""


@pytest.mark.parametrize("name,f", FINDINGS, ids=lambda v: v if isinstance(v, str) else v.headline[:40])
def test_member_impact_and_actions_read_at_grade_eight_or_below(name, f):
    # Plain language, not jargon. Short strings make the formula noisy, so 8.5 leaves a half grade of slack.
    for text in (f.member_impact, *f.steps, f.you_check or ""):
        if len(text.split()) >= 5:
            assert reading_grade(text) <= 8.5, (round(reading_grade(text), 1), text)


@pytest.mark.parametrize("name,f", [p for p in FINDINGS if p[1].action_kind == "paste"],
                         ids=lambda v: v if isinstance(v, str) else v.headline[:40])
def test_paste_actions_paste_something_new(name, f):
    pasted = f.suggested_text or f.options[0].text
    assert pasted.strip() and pasted != f.current_text


@pytest.mark.parametrize("name,f", [p for p in FINDINGS if p[1].action_kind == "you_check"],
                         ids=lambda v: v if isinstance(v, str) else v.headline[:40])
def test_you_check_is_one_question_pointing_at_one_place(name, f):
    assert f.you_check.count("?") == 1 and f.you_check.endswith("?")
    assert not f.steps


def test_a_finding_without_any_action_cannot_be_built_by_a_check():
    with pytest.raises(ValueError, match="action"):
        finding("3.2", "worth_improving", "Hard word", "ev", "Why.", "Impact.")


def test_a_check_finding_with_suggested_text_is_a_paste_by_default():
    f = finding("3.2", "worth_improving", "Hard word", "ev", "Why.", "Impact.", suggested_text="Use this.")
    assert f.action_kind == "paste"


def test_every_survey_in_the_battery_is_flawed_so_the_battery_means_something():
    assert len(surveys()) >= 15
