"""'My changes': accepted text changes in RedJade order, plus one server-made 'copy all' text."""
import pytest

from builders import intro, page, question, survey, thank_you
from concept_fixture import concept_survey
from surveycoach.labels import screen_labels
from surveycoach.review import run_review
from surveycoach.server.my_changes import build_my_changes
from surveycoach.server.repository import Repository


def finding(fp, qid=None, page_id=None, current="", **extra):
    base = {"fingerprint": fp, "criterion_id": "1.1", "severity": "worth_improving", "headline": f"Fix {fp}",
            "explanation": "Because.", "current_text": current, "question_id": qid, "page_id": page_id}
    return base | extra


def synthetic():
    q2 = question("q2", "Which flavor do you like best?", help_text="Pick one flavor.",
                  options=("Vanilla", "Chocolate", "Mint"))
    snapshot = survey(intro("Thanks for helping!"), page(1, question("q1", "Do you like it?")), page(2, q2), thank_you())
    return snapshot.model_dump(mode="json"), snapshot


def detail_with(findings, decisions):
    data, snapshot = synthetic()
    return {"snapshot": data, "screens": screen_labels(snapshot), "decisions": decisions,
            "review": {"findings": findings}}


def pick(text):
    return {"action": "pick", "picked_text": text}


SHUFFLED = [   # deliberately not in RedJade order
    finding("a2", "q2", current="Chocolate"),
    finding("hp", "q2", current="Pick one flavor."),
    finding("qt2", "q2", current="Which flavor do you like best?"),
    finding("qt1", "q1", current="Do you like it?"),
    finding("w", page_id="p0", current="Thanks for helping!"),
    finding("a1", "q2", current="Vanilla"),
]
CHOSEN = {fp: pick(f"new {fp}") for fp in ("a2", "hp", "qt2", "qt1", "w", "a1")}


def test_changes_come_in_redjade_order_screen_then_question_then_field():
    mine = build_my_changes(detail_with(SHUFFLED, CHOSEN))
    assert [c["fingerprint"] for c in mine["items"]] == ["w", "qt1", "qt2", "hp", "a1", "a2"]
    assert [c["field"] for c in mine["items"]] == [
        "screen_text", "question_text", "question_text", "help_text", "answer", "answer"]
    assert mine["count"] == 6


def test_each_change_names_where_it_goes_and_what_replaces_what():
    mine = build_my_changes(detail_with(SHUFFLED, CHOSEN))
    help_change = next(c for c in mine["items"] if c["fingerprint"] == "hp")
    assert help_change["before"] == "Pick one flavor." and help_change["after"] == "new hp"
    assert (help_change["screen"], help_change["page_id"], help_change["page_label"]) == (3, "p2", "Q2")
    assert (help_change["question_id"], help_change["question_label"]) == ("q2", "Q2")
    assert help_change["screen_label"] == "Q2 · Screen 3"
    assert help_change["field_location"] == "RedJade > Q2 > Help text"
    welcome = next(c for c in mine["items"] if c["fingerprint"] == "w")
    assert welcome["question_id"] is None and welcome["question_label"] is None and welcome["page_label"] == "Welcome"
    assert welcome["field_location"] == "RedJade > Welcome > Welcome text"


def test_the_finding_may_pin_its_own_field_location():
    pinned = finding("qt1", "q1", current="Do you like it?", field_location="RedJade > Q1 > Question text")
    mine = build_my_changes(detail_with([pinned], {"qt1": pick("Better?")}))
    assert mine["items"][0]["field_location"] == "RedJade > Q1 > Question text"


def test_copy_all_is_made_from_the_same_items_so_it_cannot_diverge():
    mine = build_my_changes(detail_with(SHUFFLED, CHOSEN))
    assert mine["copy_all_text"] == "\n\n".join(c["copy_text"] for c in mine["items"])
    first = mine["items"][0]["copy_text"]
    assert first == "RedJade > Welcome > Welcome text\nBefore: Thanks for helping!\nAfter: new w"
    assert mine["copy_all_text"].count("Before: ") == mine["copy_all_text"].count("After: ") == 6


