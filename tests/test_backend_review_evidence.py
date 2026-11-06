"""Regression contracts for retained assessment evidence and bounded round reads."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from builders import intro, page, question, survey, thank_you
from surveycoach.findings import CheckResult, Finding
from surveycoach.judge.judge import AiRunInfo
from surveycoach.review import run_review, _with_ai
from surveycoach.rubric import load_rubric
from surveycoach.scoring import score
from surveycoach.server.example import run_example
from surveycoach.server.repository import Repository
from surveycoach.server.rounds import compare_rounds, project_review
from surveycoach.server.service import run_job
from surveycoach.snapshot import SurveySnapshot
from test_committee_rounds import detail, finding, snapshot


def assessed_review(snap, flagged=False):
    result = run_review(snap)
    flags = [Finding(criterion_id="5.1", source="ai", severity="worth_improving",
                     headline="Leading wording", evidence="How did you like it?",
                     explanation="Use neutral wording", member_impact="Avoid bias",
                     question_id="old", suggested_text="What do you think?",
                     current_text="How did you like it?")] if flagged else []
    ai = {"5.1": CheckResult(criterion_id="5.1", fraction=0.5 if flagged else 1, findings=flags),
          "B1": CheckResult(criterion_id="B1"), "B2": CheckResult(criterion_id="B2")}
    result.results = _with_ai(result.results, ai)
    result.findings += flags
    result.scorecard = score(load_rubric(), result.results)
    result.ai = AiRunInfo(model="synthetic", checked=["wording"])
    return result


@pytest.mark.parametrize("runner,module", [(run_job, "service"), (run_example, "example")])
def test_new_reviews_persist_passes_and_project_same_score(runner, module):
    repo = Repository(":memory:")
    try:
        snap = survey(intro(), page(1, question()), thank_you())
        result = assessed_review(snap)
        submitted = repo.submit(snap, ai=True)
        with patch(f"surveycoach.server.{module}.run_review", return_value=result):
            if module == "service":
                runner(repo, submitted["job_id"], provider=object())
            else:
                runner(repo, submitted["job_id"])
        stored = json.loads(repo.db.execute("SELECT data FROM reviews").fetchone()[0])["review"]
        assert "timing" not in stored
        assert stored["results"]["B1"]["assessed"]
        projected = repo.detail(submitted["id"])["review"]
        assert projected["scorecard"] == result.scorecard.model_dump(mode="json")
        assert {"5.1", "B1", "B2"} <= set(projected["checked_criteria"])
        assert "B1" not in projected["scorecard"]["pending_blockers"]
    finally:
        repo.close()


def test_assessed_ai_failure_preserves_fraction_finding_and_checked_status():
    snap = SurveySnapshot.model_validate(snapshot())
    result = assessed_review(snap, flagged=True)
    historical = result.model_dump(mode="json", exclude={"timing"})
    historical["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint}
                              for f in result.findings]
    before = deepcopy(historical)
    projected = project_review(snap.model_dump(mode="json"), historical)
    assert projected["results"]["5.1"]["fraction"] == 0.5
    assert projected["results"]["5.1"]["assessed"]
    assert "5.1" in projected["checked_criteria"]
    assert projected["scorecard"] == result.scorecard.model_dump(mode="json")
    assert any(f["source"] == "ai" and f["criterion_id"] == "5.1" for f in projected["findings"])
    assert historical == before


def test_round_two_ai_pass_is_verified_as_fixed_not_unchecked():
    old = detail(decisions={"old": {"action": "pick", "picked_text": "What do you think?"}})
    old["review"]["findings"][0]["criterion_id"] = "5.1"
    current = detail(snapshot("What do you think?"), findings=[], version=2)
    snap = SurveySnapshot.model_validate(current["snapshot"])
    result = assessed_review(snap)
    current["review"] = project_review(current["snapshot"], result.model_dump(mode="json"))
    changes, carried = compare_rounds(old, current)
    assert changes["fixed"][0]["resolution"] == "Fixed with your rewrite"
    assert not changes["uncertain"] and not carried


@pytest.mark.parametrize("change", [
    {"required": False}, {"conditional": True}, {"help_text": "Only answer for last week"},
    {"scale": {"points": 7, "low_label": "Bad", "high_label": "Good", "labels": []}},
    {"scale": {"points": 5, "low_label": "Awful", "high_label": "Good", "labels": []}},
    {"scale": {"points": 5, "low_label": "Bad", "high_label": "Good", "labels": ["Middle"]}},
    {"options": [{"id": "a", "label": "Yes", "is_exclusive": True}, {"id": "b", "label": "No"}]},
    {"options": [{"id": "a", "label": "Yes", "is_other_with_text": True}, {"id": "b", "label": "No"}]},
])
def test_changed_design_never_carries_a_decision_or_claims_a_fix(change):
    old = detail(decisions={"old": {"action": "keep", "reason": "Tracker"}})
    old["snapshot"]["pages"][1]["questions"][0]["scale"] = {
        "points": 5, "low_label": "Bad", "high_label": "Good", "labels": []}
    now = deepcopy(old)
    now["version"] = 2
    now["snapshot"]["pages"][1]["questions"][0].update(change)
    for findings in ([finding()], []):
        now["review"]["findings"] = findings
        changes, carried = compare_rounds(old, now)
        assert changes["uncertain"] and not changes["fixed"] and not changes["still"]
        assert not carried


def test_long_history_projects_two_rounds_for_detail_and_one_for_save(monkeypatch):
    repo = Repository(":memory:")
    try:
        for number in range(1, 36):
            snap = survey(intro(), page(1, question()), title=f"Round {number}")
            submitted = repo.submit(snap, ai=False, survey_id=submitted["id"] if number > 1 else None)
            result = run_review(snap)
            encoded = result.model_dump(mode="json", exclude={"timing"})
            encoded["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint}
                                   for f in result.findings]
            repo.finish(submitted["job_id"], {"review": encoded})
        import surveycoach.server.repository as module
        original = module.project_review
        calls = []

        def counted(snap, review, *context):      # the reward answer rides along as a third argument
            calls.append(snap["title"])
            return original(snap, review, *context)

        monkeypatch.setattr(module, "project_review", counted)
        current = repo.detail(submitted["id"])
        assert calls == ["Round 35", "Round 34"]
        assert current["round_changes"]["compared_to_round"] == 34
        calls.clear()
        issue = current["review"]["findings"][0]
        monkeypatch.setattr(module, "compare_rounds", lambda *args: pytest.fail("Save walked history"))
        saved = repo.save_decision(submitted["id"], 35, issue["fingerprint"],
                                   {"action": "keep", "reason": "Intentional"})
        assert calls == ["Round 35"] and saved["reason"] == "Intentional"
    finally:
        repo.close()
