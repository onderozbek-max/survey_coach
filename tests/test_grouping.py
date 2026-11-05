"""Identical findings across a repeated block are one card with one action (brief 6.1, last row).

Grouping is a projection: members keep their own fingerprints, decisions stay per member and durable,
and nothing stored is rewritten.
"""
import pytest
from concept_fixture import concept_survey

from surveycoach.review import run_review
from surveycoach.server.plan import build_plan
from surveycoach.server.repository import Repository


def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "group.db")
    yield repository
    repository.close()


def saved(repo, payload=None):
    snapshot = concept_survey()
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], payload or encoded(snapshot))
    return created["id"]


def group(detail, criterion):
    return next(i for i in detail["overview"]["items"] if i["criterion_id"] == criterion)


def test_the_three_tray_screens_are_one_card_per_problem_with_the_screens_listed(repo):
    detail = repo.detail(saved(repo))
    phone = group(detail, "6.2")
    assert phone["count"] == 3 and len(phone["fingerprints"]) == 3 and len(phone["pages"]) == 3
    assert phone["location"] == "Q4, Q6 and Q8 · Screens 5, 7 and 9"
    assert phone["screens"] == [5, 7, 9]
    select_all = group(detail, "3.3")
    assert select_all["count"] == 3 and select_all["location"] == "Q4, Q6 and Q8 · Screens 5, 7 and 9"
    # no repeated cards: one item per group, never one per screen
    ids = [i["id"] for i in detail["overview"]["items"] if i["criterion_id"] in {"6.2", "3.3"}]
    assert len(ids) == 2


def test_a_grouped_you_check_names_every_affected_question_in_its_one_instruction(repo):
    phone = group(repo.detail(saved(repo)), "6.2")
    assert phone["instruction"] == "Scroll Q4, Q6 and Q8 on your phone: are all 10 answers easy to reach?"


def test_a_single_finding_keeps_its_own_label_and_has_no_group_instruction(repo):
    detail = repo.detail(saved(repo))
    single = next(i for i in detail["overview"]["items"] if i["kind"] == "finding" and i["count"] == 1)
    assert single["location"].count("·") == 1 and "instruction" not in single


def test_per_screen_markers_stay_on_every_affected_screen(repo):
    detail = repo.detail(saved(repo))
    marked = {s["screen"]: s["state"] for s in detail["overview"]["energy"]["screens"]}
    assert all(marked[n] is not None for n in (5, 7, 9))     # each tray screen still carries its marker


def finding(fp, question, headline="10 answer choices; review the phone layout", **extra):
    base = {"fingerprint": fp, "criterion_id": "6.2", "severity": "worth_improving", "question_id": question,
            "headline": headline, "explanation": "Details.", "member_impact": "Impact.",
            "action_kind": "you_check", "you_check": f"Scroll {question.upper()} on your phone: are all 10 answers easy to reach?"}
    return base | extra


SCREENS = [{"page_id": f"p{n}", "screen": n, "questions": [{"id": f"q{n}", "label": f"Q{n}"}]} for n in range(1, 5)]


def groups(findings):
    plan = build_plan(findings, {}, {"6.2": 10}, SCREENS)
    return [item["fingerprints"] for item in plan["quick_wins"]]


def test_the_question_label_in_a_you_check_does_not_split_a_group():
    assert groups([finding("a", "q1"), finding("b", "q2"), finding("c", "q3")]) == [["a", "b", "c"]]


def test_a_custom_question_label_in_a_you_check_does_not_split_a_group():
    """RedJade questions can carry their own label ("Research B"); it is masked like Q4, not read as a different action."""
    labelled = [{"page_id": f"p{n}", "screen": n, "questions": [{"id": f"q{n}", "label": label}]}
                for n, label in enumerate(("Q1", "Research B", "Q3"), 1)]
    custom = [finding("a", "q1"), finding("b", "q2", you_check="Scroll Research B on your phone: are all 10 answers easy to reach?"),
              finding("c", "q3")]
    plan = build_plan(custom, {}, {"6.2": 10}, labelled)
    assert [item["fingerprints"] for item in plan["quick_wins"]] == [["a", "b", "c"]]


def test_different_actions_never_share_a_card_even_with_the_same_headline():
    paste = lambda text: dict(action_kind="paste", suggested_text=text, you_check=None)
    same = [finding("a", "q1", **paste("One.")), finding("b", "q2", **paste("One."))]
    other = [finding("a", "q1", **paste("One.")), finding("b", "q2", **paste("Two."))]
    assert groups(same) == [["a", "b"]]
    assert groups(other) == [["a"], ["b"]]


def test_a_different_headline_never_joins_a_group():
    assert groups([finding("a", "q1"), finding("b", "q2", headline="9 answer choices; review the phone layout")]) \
        == [["a"], ["b"]]


def test_steps_with_different_words_are_different_actions():
    steps = lambda text: dict(action_kind="steps", steps=[text], you_check=None)
    a = [finding("a", "q1", **steps("Rework \"alpha\".")), finding("b", "q2", **steps("Rework \"beta\"."))]
    assert groups(a) == [["a"], ["b"]]


# --- durable decisions ---------------------------------------------------------------------------

def test_handling_a_grouped_card_is_recorded_per_member_and_survives_a_reload(repo, tmp_path):
    survey_id = saved(repo)
    phone = group(repo.detail(survey_id), "6.2")
    for fingerprint in phone["fingerprints"][:2]:
        repo.save_decision(survey_id, 1, fingerprint, {"action": "keep", "reason": "Checked on my phone"})
    assert group(repo.detail(survey_id), "6.2")["open"] is True            # two of three: still open
    repo.save_decision(survey_id, 1, phone["fingerprints"][2], {"action": "keep", "reason": "Checked on my phone"})
    reopened = Repository(tmp_path / "group.db")
    try:
        after = reopened.detail(survey_id)
        item = group(after, "6.2")
        assert item["decided"] is True and item["open"] is False
        assert set(item["fingerprints"]) <= set(after["decisions"])
        assert after["overview"]["verdict"]["progress"]["done"] == 1        # one card done, not three
    finally:
        reopened.close()


def test_decisions_made_before_the_copy_changed_still_close_the_same_findings(repo):
    """A review saved by the old code (old headline, no action fields) with decisions on it: the
    fingerprint never depended on copy, so the decisions apply to the regrouped item unchanged."""
    snapshot = concept_survey()
    payload = encoded(snapshot)
    for stored in [*payload["review"]["findings"],
                   *[f for r in payload["review"]["results"].values() for f in r["findings"]]]:
        for key in ("action_kind", "steps", "you_check", "field_location"):
            stored.pop(key, None)
        if stored["criterion_id"] == "6.2":
            stored["member_impact"] = "Long or crowded answers are hard to read and tap on a phone."
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], payload)
    fingerprints = [f["fingerprint"] for f in payload["review"]["findings"] if f["criterion_id"] == "6.2"]
    for fingerprint in fingerprints:
        repo.save_decision(created["id"], 1, fingerprint, {"action": "original"})
    before = repo.db.execute("SELECT data FROM reviews").fetchone()["data"]
    detail = repo.detail(created["id"])
    item = group(detail, "6.2")
    assert sorted(item["fingerprints"]) == sorted(fingerprints) and item["decided"] is True
    assert repo.db.execute("SELECT data FROM reviews").fetchone()["data"] == before     # history never rewritten
