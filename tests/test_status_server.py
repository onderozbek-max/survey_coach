"""The status model end to end: decisions, payload shape, methodology split, home card, share."""
import re

import pytest
from fastapi.testclient import TestClient

from builders import intro, page, question, survey, thank_you
from concept_fixture import concept_survey
from surveycoach.review import run_review
from surveycoach.server import create_app
from surveycoach.server.report import stakeholder_packet, summary_packet
from surveycoach.server.repository import Repository

PRIMARY_FORBIDDEN = {"score", "provisional", "coverage_percent", "score_checked", "scorecard", "readiness"}


def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "status.db")
    yield repository
    repository.close()


def saved(repo, snapshot=None, survey_type=None):
    snapshot = snapshot or concept_survey()
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], encoded(snapshot))
    if survey_type:
        repo.update(created["id"], survey_type=survey_type)
    return created["id"]


def keys(value, path=()):
    """Every dict key with the path to it, so a forbidden key can be located."""
    if isinstance(value, dict):
        for key, inner in value.items():
            yield path + (key,), key
            yield from keys(inner, path + (key,))
    elif isinstance(value, list):
        for inner in value:
            yield from keys(inner, path)


def test_detail_carries_one_verdict_in_overview_and_presentation(repo):
    detail = repo.detail(saved(repo))
    verdict = detail["overview"]["verdict"]
    assert detail["presentation"]["verdict"] == verdict
    assert verdict["kind"] in {"fix_before_launch", "almost_ready", "ready_for_signoff"}
    assert detail["overview"]["headline"] == verdict["headline"]
    assert len(detail["overview"]["you_check"]) == 6
    assert verdict["story"].startswith("Members get a welcome")


def test_the_primary_payload_has_no_score_provisional_or_coverage_percent(repo):
    survey_id = saved(repo)
    detail = repo.detail(survey_id)
    for part in ("overview", "presentation"):
        offenders = [path for path, key in keys(detail[part]) if key in PRIMARY_FORBIDDEN and "methodology" not in path]
        assert offenders == [], (part, offenders)
    item = next(s for s in repo.list_surveys() if s["id"] == survey_id)
    offenders = [path for path, key in keys(item) if key in PRIMARY_FORBIDDEN and "methodology" not in path]
    assert offenders == []


def test_score_and_coverage_live_under_methodology_so_the_dialogs_still_work(repo):
    survey_id = saved(repo)
    detail = repo.detail(survey_id)
    quality = detail["methodology"]["quality"]
    assert {"score", "provisional", "coverage_percent", "dimensions"} <= set(quality)
    assert "quality" not in detail
    item = next(s for s in repo.list_surveys() if s["id"] == survey_id)
    assert item["methodology"]["quality"]["score"] == quality["score"]


def test_not_checked_automatically_is_a_methodology_list_not_a_state(repo):
    detail = repo.detail(saved(repo))
    listed = detail["methodology"]["not_checked_automatically"]
    assert listed and all({"id", "title"} <= set(entry) for entry in listed)
    assert "not_checked_automatically" not in detail["overview"]
    states = {s["state"] for s in detail["overview"]["signals"]}
    assert states <= {None, "fix_before_launch", "worth_improving", "you_check", "looks_good"}


def test_you_check_items_are_closed_through_the_existing_decisions_api(repo):
    survey_id = saved(repo)
    before = repo.detail(survey_id)
    fingerprint = before["overview"]["you_check"][0]["fingerprint"]
    assert fingerprint.startswith("you-check:")
    repo.save_decision(survey_id, 1, fingerprint, {"action": "original"})
    after = repo.detail(survey_id)
    assert fingerprint in after["decisions"]
    done = next(i for i in after["overview"]["items"] if i["id"] == fingerprint)
    assert done["open"] is False
    assert after["overview"]["verdict"]["tiles"]["you_check"] == before["overview"]["verdict"]["tiles"]["you_check"] - 1
    kept = after["overview"]["you_check"][1]["fingerprint"]
    repo.save_decision(survey_id, 1, kept, {"action": "keep", "reason": "Checked by phone"})
    assert repo.detail(survey_id)["overview"]["verdict"]["progress"]["done"] == 2


def test_you_check_decisions_reject_what_makes_no_sense(repo):
    survey_id = saved(repo)
    fingerprint = repo.detail(survey_id)["overview"]["you_check"][0]["fingerprint"]
    with pytest.raises(ValueError):
        repo.save_decision(survey_id, 1, fingerprint, {"action": "pick", "picked_text": "invented"})
    with pytest.raises(KeyError):
        repo.save_decision(survey_id, 1, "you-check:images:deadbeef", {"action": "original"})


def test_the_http_decisions_endpoint_accepts_you_check_keys_offline(tmp_path):
    app = create_app(tmp_path / "http.db")
    with TestClient(app, base_url="http://localhost") as client:
        repository = app.state.repository
        snapshot = concept_survey()
        created = repository.submit(snapshot, ai=False)
        repository.finish(created["job_id"], encoded(snapshot))
        detail = client.get(f"/api/surveys/{created['id']}").json()
        fingerprint = detail["overview"]["you_check"][0]["fingerprint"]
        url = f"/api/surveys/{created['id']}/versions/1/decisions/{fingerprint}"
        assert client.put(url, json={"action": "original"}).status_code == 200
        assert client.get(f"/api/surveys/{created['id']}/versions/1/decisions").json()["decisions"][fingerprint]["action"] == "original"
        assert client.put(url, json={"action": "keep"}).status_code == 422


