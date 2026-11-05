"""The AI judge merged into the real scored review, using the flawed Boxer Briefs sample."""
import subprocess
import sys
from pathlib import Path

import pytest

from surveycoach import cli
from surveycoach.judge.batches import BATCHES
from surveycoach.judge.schemas import AiFinding, BatchOutput, BlockerCall, Verdict
from surveycoach.llm import FakeProvider, LlmError, LlmUnavailable
from surveycoach.review import run_review
from surveycoach.snapshot import SurveySnapshot

ROOT = Path(__file__).parent.parent
IMAGES_STILL_WAITING = {"The right image is there", "The product is the hero", "Readable, light, and accessible"}
# 7.6 joined the set: boxer-briefs has an image with no measured bytes, which used to earn full
# credit (audit 5). Unmeasured weight is unknown, so the criterion waits for evidence.


@pytest.fixture(scope="module")
def flawed() -> SurveySnapshot:
    return SurveySnapshot.model_validate_json((ROOT / "fixtures" / "boxer-briefs.json").read_text())


def batch_of(system: str):
    return next(b for b in BATCHES if f"Your job in this call: {b.title}" in system)


def verdicts(batch, blockers_triggered=()):
    return BatchOutput(verdicts=[Verdict(criterion_id=c, fraction=1.0) for c in batch.criteria],
                       blockers=[BlockerCall(blocker_id=b, triggered=b in blockers_triggered) for b in batch.blockers])


def clear_provider(extra_findings=(), triggered=()):
    def answer(system: str, data: str) -> BatchOutput:
        batch = batch_of(system)
        mine = [f for f in extra_findings if f.criterion_id in (*batch.criteria, *batch.blockers)]
        return verdicts(batch, triggered).model_copy(update={"findings": mine})
    return FakeProvider({"BatchOutput": answer})


def failing_provider(error=LlmError("Wibey timed out after 180 s")):
    def answer(system: str, data: str):
        raise error
    return FakeProvider({"BatchOutput": answer})


def test_without_a_provider_nothing_changes(flawed):
    assert run_review(flawed).model_dump() == run_review(flawed, provider=None).model_dump()
    assert run_review(flawed).ai is None


def test_all_clear_judge_resolves_semantic_blockers_but_cannot_calibrate_timing(flawed):
    code_only, review = run_review(flawed), run_review(flawed, provider=clear_provider())
    assert review.scorecard.pending_blockers == ["B5", "B7"] and set(review.unchecked) == IMAGES_STILL_WAITING
    assert not review.results["B7"].assessed  # AI cannot resolve a reader-only image observation.
    # Checking more earns evidence-backed points; unknown checks never get free credit.
    assert review.scorecard.unchecked_points == 6 < code_only.scorecard.unchecked_points == 56
    assert review.scorecard.score > code_only.scorecard.score
    assert review.scorecard.checked_points == 89
    assert review.scorecard.not_applicable_points == 5
    assert sum((review.scorecard.checked_points, review.scorecard.unchecked_points,
                review.scorecard.not_applicable_points)) == 100
    assert review.results["9.1"].fraction == 0.75  # All-clear AI does not erase the emoji defect.
    assert [f.headline for f in review.findings if f.source == "auto"] == [f.headline for f in code_only.findings]
    assert review.ai.checked == ["wording", "story", "flow"] and review.ai.failed == {}


def test_a_judge_that_is_down_leaves_the_review_exactly_as_honest_as_before(flawed):
    code_only, review = run_review(flawed), run_review(flawed, provider=failing_provider(LlmUnavailable("no wibey")))
    assert review.scorecard == code_only.scorecard and review.unchecked == code_only.unchecked
    assert review.scorecard.pending_blockers == ["B1", "B2", "B5", "B6", "B7"] and set(review.ai.failed) == {"wording", "story", "flow"}


