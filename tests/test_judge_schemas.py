"""The AI judge's contract: which criteria it owns, and what shape its answers must take."""
import pytest
from pydantic import ValidationError

from surveycoach.findings import Finding, RewriteOption
from surveycoach.judge.batches import BATCHES
from surveycoach.judge.schemas import AiFinding, BatchOutput
from pathlib import Path

from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot

FIXTURES = Path(__file__).parent.parent / "fixtures"
IMAGE_CRITERIA_WAITING_FOR_PLAN_5 = {"7.1", "7.4"}


def test_every_batch_names_real_active_criteria_and_blockers():
    rubric = load_rubric()
    active = {c.id for c in rubric.criteria if c.active}
    blockers = {b.id for b in rubric.blockers}
    for batch in BATCHES:
        assert set(batch.criteria) <= active and set(batch.blockers) <= blockers, batch.id


def test_no_criterion_or_blocker_is_judged_twice():
    criteria = [c for b in BATCHES for c in b.criteria]
    blockers = [x for b in BATCHES for x in b.blockers]
    assert len(criteria) == len(set(criteria)) and len(blockers) == len(set(blockers))


def test_the_batches_cover_everything_the_engine_says_is_waiting_on_ai():
    """Every pending check has an owner; timing needs calibration, not an AI all-clear."""
    rubric = load_rubric()
    title = {c.id: c.title for c in rubric.criteria}
    owned = {title[c] for b in BATCHES for c in b.criteria} | {title[c] for c in IMAGE_CRITERIA_WAITING_FOR_PLAN_5}
    for path in sorted(FIXTURES.glob("*.json")):
        review = run_review(SurveySnapshot.model_validate_json(path.read_text()), rubric)
        assert set(review.unchecked) <= owned, (path.name, set(review.unchecked) - owned)
        ai_blockers = {x for b in BATCHES for x in b.blockers}
        assert set(review.scorecard.pending_blockers) <= ai_blockers | {"B5"}, path.name
        assert "B5" not in ai_blockers
        assert not review.timing.calibrated and not review.results["B5"].assessed


def test_the_judge_only_owns_criteria_the_rubric_says_need_ai():
    rubric = load_rubric()
    needs_ai = {c.id for c in rubric.criteria if "AI" in c.check} | {b.id for b in rubric.blockers if "AI" in b.check}
    assert {x for b in BATCHES for x in (*b.criteria, *b.blockers)} <= needs_ai


def test_a_verdict_fraction_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        BatchOutput.model_validate_json('{"verdicts": [{"criterion_id": "5.1", "fraction": 1.4}]}')


def test_a_minimal_answer_is_valid_and_findings_default_to_worth_improving():
    out = BatchOutput.model_validate_json('{"findings": [{"criterion_id": "5.1", "headline": "h", "evidence": "e", '
                                          '"explanation": "x", "member_impact": "m"}]}')
    assert out.verdicts == [] and out.findings[0].severity == "worth_improving" and out.findings[0].options == []
    assert isinstance(out.findings[0], AiFinding)


def test_findings_still_validate_without_rewrite_options_and_accept_them():
    base = dict(criterion_id="5.1", severity="worth_improving", headline="h", evidence="e", explanation="x", member_impact="m")
    assert Finding(**base).options == []
    assert Finding(**base, options=[RewriteOption(label="Shorter", text="Hi")]).options[0].label == "Shorter"
