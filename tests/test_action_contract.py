"""Brief 6.3: one action kind per finding, validated once, legacy findings still load."""
import pytest

from surveycoach.findings import Finding
from surveycoach.recommendations import (BANNED_WORDS, action_kind_of, banned_words,
                                         validate_finding, with_action)


def raw(**extra):
    base = dict(criterion_id="3.2", severity="worth_improving", headline="Hard words in Q1",
                evidence="utilize", explanation="Swap the long word for a short one.",
                member_impact="Members may stall here.")
    return base | extra


def test_new_fields_are_optional_and_absent_from_legacy_dumps():
    finding = Finding(**raw())
    assert finding.action_kind is None and finding.steps == []
    assert finding.you_check is None and finding.field_location is None
    dumped = finding.model_dump(mode="json")
    for key in ("action_kind", "steps", "you_check", "field_location"):
        assert key not in dumped


def test_new_fields_round_trip_when_set():
    finding = Finding(**raw(action_kind="steps", steps=["Open Q1.", "Shorten it."],
                            field_location="RedJade > Q1 > Question text"))
    again = Finding.model_validate(finding.model_dump(mode="json"))
    assert again.action_kind == "steps" and again.steps == ["Open Q1.", "Shorten it."]
    assert again.field_location == "RedJade > Q1 > Question text"


def test_unknown_action_kind_is_rejected():
    with pytest.raises(ValueError):
        Finding(**raw(action_kind="telepathy"))


def test_legacy_suggested_text_becomes_paste():
    out = with_action(raw(suggested_text="Use this."))
    assert out["action_kind"] == "paste" and not out.get("steps") and out["action_fallback"] is True


def test_legacy_options_alone_become_paste():
    out = with_action(raw(options=[{"label": "Short", "text": "Use this."}]))
    assert out["action_kind"] == "paste"


def test_legacy_explanation_becomes_one_step():
    out = with_action(raw())
    assert out["action_kind"] == "steps"
    assert out["steps"] == ["Swap the long word for a short one."]
    assert out["action_fallback"] is True


@pytest.mark.parametrize("finding", [
    raw(criterion_id="B7", severity="worth_improving",
        headline="Reader could not verify image loading: Hero"),
    raw(criterion_id="6.2", headline="10 answer choices; review the phone layout"),
    raw(criterion_id="7.2", headline="Check image on mobile: potential layout risk", source="auto"),
])
def test_human_judgement_findings_become_you_check(finding):
    out = with_action(finding)
    assert out["action_kind"] == "you_check"
    assert out["you_check"].strip() and not out.get("steps")


def test_a_confirmed_image_problem_is_not_a_you_check():
    out = with_action(raw(criterion_id="B7", severity="must_fix",
                          headline="Image options are too small to judge (80 px)"))
    assert out["action_kind"] == "steps"


def test_explicit_action_is_never_overwritten_and_projection_is_idempotent():
    explicit = raw(action_kind="you_check", you_check="Does the logo show on your phone?")
    out = with_action(explicit)
    assert out["you_check"] == "Does the logo show on your phone?"
    assert "action_fallback" not in out
    once = with_action(raw())
    assert with_action(once) == once


def test_with_action_does_not_mutate_its_input():
    legacy = raw()
    before = dict(legacy)
    with_action(legacy)
    assert legacy == before


def test_action_kind_of_reads_explicit_before_inferring():
    assert action_kind_of(raw(action_kind="paste", suggested_text="x")) == "paste"
    assert action_kind_of(raw()) == "steps"


def test_valid_findings_have_no_problems():
    assert validate_finding(with_action(raw())) == []
    paste = with_action(raw(suggested_text="Use this."))
    assert validate_finding(paste) == []