def test_a_triggered_ai_blocker_becomes_a_must_fix_finding_and_sorts_first(flawed):
    leading = AiFinding(criterion_id="B1", page_id="p4", question_id="q4", headline="The main question pushes members toward love",
                        evidence="LOVE the fit", explanation="Ask how well it fits.", member_impact="Members feel steered.")
    review = run_review(flawed, provider=clear_provider([leading], triggered=("B1",)))
    ai_blocker = next(f for f in review.findings if f.criterion_id == "B1")
    assert (ai_blocker.source, ai_blocker.severity, ai_blocker.question_id) == ("ai", "must_fix", "q4")
    assert review.findings[0] == ai_blocker
    assert [f.criterion_id for f in review.findings if f.severity == "must_fix"] == ["B1"]
    assert "B7" in review.scorecard.pending_blockers and not review.results["B7"].assessed
    assert all(f.severity == "worth_improving" for f in review.results["B7"].findings)
    assert "B1" in review.scorecard.open_blockers and review.scorecard.readiness == "needs_work"


def test_a_criterion_the_code_only_half_judged_keeps_its_code_finding_and_takes_the_ai_verdict(flawed):
    review = run_review(flawed, provider=clear_provider())
    nine_one = review.results["9.1"]
    assert nine_one.fraction == 0.75                                    # AI said 1.0, but a real emoji finding caps it
    assert any(f.headline == "Emoji in a question" and f.source == "auto" for f in nine_one.findings)


def test_a_criterion_the_code_fully_judged_is_never_overridden_by_the_ai(flawed):
    code_only = run_review(flawed)
    wrong = AiFinding(criterion_id="4.2", page_id="p2", question_id="q2", headline="Ranges are fine", evidence="How long",
                      explanation="x", member_impact="m")
    review = run_review(flawed, provider=clear_provider([wrong]))
    assert review.results["4.2"] == code_only.results["4.2"]


def run_cli(*args, **env):
    return subprocess.run([sys.executable, "-m", "surveycoach", "review", "fixtures/boxer-briefs.json", *args],
                          cwd=ROOT, capture_output=True, text=True, check=True, env={**__import__("os").environ, **env}).stdout


def test_the_cli_says_the_ai_has_not_run_unless_asked():
    out = run_cli()
    assert "AI check: not run" in out and "AI judge" not in out


def test_the_cli_reports_the_ai_run_and_marks_ai_findings(monkeypatch, capsys, flawed):
    finding = AiFinding(criterion_id="5.1", page_id="p4", question_id="q4", headline="Leading words in the question",
                        evidence="LOVE the fit", explanation="Ask it neutrally.", member_impact="Members feel steered.")
    monkeypatch.setattr(cli, "WibeyProvider", lambda: clear_provider([finding]))
    cli.main(["review", str(ROOT / "fixtures" / "boxer-briefs.json"), "--ai"])
    out = capsys.readouterr().out
    assert "AI judge (gpt-6.1-sol): checked 3 of 3 parts" in out and "[AI] Leading words in the question" in out


def test_the_cli_names_what_the_ai_could_not_check(monkeypatch, capsys):
    monkeypatch.setattr(cli, "WibeyProvider", lambda: failing_provider())
    cli.main(["review", str(ROOT / "fixtures" / "boxer-briefs.json"), "--ai"])
    out = capsys.readouterr().out
    assert "could not check: Wording and answer choices, Intro, voice and thank-you, Order and relevance" in out
    assert "Wibey timed out after 180 s" in out and "Readiness: Needs work" in out


def test_the_judge_is_told_what_the_code_checks_already_found(flawed):
    fake = clear_provider()
    run_review(flawed, provider=fake)
    data = fake.calls[0][1]
    assert "ALREADY FOUND BY CODE" in data and "Emoji in a question" in data and "Answer ranges overlap" in data


def test_the_cli_lists_the_claims_it_refused_so_nothing_is_hidden(monkeypatch, capsys):
    invented = AiFinding(criterion_id="5.1", page_id="p4", question_id="q4", headline="h", evidence="a sentence nobody wrote",
                         explanation="x", member_impact="m")
    monkeypatch.setattr(cli, "WibeyProvider", lambda: clear_provider([invented]))
    cli.main(["review", str(ROOT / "fixtures" / "boxer-briefs.json"), "--ai"])
    out = capsys.readouterr().out
    assert "ignored 2 claims the survey did not back up" in out
    assert "wording: 5.1: the quote was not found" in out
    assert "wording: 5.1: no independent grounded assessment; remains unchecked" in out