def test_only_accepted_changes_are_included_never_kept_done_open_or_unchosen():
    decisions = {"qt1": pick("A"), "qt2": {"action": "keep", "reason": "On purpose"},
                 "hp": {"action": "done"}, "w": {"action": "open"}, "a1": {"action": "original"}}
    mine = build_my_changes(detail_with(SHUFFLED, decisions))
    assert [c["fingerprint"] for c in mine["items"]] == ["qt1"]      # "a2" has no decision at all (a preview)
    assert "On purpose" not in mine["copy_all_text"]


def test_absorbed_findings_are_evidence_not_changes():
    absorbed = finding("qt1", "q1", current="Do you like it?", absorbed_by="other")
    assert build_my_changes(detail_with([absorbed], {"qt1": pick("A")}))["items"] == []


def test_adding_an_answer_has_no_before_text_and_sorts_after_the_existing_answers():
    add = finding("add", "q2", current="Which flavor do you like best?", edit_kind="add_answer")
    chosen = {"add": pick("Strawberry"), "a1": pick("Vanilla bean"), "qt2": pick("Which flavor?")}
    mine = build_my_changes(detail_with([add, SHUFFLED[5], SHUFFLED[2]], chosen))
    assert [c["fingerprint"] for c in mine["items"]] == ["qt2", "a1", "add"]
    new = mine["items"][-1]
    assert new["field"] == "new_answer" and new["before"] is None and new["after"] == "Strawberry"
    assert new["copy_text"].splitlines()[1] == "Before: (nothing: this adds a new answer)"


def test_a_finding_that_cannot_be_placed_still_lists_last_with_an_honest_before():
    lost = finding("lost", "gone", current="Old wording")
    mine = build_my_changes(detail_with([lost, SHUFFLED[3]], {"lost": pick("New"), "qt1": pick("A")}))
    assert [c["fingerprint"] for c in mine["items"]] == ["qt1", "lost"]
    assert mine["items"][-1]["before"] is None and mine["items"][-1]["field_location"] == "RedJade > Survey overall"
    assert "Before: (not found in the saved survey)" in mine["items"][-1]["copy_text"]


def test_nothing_accepted_is_an_empty_list_and_empty_text():
    assert build_my_changes(detail_with(SHUFFLED, {})) == {"items": [], "count": 0, "copy_all_text": ""}


# --- end to end through the repository ---------------------------------------------------------

def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "mine.db")
    yield repository
    repository.close()


def test_detail_serves_my_changes_for_accepted_picks_only(repo):
    snapshot = concept_survey()
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], encoded(snapshot))
    detail = repo.detail(created["id"])
    assert detail["my_changes"] == {"items": [], "count": 0, "copy_all_text": ""}
    pickable = [f for f in detail["review"]["findings"] if f.get("suggested_text") and not f.get("absorbed_by")]
    chosen, other = pickable[0], pickable[1:2]
    repo.save_decision(created["id"], 1, chosen["fingerprint"], {"action": "pick", "picked_text": chosen["suggested_text"]})
    for f in other:
        repo.save_decision(created["id"], 1, f["fingerprint"], {"action": "done"})
    mine = repo.detail(created["id"])["my_changes"]
    assert [c["fingerprint"] for c in mine["items"]] == [chosen["fingerprint"]]
    assert chosen["suggested_text"] in mine["copy_all_text"] and mine["items"][0]["field_location"].startswith("RedJade > ")


def test_the_change_sheet_still_lists_what_it_listed(repo):
    snapshot = concept_survey()
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], encoded(snapshot))
    target = next(f for f in repo.detail(created["id"])["review"]["findings"]
                  if f.get("suggested_text") and not f.get("absorbed_by"))
    repo.save_decision(created["id"], 1, target["fingerprint"], {"action": "pick", "picked_text": target["suggested_text"]})
    sheet = repo.detail(created["id"])["change_sheet"]
    assert [line["fingerprint"] for line in sheet] == [target["fingerprint"]]
