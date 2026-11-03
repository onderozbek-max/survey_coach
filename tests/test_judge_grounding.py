"""Grounding: an AI answer only counts for as much as the survey itself can back up."""
from surveycoach.judge.batches import WORDING
from surveycoach.judge.grounding import ground
from surveycoach.judge.schemas import AiFinding, BatchOutput, BlockerCall, Verdict
from surveycoach.findings import Finding, RewriteOption
from surveycoach.rubric import load_rubric
from tests.builders import intro, page, question, survey, thank_you

RUBRIC = load_rubric()
LOUD = "How much did you LOVE the amazing softness?"


def snapshot():
    loud = question("q1", LOUD, options=("A lot", "A little"))
    other = question("q2", "How often do you buy briefs?", options=("Weekly", "Monthly"))
    return survey(intro("Welcome! This takes about 3 minutes."), page(1, loud), page(2, other), thank_you())


def finding(**overrides) -> AiFinding:
    base = dict(criterion_id="5.1", page_id="p1", question_id="q1", headline="Leading words in the question",
                evidence="LOVE the amazing softness", explanation="Ask it neutrally.", member_impact="Members feel steered.")
    return AiFinding(**{**base, **overrides})


def output(findings=(), fraction=1.0, blockers=(), skip=(), only=None) -> BatchOutput:
    """Every criterion gets `fraction`, unless `only` names the single criterion that should get it."""
    verdicts = [Verdict(criterion_id=c, fraction=fraction if only in (None, c) else 1.0) for c in WORDING.criteria if c not in skip]
    return BatchOutput(verdicts=verdicts, blockers=list(blockers), findings=list(findings))


def run(out: BatchOutput):
    return ground(out, WORDING, snapshot(), RUBRIC)


def the_finding(grounded, criterion="5.1"):
    return grounded.results[criterion].findings[0]


def test_a_quotable_finding_keeps_its_place_and_is_marked_as_ai():
    grounded = run(output([finding()], fraction=0.5, only="5.1"))
    f = the_finding(grounded)
    assert (f.source, f.page_id, f.question_id, f.severity) == ("ai", "p1", "q1", "worth_improving")
    assert grounded.results["5.1"].fraction == 0.5 and grounded.dropped == []


def test_findings_for_criteria_outside_the_batch_are_dropped():
    grounded = run(output([finding(criterion_id="10.1")]))
    assert grounded.results["5.1"].findings == [] and len(grounded.dropped) == 1


def test_unknown_pages_unknown_questions_and_questions_on_the_wrong_page_are_dropped():
    for bad in (dict(page_id="p9"), dict(question_id="q9"), dict(page_id="p2", question_id="q1")):
        assert run(output([finding(**bad)])).results["5.1"].findings == [], bad


def test_a_quote_that_is_not_in_the_survey_is_dropped_as_invented():
    grounded = run(output([finding(evidence="You must agree this is the softest ever")]))
    assert grounded.results["5.1"].findings == [] and "quote" in grounded.dropped[0].lower()


def test_quote_matching_ignores_case_spacing_and_curly_quotes():
    assert run(output([finding(evidence="love   THE amazing\nsoftness")])).results["5.1"].findings
    q = question("q1", "Is it Member's Mark?")
    snap = survey(intro(), page(1, q), thank_you())
    got = ground(output([finding(evidence="Member\u2019s Mark")]), WORDING, snap, RUBRIC)
    assert got.results["5.1"].findings


def test_the_quote_must_come_from_the_place_the_finding_cites():
    # "Weekly" is a real word in q2, but the finding cites q1.
    assert run(output([finding(evidence="Weekly")])).results["5.1"].findings == []


def test_a_whole_survey_finding_may_quote_any_text_in_the_survey():
    f = finding(page_id=None, question_id=None, criterion_id="3.5", evidence="takes about 3 minutes")
    assert run(output([f])).results["3.5"].findings


def test_a_before_text_that_is_not_verbatim_removes_the_fake_before_and_after_but_keeps_the_finding():
    f = finding(current_text="How much did you adore the softness?", suggested_text="How soft was it?",
                options=[RewriteOption(label="Neutral", text="How soft was it?")])
    kept = the_finding(run(output([f])))
    assert kept.current_text is None and kept.suggested_text is None and kept.options == []


def test_a_verbatim_before_text_keeps_the_rewrite_and_a_stray_highlight_is_cleared():
    f = finding(current_text=LOUD, suggested_text="How would you rate the softness?", highlight="adore")
    kept = the_finding(run(output([f])))
    assert kept.current_text == LOUD and kept.suggested_text == "How would you rate the softness?" and kept.highlight is None
    assert the_finding(run(output([finding(current_text=LOUD, suggested_text="x", highlight="LOVE")]))).highlight == "LOVE"


def test_a_suggestion_identical_to_the_original_is_not_a_suggestion():
    kept = the_finding(run(output([finding(current_text=LOUD, suggested_text=LOUD)])))
    assert kept.suggested_text is None


def test_options_are_capped_at_three_empty_ones_are_removed_and_the_first_becomes_the_suggestion():
    options = [RewriteOption(label="Neutral", text="How soft was it?"), RewriteOption(label="Empty", text="  "),
               RewriteOption(label="Shorter", text="Soft?"), RewriteOption(label="Friendlier", text="How soft did it feel?"),
               RewriteOption(label="Extra", text="Too many")]
    kept = the_finding(run(output([finding(current_text=LOUD, options=options)])))
    assert [o.label for o in kept.options] == ["Neutral", "Shorter", "Friendlier"] and kept.suggested_text == "How soft was it?"


def test_must_fix_is_only_for_blockers():
    assert the_finding(run(output([finding(severity="must_fix")]))).severity == "worth_improving"


