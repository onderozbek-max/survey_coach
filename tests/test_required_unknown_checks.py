"""D8 follow-up: unknown requiredness (`Question.required is None`) is neither optional nor required.

8.6 may pass only for a verified-optional open-text question; 2.4 may only count verified-required ones.
When the unknown questions could change the verdict, the check says "unassessed" and explains why.
"""
import pytest
from builders import context, intro, one_question_survey, page, question, survey, thank_you

from surveycoach.checks import structure
from surveycoach.quality import build_quality
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.labels import screen_labels
from surveycoach.signals import build_overview

OPEN = dict(kind="text_long", options=())


def run(fn, snapshot):
    return fn(context(snapshot))


def comment(qid="last", required=None):
    return question(qid, "Anything else you'd like the product team to know?", required=required, **OPEN)


def ending(*closing):
    return survey(intro(), page(1, question()), page(2, *closing), thank_you())


# --- 8.6 ---------------------------------------------------------------------------------------
def test_8_6_unknown_requiredness_is_unassessed_not_a_pass_or_a_fail():
    result = run(structure.room_to_speak, ending(comment(required=None)))
    assert result.assessed is False and result.fraction is None and result.findings == []
    assert "required" in result.note.lower() and "unknown" in result.note.lower()


def test_8_6_verified_optional_still_passes():
    result = run(structure.room_to_speak, ending(comment(required=False)))
    assert (result.assessed, result.fraction, result.findings, result.note) == (True, 1.0, [], None)


def test_8_6_verified_required_still_fails_with_the_make_it_optional_fix():
    result = run(structure.room_to_speak, ending(comment(required=True)))
    assert result.assessed is True and result.fraction == 0.0
    assert [f.headline for f in result.findings] == ["Make the final comment optional"]


def test_8_6_a_verified_optional_comment_wins_over_an_unknown_one():
    result = run(structure.room_to_speak, ending(comment("a", required=None), comment("b", required=False)))
    assert result.assessed is True and result.fraction == 1.0


def test_8_6_required_plus_unknown_is_unassessed_because_the_unknown_one_may_be_optional():
    result = run(structure.room_to_speak, ending(comment("a", required=True), comment("b", required=None)))
    assert result.assessed is False and result.fraction is None and result.findings == []


def test_8_6_no_open_text_at_all_is_still_a_missing_comment_box_regardless_of_requiredness():
    result = run(structure.room_to_speak, one_question_survey(question(required=None)))
    assert result.assessed is True and result.fraction == 0.0
    assert result.findings[0].headline == "No optional comment box near the end"


def test_8_6_unknown_requiredness_never_becomes_a_strength_or_quality_credit():
    snapshot = ending(comment(required=None))
    review = run_review(snapshot)
    raw = review.model_dump()
    raw["findings"] = [dict(f.model_dump(), fingerprint=f.fingerprint) for f in review.findings]
    title = next(c.title for c in load_rubric().criteria if c.id == "8.6")
    assert review.results["8.6"].assessed is False
    assert title in review.unchecked
    assert title not in review.scorecard.strengths
    assert title not in build_overview(snapshot, raw, {}, screen_labels(snapshot), {}, load_rubric())["strengths"]
    quality = build_quality(raw, load_rubric())
    d8 = next(d for d in quality["dimensions"] if d["id"] == "D8")
    assert d8["unchecked_points"] >= 1 and quality["provisional"] is True


def test_8_6_a_verified_optional_comment_is_a_strength_so_the_control_is_meaningful():
    review = run_review(ending(comment(required=False)))
    assert review.results["8.6"].assessed is True and review.results["8.6"].fraction == 1.0
    assert "8.6" not in [c.id for c in load_rubric().criteria if c.title in review.unchecked]


# --- 2.4 ---------------------------------------------------------------------------------------
def typing(required_flags):
    pages = [intro()] + [page(i + 1, question(f"q{i}", "Tell us more", required=flag, **OPEN))
                         for i, flag in enumerate(required_flags)] + [thank_you()]
    return survey(*pages)


@pytest.mark.parametrize("flags,fraction", [
    ([True, True], 1.0), ([True] * 3, 0.5), ([True] * 4, 0.0), ([False] * 6, 1.0),
    ([True] * 4 + [None] * 2, 0.0),           # unknown cannot lower an already-lowest verdict
    ([True, True, False, False], 1.0),        # verified optional is not counted
])
def test_2_4_counts_only_verified_required_when_the_verdict_is_settled(flags, fraction):
    result = run(structure.typing_load, typing(flags))
    assert result.assessed is True and result.fraction == fraction and result.note is None


@pytest.mark.parametrize("flags", [[None] * 5, [True] * 3 + [None] * 3, [True, True, None], [None] * 3])
def test_2_4_unknown_requiredness_that_could_change_the_verdict_is_unassessed(flags):
    result = run(structure.typing_load, typing(flags))
    assert result.assessed is False and result.fraction is None
    assert "unknown" in result.note.lower()


def test_2_4_unknown_questions_are_never_named_in_a_make_it_optional_finding():
    result = run(structure.typing_load, typing([True, True, True, None, None]))
    assert [f.question_id for f in result.findings] == ["q2"]   # only the verified required 3rd one


def test_2_4_unknown_open_text_alone_is_not_a_pass_that_becomes_a_strength():
    review = run_review(typing([None] * 5))
    title = next(c.title for c in load_rubric().criteria if c.id == "2.4")
    assert review.results["2.4"].assessed is False
    assert title in review.unchecked and title not in review.scorecard.strengths


# --- the note itself -----------------------------------------------------------------------------
def test_a_result_without_a_note_keeps_its_old_saved_shape_and_a_note_round_trips():
    from surveycoach.findings import CheckResult
    plain, noted = CheckResult(criterion_id="x"), CheckResult(criterion_id="x", assessed=False, note="why")
    assert "note" not in plain.model_dump() and '"note"' not in plain.model_dump_json()
    assert CheckResult.model_validate_json(noted.model_dump_json()).note == "why"
    assert CheckResult.model_validate(plain.model_dump()).note is None


def test_an_ai_merge_keeps_the_note_only_while_the_check_is_still_unassessed():
    from surveycoach.findings import CheckResult
    from surveycoach.review import _with_ai
    mine = CheckResult(criterion_id="8.6", assessed=False, note="unknown required status")
    still_unknown = _with_ai({"8.6": mine}, {"8.6": CheckResult(criterion_id="8.6", assessed=False, fraction=None)})
    assert still_unknown["8.6"].note == "unknown required status"
    # the unassessed result is replaced only when the AI actually judged it
    judged = _with_ai({"8.6": mine}, {"8.6": CheckResult(criterion_id="8.6", fraction=1.0)})
    assert judged["8.6"].assessed is True and judged["8.6"].note is None
