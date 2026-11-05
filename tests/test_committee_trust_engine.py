"""Offline regression contracts for the November committee trust fixes."""
import pytest

from builders import context, intro, page, question, scale, survey, thank_you
from surveycoach.checks import run_all
from surveycoach.checks.structure import fixed_intro
from surveycoach.findings import CheckResult, Finding
from surveycoach.judge.batches import WORDING, STORY
from surveycoach.judge.dedupe import dedupe
from surveycoach.judge.grounding import ground
from surveycoach.judge.prompts import survey_block, system_prompt
from surveycoach.judge.schemas import AiFinding, BatchOutput, Verdict
from surveycoach.review import _merge, _with_ai, run_review
from surveycoach.rubric import load_rubric
from surveycoach.scoring import score

RUBRIC = load_rubric()


def issue(cid="5.1", headline="Leading wording", **kw):
    return Finding(criterion_id=cid, severity="must_fix" if cid.startswith("B") else "worth_improving",
                   headline=headline, evidence="amazing", explanation="Use neutral wording.",
                   member_impact="May influence the answer.", question_id="q1", **kw)


def test_reader_info_welcome_and_ending_are_recognized_without_mutating_capture():
    opening = page(0, question("welcome", "Welcome! Thanks for helping us. This takes 5 minutes.",
                               kind="info", options=()), kind="info")
    closing = page(2, kind="info", text="Thank you for completing this survey!")
    snap = survey(opening, page(1, question()), closing)
    result = run_review(snap)
    assert not result.results["B4"].findings
    assert result.promised_minutes == 5
    assert "PAGE p0 (intro" in survey_block(snap)
    assert "PAGE p2 (thank_you" in survey_block(snap)
    assert snap.pages[0].kind == "info"


@pytest.mark.parametrize("text", [
    "The spookiest time of the year just happened [icon] Let us know how you celebrated! Next",
    "Tell us about your favorite holiday traditions.",
    "Tell us about Halloween.",
    "Share your experience with our new snacks.",
    "We'd love your thoughts on our coffee flavors.",
])
def test_first_question_free_info_invitation_is_an_intro(text):
    opening = page(0, kind="info", text=text)
    snap = survey(opening, page(1, question()))
    assert snap.page_role(opening) == "intro"
    assert snap.intro_text == text
    assert not run_review(snap).results["B4"].findings
    assert opening.kind == "info"


@pytest.mark.parametrize("text", [
    "Let us know", "Tell us", "Share", "Your thoughts", "Share this link. Next",
    "Tell us about. Next", "Your thoughts on Next",
    "Loading... Let us know about your holiday.",
    "Please sign in to share your thoughts on snacks.",
    "Authentication required. Tell us about your holiday.",
    "Validation error: let us know about your holiday.",
    "Please answer the required question. Tell us about your holiday.",
])
def test_incomplete_invitations_and_system_messages_are_not_intros(text):
    opening = page(0, kind="info", text=text)
    assert survey(opening, page(1, question())).page_role(opening) == "info"


def test_invitation_inference_is_limited_to_first_question_free_info_page():
    text = "Tell us about your holiday traditions."
    opening = page(0, question(text=text), kind="info", text=text)
    later = page(2, kind="info", text=text)
    snap = survey(opening, page(1, question()), later)
    assert snap.page_role(opening) == "info"
    assert snap.page_role(later) == "info"


@pytest.mark.parametrize("text", ["Read the package instructions carefully.", "Thank you. Now taste sample A.", ""])
def test_info_instructions_are_not_blindly_classified_as_welcome(text):
    result = run_review(survey(page(0, kind="info", text=text), page(1, question())))
    assert result.results["B4"].findings


def test_inferred_welcome_runs_content_standards_checks():
    snap = survey(page(0, kind="info", text="Welcome, participants! This takes 5 minutes."), page(1, question()))
    assert any('participants' in f.evidence for f in run_all(context(snap))["9.2"].findings)