def test_a_decision_follows_its_evidence_a_changed_survey_gets_a_new_item(repo):
    survey_id = saved(repo)
    fingerprint = repo.detail(survey_id)["overview"]["you_check"][0]["fingerprint"]
    repo.save_decision(survey_id, 1, fingerprint, {"action": "original"})
    changed = concept_survey().model_copy(deep=True)
    changed.pages[-1].media = []
    again = repo.submit(changed, ai=False, survey_id=survey_id)
    repo.finish(again["job_id"], encoded(changed))
    v2 = repo.detail(survey_id, 2)
    assert fingerprint not in [c["fingerprint"] for c in v2["overview"]["you_check"]]


def test_every_finding_in_the_payload_has_one_action_kind(repo):
    detail = repo.detail(saved(repo))
    findings = detail["review"]["findings"]
    assert findings and all(f["action_kind"] in {"paste", "steps", "you_check"} for f in findings)


def test_the_effective_survey_type_target_drives_time(repo):
    survey_id = saved(repo, concept_survey("non_ihut_product"))
    default = repo.detail(survey_id)["overview"]["verdict"]["time"]
    assert default["type_source"] in {"detected", "default"}
    repo.update(survey_id, survey_type="services_concept")
    confirmed = repo.detail(survey_id)["overview"]["verdict"]["time"]
    assert confirmed["type_source"] == "confirmed" and confirmed["target_high"] == 10.0


def test_home_card_item_leads_with_the_verdict_not_the_score(repo):
    survey_id = saved(repo)
    item = next(s for s in repo.list_surveys() if s["id"] == survey_id)
    assert item["verdict"]["kind"] == "almost_ready" and item["tiles"] == item["verdict"]["tiles"]
    assert item["ready_to_share"] is False
    assert all(s["state"] in {None, "fix_before_launch", "worth_improving", "you_check", "looks_good"}
               for s in item["signals"])


def test_ready_to_share_needs_the_ready_verdict_and_a_finished_job(repo):
    snapshot = survey(intro("Welcome! Thanks for helping us."), page(1, question(required=True)),
                      thank_you())
    survey_id = saved(repo, snapshot)
    item = next(s for s in repo.list_surveys() if s["id"] == survey_id)
    detail = repo.detail(survey_id)
    ready = detail["overview"]["verdict"]["kind"] == "ready_for_signoff"
    assert item["ready_to_share"] is ready


def strip_details(html):
    return re.sub(r"<details.*?</details>", "", html, flags=re.S)


@pytest.mark.parametrize("packet", [lambda d: summary_packet(d), lambda d: stakeholder_packet(d)])
def test_share_leads_with_the_verdict_and_hides_the_score_in_methodology(repo, packet):
    html = packet(repo.detail(saved(repo)))
    visible = strip_details(html)
    for banned in ("Provisional", "% coverage", "/100", "Survey Quality", "Room to improve", "Needs attention"):
        assert banned not in visible, banned
    assert "Almost ready" in visible or "to fix before launch" in visible or "Ready for sign-off" in visible
    assert "<details" in html and ("Provisional" in html or "Assessed" in html)   # still there for experts


def test_a_pending_survey_has_no_verdict_and_home_still_loads(repo):
    created = repo.submit(concept_survey(), ai=False)   # no review yet
    detail = repo.detail(created["id"])
    assert "overview" not in detail and detail["presentation"]["verdict"] is None
    assert detail["methodology"]["not_checked_automatically"] == []
    card = next(s for s in repo.list_surveys() if s["id"] == created["id"])
    assert card["verdict"] is None and card["tiles"] is None and card["ready_to_share"] is False
    assert card["signals"] == []


def test_a_legacy_saved_review_without_action_fields_still_loads_and_gets_them(repo):
    snapshot = survey(intro(), page(1, question()), thank_you())
    payload = encoded(snapshot)
    stripped = [*payload["review"]["findings"],
                *[f for r in payload["review"]["results"].values() for f in r["findings"]]]
    for finding in stripped:                     # exactly what an old save looks like: no action fields yet
        for key in ("action_kind", "steps", "you_check", "field_location"):
            finding.pop(key, None)
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], payload)
    detail = repo.detail(created["id"])
    assert all(f["action_kind"] in {"paste", "steps", "you_check"} for f in detail["review"]["findings"])
    stored = repo.db.execute("SELECT data FROM reviews").fetchone()["data"]
    assert "action_kind" not in stored          # the stored evidence is never decorated


def test_the_decisions_api_and_the_overview_apply_one_rule_to_absorbed_findings():
    """Both feed from extra_items, so an absorbed length finding never stands in for the item."""
    from surveycoach.server.extras import extras_for
    from test_signals import finding, long_survey
    snapshot = long_survey()
    review = {"results": {}, "findings": [finding("len", "2.1", "worth_improving", absorbed_by="root")]}
    data = {"snapshot": snapshot.model_dump(mode="json"), "review": review, "survey_type": "community_pulse"}
    assert [e["kind"] for e in extras_for(data)] == ["time"]
    review["findings"][0].pop("absorbed_by")
    assert extras_for(data) == []            # a visible length finding already explains it
