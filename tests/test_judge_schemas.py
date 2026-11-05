"""The AI judge's contract: which criteria it owns, and what shape its answers must take."""
import pytest
from pydantic import ValidationError

from surveycoach.findings import Finding, RewriteOption
from surveycoach.judge.batches import BATCHES
from surveycoach.judge.schemas import AiFinding, BatchOutput
from pathlib import Path

from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.checks.structure import OPEN_TEXT
from surveycoach.snapshot import SurveySnapshot

FIXTURES = Path(__file__).parent.parent / "fixtures"
IMAGE_CRITERIA_WAITING_FOR_PLAN_5 = {"7.1", "7.4"}
# 7.6 is measured, not judged: it waits for reader-measured file sizes, never for an AI batch (0A).
WAITING_FOR_MEASURED_BYTES = "7.6"
# 2.4 and 8.6 are code checks that wait on `required`, which no AI batch can know (D8 tri-state).
WAITING_FOR_REQUIRED_STATUS = {"2.4", "8.6"}


def unmeasured_media(snapshot):
    media = [m for p in snapshot.pages for m in [*p.media, *[m for q in p.questions for m in q.media],
                                                 *[o.media for q in p.questions for o in q.options if o.media]]]
    return [m for m in media if m.bytes is None]


def unknown_required_open_text(snapshot):
    return [q for q in snapshot.all_questions() if q.kind in OPEN_TEXT and q.required is None]


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
    """Pending checks have owners; timing and reader loading need non-AI verification."""
    rubric = load_rubric()
    title = {c.id: c.title for c in rubric.criteria}
    owned = {title[c] for b in BATCHES for c in b.criteria} | {title[c] for c in IMAGE_CRITERIA_WAITING_FOR_PLAN_5}
    for path in sorted(FIXTURES.glob("*.json")):
        snapshot = SurveySnapshot.model_validate_json(path.read_text())
        review = run_review(snapshot, rubric)
        # 7.6 may wait only while some image really has no measured size; otherwise it is a missed check.
        waiting_on_bytes = title[WAITING_FOR_MEASURED_BYTES] in review.unchecked
        assert not waiting_on_bytes or unmeasured_media(snapshot), path.name
        pending = set(review.unchecked) - ({title[WAITING_FOR_MEASURED_BYTES]} if waiting_on_bytes else set())
        # 2.4/8.6 may wait only while some typing question really has unknown requiredness.
        waiting_on_required = {title[c] for c in WAITING_FOR_REQUIRED_STATUS} & pending
        assert not waiting_on_required or unknown_required_open_text(snapshot), path.name
        pending -= waiting_on_required
        assert pending <= owned, (path.name, pending - owned)
        ai_blockers = {x for b in BATCHES for x in b.blockers}
        assert set(review.scorecard.pending_blockers) <= ai_blockers | {"B5", "B7"}, path.name
        assert "B7" not in ai_blockers
        if "B7" in review.scorecard.pending_blockers:
            assert not review.results["B7"].assessed
            assert review.results["B7"].findings
            assert all(f.severity == "worth_improving" for f in review.results["B7"].findings)
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
