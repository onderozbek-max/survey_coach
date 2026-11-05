"""One read-time contract for workspace, offline demo and worked example."""
from copy import deepcopy
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from builders import intro, page, question, survey, thank_you
from surveycoach.demo_export import build_demo_data
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.server import create_app
from surveycoach.server.example import run_example
from surveycoach.server.repository import Repository


def assert_contract(data):
    assert data["screens"]
    assert set(data["plan"]["counts"]) == {"must_fix", "quick_wins", "more", "open_must_fix"}
    assert data["overview"]["headline"]
    assert len(data["overview"]["signals"]) == 6
    assert all("also_covers" in f for f in data["review"]["findings"])
    visible = {f["fingerprint"] for f in data["review"]["findings"] if not f.get("absorbed_by")}
    planned = {fp for tier in ("must_fix", "quick_wins", "more")
               for item in data["plan"][tier] for fp in item["fingerprints"]}
    assert planned == visible


def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint}
                          for f in result.findings]
    return {"review": review}


def test_sample_api_and_demo_share_contract_without_enriching_stored_evidence(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/samples/boxer-briefs", json={}).json()
        repo = app.state.repository
        before = list(repo.db.iterdump())
        data = client.get(f"/api/surveys/{created['id']}").json()
        assert_contract(data)
        assert client.get(f"/api/surveys/{created['id']}").json() == data
        assert not data["change_sheet"]  # Never copy a suggestion before a choice.
        assert list(repo.db.iterdump()) == before
    for data in build_demo_data()["surveys"]:
        assert_contract(data)
        assert data["review"]["results"]  # Assessed evidence, not inferred strengths.


def test_enrich_is_detached_repeatable_and_uses_effective_type():
    from surveycoach.server.present import enrich

    snap = survey(page(1, text="word " * 2695))
    data = {"snapshot": snap.model_dump(mode="json"), "survey_type": "community_pulse",
            **encoded(snap), "decisions": {}}
    before = deepcopy(data)
    first = enrich(data, load_rubric())
    assert_contract(first)
    assert data == before
    assert enrich(first, load_rubric()) == first
    assert first["review"]["results"] == data["review"]["results"]
    assert first["review"]["scorecard"] == data["review"]["scorecard"]
    assert "Community surveys aim for 5 minutes" in first["overview"]["signals"][0]["summary"]
    first["snapshot"]["pages"].clear()
    first["review"]["results"].clear()
    assert data == before


def test_pending_payload_gets_screens_but_no_invented_review():
    from surveycoach.server.present import enrich

    data = {"snapshot": survey(page(1, question())).model_dump(mode="json"), "review": None}
    before = deepcopy(data)
    projected = enrich(data, load_rubric())
    assert projected["screens"]
    assert "plan" not in projected and "overview" not in projected
    assert data == before


def test_example_returns_enriched_payload_but_persists_only_raw_evidence(tmp_path):
    from surveycoach.server.example import ROOT
    from surveycoach.snapshot import SurveySnapshot

    repo = Repository(tmp_path / "example.db")
    try:
        snap = SurveySnapshot.model_validate_json((ROOT / "fixtures/boxer-briefs.json").read_text())
        created = repo.submit(snap, ai=False)
        data = run_example(repo, created["job_id"])
        assert_contract(data)
        stored = repo._latest_review(repo.db, created["id"], 1)
        assert not {"screens", "plan", "overview"} & stored.keys()
        assert all("also_covers" not in f for f in stored["review"]["findings"])
        assert stored["review"]["results"]
        assert_contract(repo.detail(created["id"]))
    finally:
        repo.close()


def test_presentation_precedes_comparison_and_sheet_and_curation_follows_carry(tmp_path):
    repo = Repository(tmp_path / "rounds.db")
    try:
        snap = survey(intro(), page(1, question()), thank_you())
        payload = encoded(snap)
        # Retained historical AI evidence: same scope, different roots, absorbable family.
        for cid, severity, fp in [("B1", "must_fix", "root"),
                                  ("5.1", "worth_improving", "child")]:
            payload["review"]["findings"].append({
                "criterion_id": cid, "severity": severity, "fingerprint": fp,
                "headline": fp, "evidence": snap.pages[1].questions[0].text,
                "explanation": "Make it clear. Also covers 5.1.",
                "member_impact": "Clearer", "source": "ai", "page_id": "p1", "question_id": "q1"})
        first = repo.submit(snap, ai=False)
        repo.finish(first["job_id"], payload)
        for fp in ("root", "child"):
            repo.save_decision(first["id"], 1, fp, {"action": "keep", "reason": "Tracker"})
        second = repo.submit(snap.model_copy(update={"title": "Round two"}),
                             ai=False, survey_id=first["id"])
        repo.finish(second["job_id"], payload)
        before = list(repo.db.iterdump())
        data = repo.detail(first["id"])
        assert_contract(data)
        child = next(f for f in data["review"]["findings"] if f["fingerprint"] == "child")
        assert child["absorbed_by"] == "root"
        entry = next(e for e in data["round_changes"]["still"]
                     if e["current_finding"]["fingerprint"] == "child")
        assert entry["prior_finding"]["absorbed_by"] == "root"
        assert entry["current_finding"]["absorbed_by"] == "root"
        assert "child" not in {line["fingerprint"] for line in data["change_sheet"]}
        assert data["carried"]["root"]["reason"] == "Tracker"
        assert data["plan"]["counts"]["open_must_fix"] == 0
        assert data["overview"]["headline"] == (
            "All 1 must-fix decisions handled; chosen changes and kept risks are not verified fixes.")
        assert all("Also covers" not in line["instructions"] for line in data["change_sheet"])
        assert data == repo.detail(first["id"])
        assert list(repo.db.iterdump()) == before
        # A current explicit reopen wins over carry-over in both curated projections.
        repo.save_decision(first["id"], 2, "root", {"action": "open"})
        reopened = repo.detail(first["id"])
        assert reopened["plan"]["counts"]["open_must_fix"] == 1
        assert reopened["overview"]["headline"].startswith("1 must-fix")
        # A keep without a reason is not a completed plan choice.
        repo.save_decision(first["id"], 2, "root", {"action": "keep", "reason": " "})
        assert repo.detail(first["id"])["plan"]["counts"]["open_must_fix"] == 1
    finally:
        repo.close()


def test_scope_counts_assessed_checks_not_points_or_findings_without_mutation():
    from surveycoach.server.rounds import scope
    data = {'review': {'checked_criteria': ['4.1', '4.1', 'B1'],
                       'unchecked': ['Unchecked wording'],
                       'results': {'4.1': {'applies': True, 'assessed': True, 'fraction': 0},
                                   'B1': {'applies': True, 'assessed': True, 'fraction': None},
                                   '4.2': {'applies': True, 'assessed': False, 'fraction': None},
                                   '4.3': {'applies': False, 'assessed': True, 'fraction': 1}}}}
    # All other rubric checks are explicitly non-applicable in this tiny case.
    rubric = load_rubric()
    for check in [*(c for c in rubric.criteria if c.active), *rubric.blockers]:
        data['review']['results'].setdefault(check.id, {'applies': False, 'assessed': True})
    before = deepcopy(data)
    actual = scope(data)
    assert actual['checked_count'] == 2  # Failed assessed checks still count as checked.
    assert actual['total_count'] == 3  # Non-applicable checks are not unchecked checks.
    assert actual['unchecked_checks'] == ['Unchecked wording', load_rubric().criterion('4.2').title]
    assert data == before
    assert scope({})['checked_count'] is None
    assert scope({})['total_count'] is None


def test_scope_available_for_offline_demo_and_enriched_payloads():
    for detail in build_demo_data()['surveys']:
        scope = detail['presentation']['scope']
        results = detail['review']['results']
        applicable = [r for r in results.values() if r['applies']]
        checked = [r for r in applicable if r['assessed'] and
                   (r['fraction'] is not None or r['criterion_id'].startswith('B'))]
        assert scope['checked_count'] == len(checked)
        rubric = load_rubric()
        active_count = sum(c.active for c in rubric.criteria) + len(rubric.blockers)
        assert scope['total_count'] == active_count - sum(not r['applies'] for r in results.values())
        assert set(detail['review']['unchecked']) <= set(scope['unchecked_checks'])
        for blocker in rubric.blockers:
            result = results.get(blocker.id)
            if result is None or (result['applies'] and not result['assessed']):
                assert blocker.title in scope['unchecked_checks']


def missing_wording_detail(mode):
    """Real review pipeline; the only provider is an in-memory synthetic stub."""
    from surveycoach.llm import FakeProvider, LlmError
    from surveycoach.snapshot import SurveySnapshot
    from tests.test_ai_review import batch_of, verdicts

    def answer(system, data):
        batch = batch_of(system)
        if batch.id == 'wording':
            raise LlmError('Synthetic wording batch failure')
        return verdicts(batch)

    snapshot = SurveySnapshot.model_validate_json(
        (Path(__file__).parent.parent / 'fixtures/boxer-briefs.json').read_text())
    provider = FakeProvider({'BatchOutput': answer}) if mode == 'wording_failure' else None
    review = run_review(snapshot, provider=provider)
    return {'snapshot': snapshot.model_dump(mode='json'), 'review': review.model_dump(mode='json')}


@pytest.mark.parametrize('mode,checked', [('disabled', 21), ('wording_failure', 33)])
@pytest.mark.parametrize('projected', [False, True])
def test_scope_keeps_absent_ai_blockers_without_inventing_assessments(mode, checked, projected):
    from surveycoach.server.rounds import project_review, scope

    detail = missing_wording_detail(mode)
    before = deepcopy(detail)
    if projected:
        detail = dict(detail, review=project_review(detail['snapshot'], detail['review']))
    actual = scope(detail)
    # Rubric v2 has 43 active criteria + 7 blockers; this fixture has 2 explicit N/A.
    assert actual['total_count'] == 48
    assert actual['checked_count'] == checked
    # Reader-only image failure stays pending, never a completed launch check.
    assert not detail['review']['results']['B7']['assessed']
    assert 'B7' in detail['review']['scorecard']['pending_blockers']
    assert next(b.title for b in load_rubric().blockers if b.id == 'B7') in actual['unchecked_checks']
    for cid, title in [('B1', 'Leading question on the main research topic'),
                       ('B6', 'Asks for personal details it does not need')]:
        assert cid not in detail['review']['results']  # Missing, not fabricated passes.
        assert title in actual['unchecked_checks']
        assert cid not in detail['review'].get('checked_criteria', [])
    assert detail['review']['scorecard'] == before['review']['scorecard']
    assert scope(before) == actual
    if mode == 'wording_failure':
        assert detail['review']['ai']['checked'] == ['story', 'flow']
        assert set(detail['review']['ai']['failed']) == {'wording'}
