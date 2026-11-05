"""The one ordered list behind 'N of M done', the fix list and 'Next item' (workstream 2A)."""
import pytest

from builders import page, question, survey
from concept_fixture import concept_survey
from surveycoach.demo_export import build_demo_data
from surveycoach.fix_queue import build_queue
from surveycoach.review import run_review
from surveycoach.server.repository import Repository
from surveycoach.status import FIX_BEFORE_LAUNCH, IMPROVE, STATES, YOU_CHECK
from test_signals import finding, overview

OPEN_STATES = (FIX_BEFORE_LAUNCH, IMPROVE, YOU_CHECK)
ENTRY_KEYS = {"id", "fingerprints", "kind", "state", "open", "handled_kind", "unverified", "keep_reason",
              "screen", "page_id", "screens", "pages", "title", "location", "action_kind", "has_paste",
              "count", "next_open_id"}


def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "queue.db")
    yield repository
    repository.close()


def saved(repo):
    snapshot = concept_survey()
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], encoded(snapshot))
    return created["id"]


def queue_of(repo, survey_id):
    return repo.detail(survey_id)["queue"]


def entry(queue, **match):
    return next(e for e in queue["items"] if all(e[k] == v for k, v in match.items()))


# --- shape and order -------------------------------------------------------------------------

def test_every_entry_has_the_documented_fields(repo):
    queue = queue_of(repo, saved(repo))
    assert queue["items"] and all(set(e) == ENTRY_KEYS for e in queue["items"])
    assert set(queue["counts"]) == {"done", "total", "open", "unverified", "by_kind"}
    assert queue["first_open_id"] == queue["items"][0]["id"]


def test_open_states_come_in_order_and_screens_keep_their_order_within_a_state(repo):
    items = queue_of(repo, saved(repo))["items"]
    states = [STATES.index(e["state"]) for e in items]
    assert states == sorted(states)
    for state in OPEN_STATES:
        screens = [e["screen"] for e in items if e["state"] == state and e["screen"] is not None]
        assert screens == sorted(screens)


def test_whole_survey_items_sit_after_screen_items_of_the_same_state():
    items = [{"id": "w", "state": YOU_CHECK, "screens": [], "open": True},
             {"id": "s9", "state": YOU_CHECK, "screens": [9], "open": True},
             {"id": "s2", "state": YOU_CHECK, "screens": [2], "open": True},
             {"id": "f", "state": FIX_BEFORE_LAUNCH, "screens": [7], "open": True}]
    assert [e["id"] for e in build_queue(items)["items"]] == ["f", "s2", "s9", "w"]


def test_equal_state_and_screen_keep_the_plan_order():
    items = [{"id": name, "state": IMPROVE, "screens": [3], "open": True} for name in "cab"]
    assert [e["id"] for e in build_queue(items)["items"]] == list("cab")


def test_a_grouped_card_is_one_entry_listing_every_screen(repo):
    items = queue_of(repo, saved(repo))["items"]
    phone = [e for e in items if e["count"] == 3 and e["screens"] == [5, 7, 9]]
    assert phone and all(e["screen"] == 5 and e["page_id"] == e["pages"][0] for e in phone)
    assert len({e["id"] for e in items}) == len(items)


def test_action_kind_and_pasteability_are_per_entry(repo):
    items = queue_of(repo, saved(repo))["items"]
    assert {e["action_kind"] for e in items} <= {"paste", "steps", "you_check"}
    assert all(e["action_kind"] == "you_check" for e in items if e["kind"] in {"you_check", "time"})
    assert any(e["has_paste"] for e in items) and not any(e["has_paste"] for e in items if e["action_kind"] == "you_check")


# --- counts come only from the list ----------------------------------------------------------