def test_unsupported_point_loss_stays_unknown_with_a_visible_reason():
    grounded = run(output([], fraction=0.2, only="5.1"))
    assert grounded.results["5.1"].fraction is None
    assert any(n.startswith("5.1") and "remains unchecked" in n for n in grounded.dropped)


def test_a_finding_caps_credit_at_three_quarters_but_a_lower_verdict_stands():
    assert run(output([finding()], fraction=0.9)).results["5.1"].fraction == 0.75
    assert run(output([finding()], fraction=0.4)).results["5.1"].fraction == 0.4


def test_a_criterion_the_judge_did_not_answer_stays_unchecked():
    assert "5.2" not in run(output(skip=("5.2",))).results and "5.1" in run(output(skip=("5.2",))).results


def test_a_triggered_blocker_with_a_quotable_finding_is_open_and_must_fix():
    blocker = finding(criterion_id="B1", severity="worth_improving")
    result = run(output([blocker], blockers=[BlockerCall(blocker_id="B1", triggered=True)])).results["B1"]
    assert [f.severity for f in result.findings] == ["must_fix"]


def test_blockers_not_triggered_are_clear_and_unanswered_blockers_stay_pending():
    grounded = run(output(blockers=[BlockerCall(blocker_id="B1", triggered=False)]))
    assert grounded.results["B1"].findings == [] and "B2" not in grounded.results and "B6" not in grounded.results


def test_a_triggered_blocker_that_cannot_be_quoted_is_not_raised_and_says_why():
    ungrounded = finding(criterion_id="B1", evidence="invented quote")
    grounded = run(output([ungrounded], blockers=[BlockerCall(blocker_id="B1", triggered=True)]))
    assert "B1" not in grounded.results  # Unsupported risk is pending, not cleared.
    assert any("B1" in note and "no quotable reason" in note for note in grounded.dropped)


def test_a_finding_for_a_blocker_that_was_not_triggered_is_dropped():
    grounded = run(output([finding(criterion_id="B1")], blockers=[BlockerCall(blocker_id="B1", triggered=False)]))
    assert grounded.results["B1"].findings == []


def test_no_criterion_gets_more_than_three_findings_and_the_rest_are_reported_as_dropped():
    many = [finding(evidence="LOVE the amazing softness", headline=f"Problem {i}") for i in range(5)]
    grounded = run(output(many, fraction=0.5, only="5.1"))
    assert [f.headline for f in grounded.results["5.1"].findings] == ["Problem 0", "Problem 1", "Problem 2"]
    assert len([n for n in grounded.dropped if "too many" in n]) == 2


def test_the_survey_title_is_quotable_for_the_title_criterion_even_when_a_page_is_cited():
    from surveycoach.judge.batches import STORY
    title = snapshot().title
    f = finding(criterion_id="1.1", page_id="p0", question_id=None, evidence=title)
    grounded = ground(BatchOutput(verdicts=[Verdict(criterion_id="1.1", fraction=0.5)], findings=[f]), STORY, snapshot(), RUBRIC)
    assert grounded.results["1.1"].findings and grounded.dropped == []


def test_the_title_is_not_a_loophole_for_other_criteria():
    title = snapshot().title
    assert run(output([finding(evidence=title)])).results["5.1"].findings == []


def test_a_rewrite_that_bundles_answer_choices_is_structural_so_it_is_never_swapped_into_the_question_text():
    bundle = [RewriteOption(label="Neutral", text=f"{LOUD}\nA lot\nA little\nNone of these")]
    kept = the_finding(run(output([finding(current_text=LOUD, options=bundle)])))
    assert kept.structural is True and kept.edit_kind == 'add_answer'
    assert kept.options[0].text == 'None of these'  # copy just the addition; never replace the stem


def test_a_single_line_rewrite_is_a_plain_text_swap():
    kept = the_finding(run(output([finding(current_text=LOUD, suggested_text="How soft was it?")])))
    assert kept.structural is False


def test_findings_default_to_not_structural():
    assert Finding(criterion_id="5.1", severity="worth_improving", headline="h", evidence="e", explanation="x",
                   member_impact="m").structural is False


def test_a_quote_spanning_the_question_and_one_of_its_choices_is_accepted_when_every_line_is_real():
    both = f"{LOUD}\n    option: A lot"                           # the model copied our 'option:' label along with the text
    assert the_finding(run(output([finding(evidence=both)], fraction=0.5, only="5.1"))).evidence == both


def test_one_invented_line_in_a_multi_line_quote_sinks_the_whole_quote():
    faked = f"{LOUD}\n    option: Absolutely everything"
    grounded = run(output([finding(evidence=faked)], fraction=0.5, only="5.1"))
    assert grounded.results["5.1"].findings == [] and any("quote was not found" in note for note in grounded.dropped)


def test_a_quote_made_only_of_labels_is_not_a_quote():
    grounded = run(output([finding(evidence="option:\nrow:")], fraction=0.5, only="5.1"))
    assert grounded.results["5.1"].findings == [] and any("quote was not found" in note for note in grounded.dropped)


def test_a_bundle_is_structural_even_when_the_models_before_text_is_the_whole_multi_line_original():
    whole = f"{LOUD}\nA lot\nA little"
    bundle = [RewriteOption(label="Neutral", text=f"{LOUD}\nA lot\nA little\nNone of these")]
    kept = the_finding(run(output([finding(current_text=whole, options=bundle)])))
    assert kept.structural is True


def test_a_multi_line_rewrite_with_no_before_text_is_structural_too():
    bundle = [RewriteOption(label="Neutral", text="A new question?\nYes\nNo")]
    assert the_finding(run(output([finding(options=bundle)]))).structural is True
