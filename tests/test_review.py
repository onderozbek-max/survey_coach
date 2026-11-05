import subprocess
import sys
from pathlib import Path

from builders import context, intro, page, question, survey, thank_you

from surveycoach.cli import render
from surveycoach.checks import run_all
from surveycoach.checks.registry import REGISTRY
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot

ROOT = Path(__file__).parent.parent
RUBRIC = load_rubric()

# Auto-capable rubric items we have deliberately not built yet. A new gap must be added here on purpose.
KNOWN_UNBUILT = {"1.1", "3.4", "7.1", "8.1"}


def load_fixture(name: str) -> SurveySnapshot:
    return SurveySnapshot.model_validate_json((ROOT / f"fixtures/{name}.json").read_text())


def test_every_registered_check_is_a_real_rubric_id():
    known = {c.id for c in RUBRIC.criteria} | {b.id for b in RUBRIC.blockers}
    assert set(REGISTRY) <= known


def test_every_active_auto_criterion_has_a_check_or_is_a_known_gap():
    auto = {c.id for c in RUBRIC.criteria if c.active and "Auto" in c.check}
    auto |= {b.id for b in RUBRIC.blockers if "Auto" in b.check}
    assert auto - set(REGISTRY) == KNOWN_UNBUILT


def test_no_check_crashes_on_an_empty_survey():
    results = run_all(context(survey()))
    assert set(results) == set(REGISTRY)


def test_flawed_fixture_needs_work_with_pending_image_verification_and_citations():
    review = run_review(load_fixture("boxer-briefs"))
    assert review.scorecard.readiness == "needs_work"
    assert review.scorecard.open_blockers == []
    assert "B7" in review.scorecard.pending_blockers
    assert not review.results["B7"].assessed
    assert review.findings[0].criterion_id == "B7"
    assert review.findings[0].severity == "worth_improving"
    cited = {f.criterion_id for f in review.findings}
    assert {"4.2", "6.3", "6.4", "7.2", "9.2"} <= cited
    assert review.scorecard.provisional


def test_clean_fixture_is_never_called_ready_while_ai_blockers_are_pending():
    review = run_review(load_fixture("coffee-pods"))
    card = review.scorecard
    expected_earned = sum(c.points * review.results[c.id].fraction for c in RUBRIC.criteria
                          if c.active and c.id in review.results and review.results[c.id].applies
                          and review.results[c.id].fraction is not None)
    # coffee-pods has no scales or grids: 4.4 and 6.3 (2 points each) used to earn 4 points for
    # categories that do not exist (audit 18); they are explicit N/A now.
    assert card.score == expected_earned == 39
    assert card.unchecked_points == 54 and card.checked_points == 39
    assert card.not_applicable_points == 7
    assert card.open_blockers == []
    assert card.pending_blockers == ["B1", "B2", "B5", "B6"]
    assert card.readiness != "ready"
    assert not [f for f in review.findings if f.severity == "must_fix"]


def test_findings_are_deduplicated_by_fingerprint():
    review = run_review(load_fixture("boxer-briefs"))
    prints = [f.fingerprint for f in review.findings]
    assert len(prints) == len(set(prints))


def test_unchecked_lists_the_ai_only_work():
    review = run_review(load_fixture("coffee-pods"))
    assert "Warm and human" in review.unchecked and "One idea per question" in review.unchecked


def test_review_is_deterministic():
    a, b = run_review(load_fixture("boxer-briefs")), run_review(load_fixture("boxer-briefs"))
    assert a.model_dump() == b.model_dump()


def test_cli_reports_earned_points_without_subtracting_unknown_points():
    review = run_review(load_fixture("boxer-briefs"))
    card = review.scorecard
    out = render(review)
    assert f"Score on the {card.checked_points} points checked so far: {card.score:.1f} of {card.checked_points}" in out
    assert "Uncalibrated estimated member completion" in out
    assert "not crawl or load time" in out
    assert "timed pilot" in out


def test_cli_prints_a_readable_review():
    out = subprocess.run([sys.executable, "-m", "surveycoach", "review", "fixtures/boxer-briefs.json"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "Readiness: Needs work" in out
    assert "MUST FIX (0)" in out
    assert "B1, B2, B5, B6, B7) are still unchecked" in out
    assert "Reader could not verify image loading" in out
    assert "WHAT'S WORKING" in out
