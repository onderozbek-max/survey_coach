from surveycoach.findings import CheckResult, Finding
from surveycoach.rubric import load_rubric
from surveycoach.scoring import score

RUBRIC = load_rubric()
AUTO_AND_AI = [c for c in RUBRIC.criteria if c.active]


def full_marks() -> dict[str, CheckResult]:
    results = {c.id: CheckResult(criterion_id=c.id, fraction=1.0) for c in AUTO_AND_AI}
    results.update({b.id: CheckResult(criterion_id=b.id) for b in RUBRIC.blockers})   # every blocker checked, none open
    return results


def must_fix(blocker_id: str) -> Finding:
    return Finding(criterion_id=blocker_id, severity="must_fix", headline="h", evidence="x", explanation="y", member_impact="z")


def test_all_full_marks_is_100_and_ready():
    card = score(RUBRIC, full_marks())
    assert card.score == 100
    assert card.readiness == "ready"
    assert not card.provisional


def test_no_results_is_provisional_with_no_earned_credit():
    card = score(RUBRIC, {})
    assert card.score == 0
    assert card.checked_points == 0
    assert card.strengths == []
    assert card.provisional
    assert card.unchecked_points == 100


def test_fraction_scales_the_rubric_points():
    results = full_marks()
    results["2.1"] = CheckResult(criterion_id="2.1", fraction=0.6)   # 5 points x 0.6 = 3
    card = score(RUBRIC, results)
    assert card.score == 98
    assert card.by_dimension["D2"].earned == 11


def test_open_blocker_forces_needs_work_even_with_a_high_score():
    results = full_marks()
    results["B4"] = CheckResult(criterion_id="B4", findings=[must_fix("B4")])
    card = score(RUBRIC, results)
    assert card.score == 100
    assert card.open_blockers == ["B4"]
    assert card.readiness == "needs_work"


def test_kept_blocker_is_not_open_but_is_listed():
    results = full_marks()
    results["B5"] = CheckResult(criterion_id="B5", findings=[must_fix("B5")])
    card = score(RUBRIC, results, kept_blockers=frozenset({"B5"}))
    assert card.open_blockers == []
    assert card.kept_blockers == ["B5"]
    assert card.readiness == "ready"


def eighty_exactly() -> dict[str, CheckResult]:
    results = full_marks()
    for cid in ("2.1", "1.3", "8.3", "10.1", "7.2"):     # -5 -4 -4 -4 -3 = -20
        results[cid] = CheckResult(criterion_id=cid, fraction=0.0)
    return results


def test_readiness_uses_the_exact_score_not_a_rounded_one():
    results = eighty_exactly()
    results["2.4"] = CheckResult(criterion_id="2.4", fraction=0.75)   # -0.5 -> 79.5
    card = score(RUBRIC, results)
    assert card.score == 79.5
    assert card.readiness == "almost_ready"


def test_exactly_80_is_ready_and_59_is_needs_work():
    results = eighty_exactly()
    assert score(RUBRIC, results).score == 80
    assert score(RUBRIC, results).readiness == "ready"
    for cid in ("1.2", "7.3", "7.5", "6.1", "8.1", "8.2", "9.1", "10.3", "4.1", "5.1"):
        results[cid] = CheckResult(criterion_id=cid, fraction=0.0)
    assert score(RUBRIC, results).score < 60
    assert score(RUBRIC, results).readiness == "needs_work"


def test_strengths_are_the_three_heaviest_full_credit_criteria():
    results = full_marks()
    results["8.3"] = CheckResult(criterion_id="8.3", fraction=0.0)
    card = score(RUBRIC, results)
    assert len(card.strengths) == 3
    assert "An insider moment" not in card.strengths


def test_fingerprint_is_stable_and_ignores_whitespace_and_case():
    a = Finding(criterion_id="6.2", severity="worth_improving", headline="h", question_id="q1", evidence="Too  LONG",
                explanation="e", member_impact="m")
    b = a.model_copy(update={"evidence": "too long"})
    assert a.fingerprint == b.fingerprint
    assert a.fingerprint != a.model_copy(update={"question_id": "q2"}).fingerprint


def test_ready_needs_every_blocker_checked_so_pending_ai_blockers_cap_it():
    results = full_marks()
    del results["B1"]      # the AI judge has not run yet
    card = score(RUBRIC, results)
    assert card.score == 100
    assert card.pending_blockers == ["B1"]
    assert card.readiness == "almost_ready"