def test_unknown_and_not_applicable_are_not_earned_points():
    results = {"1.1": CheckResult(criterion_id="1.1", fraction=1),
               "1.2": CheckResult(criterion_id="1.2", applies=False)}
    card = score(RUBRIC, results)
    assert card.score == 2
    assert card.unchecked_points == 95
    assert card.checked_points == 2
    assert card.not_applicable_points == 3
    assert card.strengths == [next(c.title for c in RUBRIC.criteria if c.id == "1.1")]
    assert "checked" in card.score_explanation.lower()


@pytest.mark.parametrize("fraction,evidence", [(0.2, None), (1, "Invented quote"), (0.2, "Invented quote")])
def test_unquotable_ai_assessment_stays_unknown_not_a_strength(fraction, evidence):
    snap = survey(intro(), page(1, question(text="How amazing is it?")))
    findings = [] if evidence is None else [AiFinding(criterion_id="5.1", headline="Leading", evidence=evidence,
        explanation="Use neutral words.", member_impact="May influence answers.", question_id="q1")]
    got = ground(BatchOutput(verdicts=[Verdict(criterion_id="5.1", fraction=fraction)], findings=findings),
                 WORDING, snap, RUBRIC)
    assert got.results["5.1"].fraction is None
    assert not score(RUBRIC, got.results).strengths


def test_merged_criterion_is_not_a_positive_check():
    snap = survey(intro(), page(1, question()))
    raw = AiFinding(criterion_id="1.2", headline="Opening lacks purpose", evidence=snap.intro_text,
                    explanation="This also covers 1.3.", member_impact="Unclear purpose.", page_id="p0")
    got = ground(BatchOutput(verdicts=[Verdict(criterion_id="1.2", fraction=.5),
                                     Verdict(criterion_id="1.3", fraction=1)], findings=[raw]), STORY, snap, RUBRIC)
    assert got.results["1.3"].fraction is None


@pytest.mark.parametrize("q", [
    question(kind="rating", text="How likely are you to recommend this to a friend?", options=(),
             scale=scale(11, "Not at all likely", "Extremely likely", [str(i) for i in range(11)])),
    question(kind="single_choice", text="How likely are you to recommend this?", options=tuple(map(str, range(11)))),
    question(kind="rating", text="How much do you like this?", options=(),
             scale=scale(9, "Dislike extremely", "Like extremely")),
    question(kind="rating", text="How sweet is it?", options=(),
             scale=scale(5, "Much too little", "Much too much", ["Much too little", "Too little", "Just about right", "Too much", "Much too much"])),
    question(kind="rating", options=(), scale=scale(5, "Excellent", "Poor", ["Excellent", "Very good", "Good", "Fair", "Poor"])),
])
def test_standard_research_scales_are_not_shortened_or_called_lopsided(q):
    results = run_all(context(survey(intro(), page(1, q))))
    assert not [f for cid in ("4.4", "6.2", "6.3") for f in results[cid].findings]


def test_nonstandard_long_scale_still_gets_reviewed():
    q = question(kind="rating", scale=scale(13, "Bad", "Good"))
    assert run_all(context(survey(intro(), page(1, q))))["6.3"].findings


@pytest.mark.parametrize("kind", ["slider", "ranking"])
def test_control_type_alone_is_not_a_measured_thumb_defect(kind):
    q = question(kind=kind)
    assert not run_all(context(survey(intro(), page(1, q))))["6.4"].findings


def test_required_final_comment_is_made_optional_not_duplicated():
    q = question(kind="text_long", text="Anything else?", options=())
    result = run_all(context(survey(intro(), page(1, q), thank_you())))["8.6"]
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.question_id == q.id
    assert "optional" in f.explanation.lower() and "add" not in f.explanation.lower()
    assert f.suggested_text is None


def test_time_rewrite_requires_calibration_not_missing_reward_context():
    text = "Welcome! This takes 1 minute."
    fixed = fixed_intro(text, 7, fix_time=True, add_reward=True)
    assert fixed == "Welcome! This takes about 7 minutes."
    result = run_all(context(survey(intro("Welcome!"), page(1, question()))))["1.4"]
    assert result.findings[0].suggested_text is None
    assert "calibrated" in result.findings[0].explanation.lower()
    assert "suggested intro does both" not in result.findings[0].explanation.lower()


