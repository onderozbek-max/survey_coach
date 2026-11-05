"""Audit 16, 17, 18: canonical screen-out copy, honest B3 timing, and N/A for absent categories.

Cross-consumer invariants: raw points, normalized quality, coverage and strengths must agree
about which criteria had something to judge.
"""
from dataclasses import replace

import pytest
from builders import context, intro, one_question_survey, page, question, survey, thank_you

from surveycoach.checks import answers, content, phone, structure
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.signals import build_overview
from surveycoach.labels import screen_labels
from surveycoach.quality import build_quality
from surveycoach.snapshot import Question, SurveySnapshot

ABSENT_WHEN_TEXT_ONLY = [("3.3", content.clear_instructions), ("4.2", answers.no_overlap),
                         ("4.4", answers.honest_scales), ("6.2", phone.tappable_answers),
                         ("6.3", phone.small_grids)]
ABSENT_STRENGTHS = {"Answer choices don't overlap", "Short, tappable answers"}


def run(fn, snapshot):
    return fn(context(snapshot))


def text_only():
    return one_question_survey(question(text="Tell us more.", kind="text_short", options=()))


# --- Audit 16: B3 thank-you uses canonical page copy -------------------------------------------
def screen_out(**fields):
    return survey(intro(), page(1, question()), page(2, kind="screen_out", **fields), thank_you())


def info(text):
    return Question(id="info", kind="info", text=text)


@pytest.mark.parametrize("fields", [
    dict(text="This survey is not a match.", intro_text="Thanks for your time!"),
    dict(text="This survey is not a match. Thanks for your time!"),
    dict(intro_text="Thanks for your time!"),
])
def test_b3_finds_thank_you_in_any_screen_copy_field(fields):
    assert run(structure.late_screen_out, screen_out(**fields)).findings == []


def test_b3_finds_thank_you_in_an_info_question():
    snapshot = screen_out(text="This survey is not a match.")
    snapshot.pages[2].questions = [info("Thanks for your time!")]
    assert run(structure.late_screen_out, snapshot).findings == []


def test_b3_split_and_flattened_copy_agree():
    split = screen_out(text="This survey is not a match.", intro_text="Thanks for your time!")
    flat = screen_out(text=SurveySnapshot.page_copy(split.pages[2]))
    assert run(structure.late_screen_out, split).findings == run(structure.late_screen_out, flat).findings


def test_b3_genuinely_missing_thank_you_is_still_must_fix_and_targets_the_element():
    snapshot = screen_out(text="This survey is not a match.", intro_text="Not eligible.")
    findings = run(structure.late_screen_out, snapshot).findings
    assert [f.headline for f in findings] == ["Screen-out page has no thank-you"]
    assert findings[0].severity == "must_fix" and findings[0].page_id == "p2"
    assert findings[0].current_text == "This survey is not a match."


# --- Audit 17: B3 timing is only assessed with calibrated, certain effort -----------------------
def late_survey(screen_text):
    pages = [intro()] + [page(i + 1, question(f"q{i}", "Tell us", "text_long", options=())) for i in range(8)]
    return survey(*pages, page(9, kind="screen_out", text=screen_text), thank_you())


def with_timing(snapshot, **timing):
    ctx = context(snapshot)
    return replace(ctx, timing=ctx.timing.model_copy(update=timing))


def test_b3_uncalibrated_late_screen_out_is_not_assessed():
    result = structure.late_screen_out(with_timing(late_survey("Thanks for your time!")))
    assert result.assessed is False and result.findings == []


def test_b3_path_uncertain_late_screen_out_is_not_assessed():
    result = structure.late_screen_out(with_timing(late_survey("Thanks for your time!"), calibrated=True, path_uncertain=True))
    assert result.assessed is False


def test_b3_calibrated_certain_route_is_assessed_and_clean_when_early_enough():
    result = structure.late_screen_out(with_timing(survey(intro(), page(1, question()), page(2, kind="screen_out", text="Thanks!"), thank_you()),
                                                   calibrated=True, path_uncertain=False))
    assert result.assessed and result.findings == []


def test_b3_unverified_timing_still_reports_independent_thank_you_finding():
    result = structure.late_screen_out(with_timing(late_survey("Sorry, you do not qualify.")))
    assert result.assessed is False
    assert [f.headline for f in result.findings] == ["Screen-out page has no thank-you"]


def test_b3_first_page_screen_out_needs_no_timing_calibration():
    snapshot = survey(page(0, kind="screen_out", text="Thanks for your time!"))
    assert run(structure.late_screen_out, snapshot).assessed is True


def test_b3_uncalibrated_late_screen_out_stays_pending_through_the_review():
    review = run_review(late_survey("Thanks for your time!"))
    assert not review.results["B3"].assessed
    assert "B3" in review.scorecard.pending_blockers
    assert review.scorecard.readiness != "ready"