def check_counts(detail):
    queue, verdict = detail["queue"], detail["overview"]["verdict"]
    entries = queue["items"]
    assert len(entries) == len({e["id"] for e in entries}) == len(detail["overview"]["items"])
    assert queue["counts"]["total"] == len(entries)
    assert queue["counts"]["open"] == sum(e["open"] for e in entries)
    assert queue["counts"]["done"] == queue["counts"]["total"] - queue["counts"]["open"]
    assert sum(queue["counts"]["by_kind"].values()) == queue["counts"]["done"]
    if verdict:      # the verdict tiles and the progress bar are the same list seen two ways
        assert {"done": queue["counts"]["done"], "total": queue["counts"]["total"]} == verdict["progress"]
        tiles = {"fix": FIX_BEFORE_LAUNCH, "improve": IMPROVE, "you_check": YOU_CHECK}
        for tile, state in tiles.items():
            assert verdict["tiles"][tile] == sum(e["open"] and e["state"] == state for e in entries)
    else:
        assert entries == []


def test_n_of_m_done_equals_the_tiles_before_and_after_every_kind_of_decision(repo):
    survey_id = saved(repo)
    check_counts(repo.detail(survey_id))
    first, second, third, fourth = repo.detail(survey_id)["queue"]["items"][:4]
    decisions = [(first, {"action": "done"}), (second, {"action": "keep", "keep_reason": "other"}),
                 (third, {"action": "original"})]
    for item, body in decisions:
        for fingerprint in item["fingerprints"]:
            repo.save_decision(survey_id, 1, fingerprint, body)
        check_counts(repo.detail(survey_id))
    counts = repo.detail(survey_id)["queue"]["counts"]
    assert counts["done"] == 3 and counts["by_kind"] == {"use": 0, "done": 2, "keep": 1}
    assert counts["unverified"] == 2 and fourth["open"] is True


def test_accepting_a_change_counts_as_use(repo):
    survey_id = saved(repo)
    detail = repo.detail(survey_id)
    target = next(f for f in detail["review"]["findings"] if f.get("suggested_text") and not f.get("absorbed_by"))
    group = next(e for e in detail["queue"]["items"] if target["fingerprint"] in e["fingerprints"])
    for fingerprint in group["fingerprints"]:
        member = next(f for f in detail["review"]["findings"] if f["fingerprint"] == fingerprint)
        text = member.get("suggested_text") or member["options"][0]["text"]
        repo.save_decision(survey_id, 1, fingerprint, {"action": "pick", "picked_text": text})
    after = repo.detail(survey_id)
    assert entry(after["queue"], id=group["id"])["handled_kind"] == "use"
    assert entry(after["queue"], id=group["id"])["unverified"] is False
    check_counts(after)


def test_a_grouped_card_is_done_only_when_every_member_is_handled(repo):
    survey_id = saved(repo)
    group = next(e for e in queue_of(repo, survey_id)["items"] if e["count"] == 3)
    for fingerprint in group["fingerprints"][:2]:
        repo.save_decision(survey_id, 1, fingerprint, {"action": "done"})
    assert entry(queue_of(repo, survey_id), id=group["id"])["open"] is True
    repo.save_decision(survey_id, 1, group["fingerprints"][2], {"action": "done"})
    after = entry(queue_of(repo, survey_id), id=group["id"])
    assert after["open"] is False and after["handled_kind"] == "done" and after["unverified"] is True


def test_mixed_decisions_on_one_card_report_the_weakest_evidence(repo):
    survey_id = saved(repo)
    group = next(e for e in queue_of(repo, survey_id)["items"] if e["count"] == 3)
    bodies = [{"action": "keep", "keep_reason": "intentional"}, {"action": "original"}, {"action": "keep", "reason": "ok"}]
    for fingerprint, body in zip(group["fingerprints"], bodies):
        repo.save_decision(survey_id, 1, fingerprint, body)
    done = entry(queue_of(repo, survey_id), id=group["id"])
    assert done["handled_kind"] == "done" and done["unverified"] is True and done["keep_reason"] == "intentional"


def test_a_kept_item_reports_its_reason_chip_and_is_never_unverified(repo):
    survey_id = saved(repo)
    item = queue_of(repo, survey_id)["items"][0]
    for fingerprint in item["fingerprints"]:
        repo.save_decision(survey_id, 1, fingerprint, {"action": "keep", "keep_reason": "owner_decided"})
    kept = entry(queue_of(repo, survey_id), id=item["id"])
    assert (kept["handled_kind"], kept["keep_reason"], kept["unverified"]) == ("keep", "owner_decided", False)


