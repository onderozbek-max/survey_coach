"""Read projections refresh code evidence without rewriting stored reviews."""
from copy import deepcopy

import pytest

from builders import intro, page, question, scale, survey, thank_you
from surveycoach.findings import Finding
from surveycoach.review import run_review
from surveycoach.server.repository import Repository
from surveycoach.server.rounds import project_review


def stored_review(snapshot):
    result = run_review(snapshot)
    data = result.model_dump(mode="json", exclude={"results", "timing"})
    data["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    data["checked_criteria"] = ["B1", "5.1", "6.3"]
    return data


def old_flag(cid, source="auto"):
    return {"criterion_id": cid, "severity": "must_fix" if cid.startswith("B") else "worth_improving",
            "headline": "Old flag", "evidence": "Historical evidence", "explanation": "Old explanation",
            "member_impact": "Old impact", "source": source, "fingerprint": "old-" + cid,
            "page_id": "p1", "question_id": "q1"}


def validated_scale():
    return survey(intro(), page(1, question(text="How likely are you to recommend this?", kind="rating",
                  options=(), scale=scale(11, "Not at all likely", "Extremely likely", [str(i) for i in range(11)]))),
                  thank_you())


def test_removes_old_validated_scale_flags_and_rescores_every_code_check():
    snap = validated_scale()
    historical = stored_review(snap)
    historical["findings"] += [old_flag(cid) for cid in ("4.4", "6.2", "6.3")]
    historical["scorecard"].update(score=100, strengths=["Invented strength"], unchecked_points=0)
    before = deepcopy(historical)
    projected = project_review(snap.model_dump(mode="json"), historical)
    assert not [f for f in projected["findings"] if f["criterion_id"] in {"4.4", "6.2", "6.3"}]
    assert projected["scorecard"] == run_review(snap).scorecard.model_dump(mode="json")
    assert historical == before
    assert set(projected["projection"]["deterministic_criteria"]) == set(run_review(snap).results)


def test_saved_title_and_raw_wording_checks_are_refreshed():
    snap = survey(intro(), page(1, question(text="CUSTOMERS!!! Which Flavor Do You Like Best?")),
                  title="Pick Our Next Flavor")
    historical = stored_review(snap)
    historical["findings"] = []
    projected = project_review(snap.model_dump(mode="json"), historical)
    assert [f for f in projected["findings"] if f["criterion_id"] == "9.2"]
    assert projected["scorecard"] == run_review(snap).scorecard.model_dump(mode="json")


def test_retained_assessed_ai_result_restores_credit_when_code_cannot_assess():
    snap = validated_scale()
    historical = run_review(snap).model_dump(mode="json")
    historical["ai"] = {"model": "old", "checked": ["story"], "failed": {}}
    historical["results"]["9.1"]["fraction"] = 1
    historical["results"]["9.1"]["findings"] = []
    historical["scorecard"]["strengths"] = ["Warm and human"]
    projected = project_review(snap.model_dump(mode="json"), historical)
    assert projected["results"]["9.1"]["fraction"] == 1
    assert "9.1" in projected["checked_criteria"]
    assert projected["projection"]["ai_score_reconstructed"] is True
    assert projected["scorecard"]["score"] > run_review(snap).scorecard.score


def test_new_current_flags_are_added_and_obsolete_flags_removed():
    snap = survey(intro(), page(1, question(kind="rating", options=(), scale=scale(13, "Bad", "Good"))))
    historical = stored_review(snap)
    historical["findings"] = [old_flag("9.2")]
    projected = project_review(snap.model_dump(mode="json"), historical)
    assert any(f["criterion_id"] == "6.3" for f in projected["findings"])
    assert not any(f["fingerprint"] == "old-9.2" for f in projected["findings"])


def test_historical_ai_evidence_and_status_survive_without_invented_credit():
    snap = validated_scale()
    historical = stored_review(snap)
    ai_flag = old_flag("6.3", "ai")
    historical["findings"].append(ai_flag)
    historical["ai"] = {"model": "historical", "checked": ["story"],
                        "failed": {"wording": "Unavailable"}, "dropped": ["Unquoted"], "merged": []}
    historical["checked_criteria"] += ["5.1", "B1"]
    projected = project_review(snap.model_dump(mode="json"), historical)
    retained = Finding.model_validate(ai_flag)
    assert retained.model_dump(mode="json") | {"fingerprint": ai_flag["fingerprint"]} in projected["findings"]
    assert projected["ai"] == historical["ai"]
    assert "5.1" not in projected["checked_criteria"]
    assert "B1" not in projected["checked_criteria"]
    assert "6.3" not in projected["checked_criteria"]
    assert projected["results"]["6.3"]["fraction"] is None
    assert projected["scorecard"]["provisional"]
    assert projected["scorecard"]["readiness"] != "ready"
    assert projected["projection"]["ai_score_reconstructed"] is False
    assert projected["projection"]["score_limitations"]


def test_ai_blocker_kept_and_historical_pending_not_falsely_cleared():
    snap = validated_scale()
    historical = stored_review(snap)
    historical["findings"].append(old_flag("B1", "ai"))
    historical["scorecard"]["kept_blockers"] = ["B1"]
    projected = project_review(snap.model_dump(mode="json"), historical)
    assert "B1" in projected["scorecard"]["kept_blockers"]
    assert "B1" in projected["scorecard"]["pending_blockers"]
    assert "B1" not in projected["checked_criteria"]


def test_invitation_opening_obsolete_b4_removed_after_role_fix():
    snap = survey(page(0, kind="info", text="We invite you to share your feedback on our products. This takes 5 minutes."),
                  page(1, question()))
    historical = stored_review(snap)
    historical["findings"].append(old_flag("B4"))
    projected = project_review(snap.model_dump(mode="json"), historical)
    assert not any(f["criterion_id"] == "B4" for f in projected["findings"])
    assert "B4" not in projected["scorecard"]["open_blockers"]


@pytest.mark.parametrize("with_results", [False, True])
def test_projection_collapses_historical_ai_duplicate_of_current_code(with_results):
    prompt = question(kind="multi_choice", options=("Vanilla", "None of these"))
    prompt.options[-1].is_exclusive = False
    snap = survey(intro(), page(1, prompt), thank_you())
    current = run_review(snap)
    code_flag = next(f for f in current.findings if f.criterion_id == "4.1")
    ai_flag = code_flag.model_copy(update={"source": "ai"})
    historical = current.model_dump(mode="json") if with_results else stored_review(snap)
    historical["findings"].append(ai_flag.model_dump(mode="json") | {"fingerprint": "historical-ai-duplicate"})
    if with_results:
        historical["results"]["4.1"]["findings"].append(ai_flag.model_dump(mode="json"))
    before = deepcopy(historical)

    projected = project_review(snap.model_dump(mode="json"), historical)

    displayed = [f for f in projected["findings"] if f["criterion_id"] == "4.1"]
    assert displayed == [code_flag.model_dump(mode="json") | {"fingerprint": code_flag.fingerprint}]
    assert len(projected["results"]["4.1"]["findings"]) == 1
    assert len({f["fingerprint"] for f in projected["findings"]}) == len(projected["findings"])
    assert historical == before


def test_projection_preserves_unknown_legacy_findings_in_results_and_display():
    snap = validated_scale()
    historical = stored_review(snap)
    legacy = old_flag("retired-criterion")
    historical["findings"].append(legacy)

    projected = project_review(snap.model_dump(mode="json"), historical)

    result = projected["results"]["retired-criterion"]
    assert result["assessed"] is False
    assert result["fraction"] is None
    displayed = next(f for f in projected["findings"] if f["criterion_id"] == "retired-criterion")
    assert {k: v for k, v in displayed.items() if k != "fingerprint"} == result["findings"][0]
    assert displayed["evidence"] == legacy["evidence"]
    assert displayed["fingerprint"] == legacy["fingerprint"]


def test_repository_list_and_detail_refresh_without_database_writes():
    repo = Repository(":memory:")
    try:
        snap = validated_scale()
        submitted = repo.submit(snap, ai=False)
        historical = stored_review(snap)
        historical["findings"].append(old_flag("6.3"))
        repo.finish(submitted["job_id"], {"review": historical})
        before = list(repo.db.iterdump())
        detail = repo.detail(submitted["id"])
        listing = repo.list_surveys()[0]
        assert not any(f["fingerprint"] == "old-6.3" for f in detail["review"]["findings"])
        assert "score_checked" not in listing   # the score is methodology, not the card
        assert listing["methodology"]["score_checked"] == [round(detail["review"]["scorecard"]["score"]),
                                                           detail["review"]["scorecard"]["checked_points"]]
        assert list(repo.db.iterdump()) == before
    finally:
        repo.close()