def test_b3_without_any_screen_out_keeps_the_existing_clear():
    assert run(structure.late_screen_out, one_question_survey(question())).assessed is True


# --- Audit 18: absent categories are explicit N/A, never earned credit --------------------------
@pytest.mark.parametrize("criterion,fn", ABSENT_WHEN_TEXT_ONLY)
def test_absent_category_is_explicit_not_applicable(criterion, fn):
    result = run(fn, text_only())
    assert (result.applies, result.assessed, result.fraction) == (False, True, None)


@pytest.mark.parametrize("criterion,fn", [("6.1", phone.fits_one_screen), ("6.4", phone.thumb_friendly),
                                          ("3.2", content.plain_words)])
def test_per_question_checks_are_na_when_there_are_no_questions(criterion, fn):
    empty = survey(intro(), thank_you())
    result = run(fn, empty)
    assert (result.applies, result.assessed, result.fraction) == (False, True, None)


def test_6_5_is_na_for_a_survey_without_pages_or_questions():
    result = run(phone.stays_put, SurveySnapshot(title="Empty", pages=[]))
    assert result.applies is False


def test_present_category_without_problems_still_earns_full_credit():
    q = question(kind="multi_choice", text="Which flavors? Select all that apply.")
    assert run(content.clear_instructions, one_question_survey(q)).fraction == 1.0
    assert run(phone.tappable_answers, one_question_survey(q)).fraction == 1.0
    assert run(answers.no_overlap, one_question_survey(q)).fraction == 1.0


def test_choice_questions_with_unreadable_options_are_unknown_not_na():
    q = Question(id="q", text="Pick one", kind="single_choice", options=[])
    for fn in (phone.tappable_answers, answers.no_overlap):
        result = run(fn, one_question_survey(q))
        assert (result.assessed, result.fraction) == (False, None)


def test_rating_without_captured_scale_is_unknown_not_na():
    q = Question(id="q", text="Rate it", kind="rating")
    for fn in (phone.small_grids, answers.honest_scales):
        assert run(fn, one_question_survey(q)).assessed is False


def raw_review(snapshot):
    review = run_review(snapshot)
    raw = review.model_dump()
    raw["findings"] = [dict(f.model_dump(), fingerprint=f.fingerprint) for f in review.findings]
    return review, raw


def test_text_only_survey_earns_no_points_for_absent_categories():
    review, _ = raw_review(text_only())
    rubric = load_rubric()
    absent_points = sum(c.points for c in rubric.criteria if c.id in {cid for cid, _ in ABSENT_WHEN_TEXT_ONLY})
    assert absent_points == 10
    assert review.scorecard.not_applicable_points >= absent_points
    for cid, _ in ABSENT_WHEN_TEXT_ONLY:
        assert review.results[cid].applies is False


def test_cross_consumer_invariants_for_absent_categories():
    snapshot = text_only()
    review, raw = raw_review(snapshot)
    rubric = load_rubric()
    absent = {cid for cid, _ in ABSENT_WHEN_TEXT_ONLY}
    # raw points: nothing earned from absent criteria and they are not "unchecked" either
    absent_titles = {c.title for c in rubric.criteria if c.id in absent}
    assert not absent_titles & set(review.scorecard.strengths)
    # normalized quality excludes them from earned, assessed and applicable points alike
    quality = build_quality(raw, rubric)
    everything_assessed = sum(c.points for c in rubric.criteria if c.active and c.id not in absent
                              and review.results.get(c.id) and review.results[c.id].assessed
                              and review.results[c.id].applies and review.results[c.id].fraction is not None)
    assert quality["assessed_points"] == everything_assessed
    not_applicable = {c.id for c in rubric.criteria if c.active and review.results.get(c.id)
                      and review.results[c.id].assessed and not review.results[c.id].applies}
    assert absent <= not_applicable
    assert quality["applicable_points"] == sum(c.points for c in rubric.criteria
                                               if c.active and c.id not in not_applicable)
    assert review.scorecard.not_applicable_points == sum(c.points for c in rubric.criteria if c.id in not_applicable)
    # strengths in both projections never come from absent categories
    overview = build_overview(snapshot, raw, {}, screen_labels(snapshot), {}, rubric)
    assert not ABSENT_STRENGTHS & set(overview["strengths"])


def test_absent_categories_do_not_dilute_real_phone_issues():
    q = question(text="Click to explain.", kind="text_short", options=(), fits_one_screen=False)
    snapshot = survey(intro(), page(1, q, links_out=["https://example.invalid/"]), thank_you())
    _, raw = raw_review(snapshot)
    d6 = next(d for d in build_quality(raw, load_rubric())["dimensions"] if d["id"] == "D6")
    assert d6["score"] < 30   # audit: was 45.45 with absent 6.2/6.3 earning credit; 14.29 once N/A