def test_a_review_with_nothing_to_say_has_an_empty_queue(repo):
    snapshot = survey(page(1, question()))
    created = repo.submit(snapshot, ai=False)       # no review yet
    queue = repo.detail(created["id"])["queue"]
    assert queue["items"] == [] and queue["counts"]["total"] == 0 and queue["first_open_id"] is None


def test_the_property_holds_for_the_offline_demo_surveys():
    surveys = build_demo_data()["surveys"]
    assert surveys
    for survey_detail in surveys:
        check_counts(survey_detail)


# --- next item -------------------------------------------------------------------------------

def test_next_open_id_is_the_next_open_entry_and_wraps_nowhere(repo):
    survey_id = saved(repo)
    items = queue_of(repo, survey_id)["items"]
    for item in items[1:3]:      # handle the 2nd and 3rd
        for fingerprint in item["fingerprints"]:
            repo.save_decision(survey_id, 1, fingerprint, {"action": "done"})
    after = queue_of(repo, survey_id)["items"]
    assert after[0]["next_open_id"] == after[3]["id"]            # skips the two handled
    assert after[1]["next_open_id"] == after[3]["id"]            # a handled item still points forward
    assert after[-1]["next_open_id"] is None
    open_ids = [e["id"] for e in after if e["open"]]
    assert all(e["next_open_id"] in open_ids + [None] for e in after)


def test_next_open_id_is_none_when_nothing_after_is_open():
    items = [{"id": "a", "state": IMPROVE, "screens": [1], "open": True},
             {"id": "b", "state": IMPROVE, "screens": [2], "open": False}]
    built = build_queue(items)["items"]
    assert built[0]["next_open_id"] is None and built[1]["next_open_id"] is None


def test_synthetic_overview_items_carry_the_new_fields():
    out = overview(findings=[finding("a", "3.4", "worth_improving", suggested_text="Better.", question_id="q1")],
                   snapshot=survey(page(1, question("q1", required=True))))
    item = out["items"][0]
    assert item["action_kind"] == "paste" and item["has_paste"] is True
    assert item["handled_kind"] is None and item["unverified"] is False and item["page_id"] == item["pages"][0]


def test_the_queue_is_served_over_http_and_follows_a_decision(tmp_path):
    from fastapi.testclient import TestClient
    from surveycoach.server import create_app
    app = create_app(tmp_path / "http.db")
    snapshot = concept_survey()
    created = app.state.repository.submit(snapshot, ai=False)
    app.state.repository.finish(created["job_id"], encoded(snapshot))
    with TestClient(app, base_url="http://localhost") as client:
        first = client.get(f"/api/surveys/{created['id']}").json()["queue"]
        target = first["items"][0]
        for fingerprint in target["fingerprints"]:
            url = f"/api/surveys/{created['id']}/versions/1/decisions/{fingerprint}"
            assert client.put(url, json={"action": "done"}).status_code == 200
        after = client.get(f"/api/surveys/{created['id']}/versions/1").json()["queue"]
    assert after["counts"]["done"] == first["counts"]["done"] + 1
    assert after["first_open_id"] == first["items"][1]["id"]


def test_done_and_keep_close_items_exactly_like_use_so_the_verdict_can_be_ready_but_flags_unverified(repo):
    survey_id = saved(repo)
    for index, item in enumerate(queue_of(repo, survey_id)["items"]):
        body = {"action": "done"} if index % 2 else {"action": "keep", "keep_reason": "intentional"}
        for fingerprint in item["fingerprints"]:
            repo.save_decision(survey_id, 1, fingerprint, body)
    detail = repo.detail(survey_id)
    assert detail["overview"]["verdict"]["kind"] == "ready_for_signoff"
    assert detail["queue"]["counts"]["open"] == 0 and detail["queue"]["first_open_id"] is None
    assert detail["queue"]["counts"]["unverified"] == detail["queue"]["counts"]["by_kind"]["done"] > 0
    check_counts(detail)
