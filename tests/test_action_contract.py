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


# --- Card body budget and the tight member impact (workstream 1C) ----------------------------------

LONG_IMPACT = ("Members who disliked the fit must translate their experience into a degree of love, "
               "which can push feedback toward positive answers.")
NO_COMMA_IMPACT = ("Members who bought a different pack, received the product without buying it or cannot "
                   "remember must choose an inaccurate purchase to continue.")


def test_visible_body_is_impact_plus_the_one_action_and_never_the_paste_text():
    from surveycoach.recommendations import MAX_BODY_WORDS, visible_body_words
    assert MAX_BODY_WORDS == 45
    steps = with_action(raw(member_impact="Four word impact here.", explanation="Do one thing now."))
    assert visible_body_words(steps) == 4 + 4
    paste = with_action(raw(member_impact="Four word impact here.", suggested_text="word " * 60))
    assert visible_body_words(paste) == 4
    check = with_action(raw(member_impact="Four word impact here.", action_kind="you_check",
                            you_check="Does it show on your phone?"))
    assert visible_body_words(check) == 4 + 6


def test_a_card_body_over_45_words_is_a_contract_problem():
    explicit = raw(action_kind="steps", steps=["word " * 25, "word " * 5], member_impact="word " * 19)
    assert "body_long" in validate_finding(explicit)


def test_a_long_ai_impact_is_cut_at_a_clause_and_the_full_text_moves_to_details():
    out = with_action(raw(member_impact=LONG_IMPACT, explanation="Ask how satisfied members are."))
    assert out["member_impact"] == ("Members who disliked the fit must translate their experience "
                                    "into a degree of love.")
    assert out["member_impact_full"] == LONG_IMPACT
    assert validate_finding(out) == []


def test_an_impact_with_no_safe_cut_falls_back_to_one_plain_line_for_the_criterion():
    out = with_action(raw(criterion_id="B2", member_impact=NO_COMMA_IMPACT))
    assert len(out["member_impact"].split()) <= 20
    assert out["member_impact_full"] == NO_COMMA_IMPACT
    assert banned_words(out["member_impact"]) == []
    assert with_action(out) == out          # projection stays idempotent


def test_short_impact_is_left_alone_and_gets_no_details_copy():
    out = with_action(raw(member_impact="Members may stall here."))
    assert out["member_impact"] == "Members may stall here." and "member_impact_full" not in out


def test_the_fallback_step_fits_the_card_budget_and_the_rest_stays_in_details():
    explanation = ("Replace the placeholder labels with real statements about the product. "
                   "Each row should say one specific thing members can judge from their own use. "
                   "The intended statements were not supplied, so no complete rewrite is offered here. "
                   "Keep the grid and the agreement scale as they are.")
    out = with_action(raw(explanation=explanation, member_impact="Members cannot judge a placeholder row."))
    assert out["steps"] == ["Replace the placeholder labels with real statements about the product. "
                            "Each row should say one specific thing members can judge from their own use."]
    assert out["explanation"] == explanation          # nothing is lost from the details
    assert validate_finding(out) == []


def test_one_overlong_fallback_sentence_is_cut_at_a_clause_not_mid_word():
    sentence = ("Rewrite the question so it asks about the experience members actually had with the product, "
                "without assuming they enjoyed it or that they remember every detail of using it at home.")
    out = with_action(raw(explanation=sentence))
    assert out["steps"] == ["Rewrite the question so it asks about the experience members actually had with the product."]
    assert len(out["steps"][0].split()) <= 30


def test_the_guard_keeps_the_new_image_card_but_still_rewrites_a_legacy_saved_one():
    from surveycoach.recommendations import guard_recommendation
    legacy = raw(criterion_id="7.2", source="auto", headline="Check wide image on mobile: potential layout risk",
                 member_impact="Old long copy.")
    assert guard_recommendation(legacy)["headline"] == "Check image on mobile: potential layout risk"
    current = dict(legacy, headline="Check this wide image on a phone", action_kind="you_check",
                   you_check="Open this screen on your phone: is the whole image easy to see?",
                   member_impact="A picture that looks fine on a desktop can be cropped or tiny on a phone.")
    assert guard_recommendation(current) == current