def test_uncalibrated_branch_totals_never_raise_time_blockers():
    pages = [page(i + 1, question(f"q{i}", kind="text_long", options=(), conditional=True)) for i in range(40)]
    review = run_review(survey(intro("Welcome! This takes 1 minute."), *pages))
    assert not review.results["B5"].findings
    assert review.timing.path_uncertain
    assert not review.timing.calibrated
    assert not review.results["2.1"].findings


def test_uncalibrated_linear_estimate_is_not_a_time_blocker_either():
    pages = [page(i + 1, question(f"q{i}", kind="text_long", options=())) for i in range(30)]
    assert not run_review(survey(intro("Welcome! This takes 1 minute."), *pages)).results["B5"].findings


def test_ai_can_report_substantive_issue_on_cosmetically_flagged_question():
    cosmetic = issue("9.1", "Emoji in a question")
    substantive = issue()
    prompt = system_prompt(WORDING, RUBRIC)
    assert "independent" in prompt.lower()
    assert "never report these again" not in survey_block(survey(page(1, question())), [cosmetic]).lower()
    got = _with_ai({"5.1": CheckResult(criterion_id="5.1", fraction=1)},
                   {"5.1": CheckResult(criterion_id="5.1", fraction=.5, findings=[substantive])})
    assert got["5.1"].findings == [substantive]


def test_exact_code_ai_root_duplicate_is_reported_once_but_independent_issue_survives():
    original = issue("9.1", "Emoji in a question")
    duplicate = original.model_copy(update={"source": "ai"})
    independent = issue("9.1", "Leading wording", source="ai")
    merged = _with_ai({"9.1": CheckResult(criterion_id="9.1", findings=[original])},
                      {"9.1": CheckResult(criterion_id="9.1", fraction=.5,
                                          findings=[duplicate, independent])})
    assert merged["9.1"].findings == [original, independent]


def test_exact_root_duplicates_across_code_and_ai_criteria_are_merged_only_once():
    first = issue("B1")
    same = issue("5.1")
    independent = issue("9.2", "Capitalization")
    got = _merge({f.criterion_id: CheckResult(criterion_id=f.criterion_id, findings=[f])
                  for f in (independent, same, first)}, RUBRIC)
    assert got == [first, independent]


def test_reward_only_advice_does_not_offer_a_no_op_rewrite():
    text = "Welcome! This takes 5 minutes."
    got = run_all(context(survey(intro(text), page(1, question()))))["1.4"]
    assert got.findings[0].suggested_text is None


def test_lost_full_credit_duplicate_is_unknown_not_strength():
    got, _ = dedupe({"B1": CheckResult(criterion_id="B1", findings=[issue("B1")]),
                    "5.1": CheckResult(criterion_id="5.1", fraction=1, findings=[issue()])}, RUBRIC)
    assert got["5.1"].fraction is None
    assert not score(RUBRIC, got).strengths


def test_partial_blocker_check_does_not_silently_clear_semantic_risk():
    review = run_review(survey(intro(), page(1, question())))
    assert "B2" in review.scorecard.pending_blockers
    assert "B5" in review.scorecard.pending_blockers


def test_semantic_ai_can_clear_partial_blocker_without_erasing_code_defect():
    code = {"B2": CheckResult(criterion_id="B2", assessed=False)}
    ai = {"B2": CheckResult(criterion_id="B2")}
    got = _with_ai(code, ai)
    assert got["B2"].assessed
    defect = issue("B2", "Placeholder text")
    code["B2"].findings = [defect]
    assert _with_ai(code, ai)["B2"].findings == [defect]


def test_same_quote_is_not_enough_to_merge_different_root_causes():
    results = {"B1": CheckResult(criterion_id="B1", findings=[issue("B1")]),
               "9.2": CheckResult(criterion_id="9.2", fraction=.5, findings=[issue("9.2", "Capitalization")])}
    got, _ = dedupe(results, RUBRIC)
    assert got["9.2"].findings