@pytest.mark.parametrize("update,code", [
    (dict(action_kind=None), "no_action"),
    (dict(action_kind="steps", steps=[]), "steps_count"),
    (dict(action_kind="steps", steps=["a", "b", "c", "d"]), "steps_count"),
    (dict(action_kind="steps", steps=["word " * 40]), "step_long"),
    (dict(action_kind="you_check", you_check="  "), "empty_you_check"),
    (dict(action_kind="paste", suggested_text=None, options=[]), "empty_paste"),
    (dict(action_kind="steps", steps=["Do it."], you_check="Is it ok?"), "multiple_actions"),
    (dict(action_kind="steps", steps=["Do it."], suggested_text="Paste me"), "multiple_actions"),
    (dict(action_kind="steps", steps=["Do it."], member_impact="word " * 21), "member_impact_long"),
])
def test_validation_codes(update, code):
    explicit = {k: v for k, v in raw().items()} | update
    explicit.pop("action_fallback", None)
    assert code in validate_finding(explicit)


def test_banned_words_are_whole_word_and_case_insensitive():
    assert banned_words("The Reader took a snapshot.") == ["reader", "snapshot"]
    assert banned_words("Threshold and coverage") == ["coverage", "threshold"]
    assert banned_words("Reader-friendly? no. Readers? no.") == ["reader"]
    assert banned_words("Open the survey on your phone.") == []
    assert banned_words("An unassessed check, assessed too") == ["assessed", "unassessed"]
    assert banned_words("See criterion B7 and the saved assessment") == ["criterion IDs", "saved assessment"]


def test_banned_list_matches_the_copy_system():
    for word in ("assessed", "unassessed", "heuristic", "configured", "threshold", "provisional",
                 "coverage", "saved assessment", "captured path", "reader", "snapshot", "calibrated",
                 "verified route", "partial test participant", "risk checks", "rubric"):
        assert word in BANNED_WORDS


def test_visible_text_is_scanned_but_survey_wording_is_not():
    finding = with_action(raw(suggested_text="The reader snapshot threshold."))
    assert validate_finding(finding) == []   # paste text is the survey's wording, not our copy
    finding = with_action(raw(headline="Reader problem"))
    assert "banned:reader" in validate_finding(finding)


def test_fallback_step_drops_bookkeeping_and_jargon_sentences_but_keeps_the_action():
    out = with_action(raw(explanation=(
        "Say how long it takes. This also covers criterion 5.1. "
        "A time rewrite is offered only for a calibrated, verified route. Add the reward too.")))
    assert out["steps"] == ["Say how long it takes. Add the reward too."]
    assert validate_finding(out) == []


def test_fallback_falls_back_to_the_headline_when_nothing_plain_is_left():
    out = with_action(raw(explanation="This also covers criterion 5.1.", headline="Add a time estimate"))
    assert out["steps"] == ["Add a time estimate"]


# --- where in RedJade ------------------------------------------------------------------------

def _located(**extra):
    from builders import intro, page, question, survey
    from surveycoach.server.present import present_findings
    snapshot = survey(intro("Welcome to our survey!"), page(1, question("q1", text="Which flavor?",
                      options=("Vanilla", "Mint"))), page(2)).model_dump(mode="json")
    return present_findings([raw(question_id=extra.pop("question_id", None), **extra)], {}, snapshot)[0]


def test_field_location_names_the_question_the_answer_and_the_welcome():
    assert _located(question_id="q1", current_text="Which flavor?")["field_location"] == "RedJade > Q1 > Question text"
    assert _located(question_id="q1", current_text="Mint")["field_location"] == "RedJade > Q1 > Answer 2"
    assert _located(page_id="p0")["field_location"] == "RedJade > Welcome > Welcome text"
    assert _located(page_id="p2")["field_location"] == "RedJade > Message > Screen text"


def test_field_location_is_left_out_when_it_cannot_be_pinned_down_and_explicit_ones_win():
    assert "field_location" not in _located()      # a whole-survey finding has no field
    assert _located(question_id="q1", field_location="RedJade > Somewhere")["field_location"] == "RedJade > Somewhere"
