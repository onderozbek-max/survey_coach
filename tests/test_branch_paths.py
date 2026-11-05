"""Branch paths: the reader walks one route, so a survey with other routes needs a human look.

A curated You check item, only on evidence (a walked route that is not fully covered, or branching
the snapshot can see), never when the whole survey was walked. It counts toward the six-item budget
and holds back "Ready for sign-off" until it is ticked or kept.
"""
import json

import pytest
from builders import intro, page, question, survey, thank_you
from concept_fixture import concept_survey

from surveycoach.labels import screen_labels
from surveycoach.recommendations import banned_words
from surveycoach.review import run_review
from surveycoach.server.repository import Repository
from surveycoach.timing import estimate
from surveycoach.you_check import MAX_ITEMS, build_you_checks

PARTIAL = {"pages_captured": 5, "full_branching_coverage": False, "paths_verified": False}
FULL = {"pages_captured": 5, "full_branching_coverage": True, "paths_verified": True}


def items(snapshot, coverage=None):
    return build_you_checks(snapshot, screen_labels(snapshot), estimate(snapshot), 10, coverage)


def branch(snapshot, coverage=None):
    return next((i for i in items(snapshot, coverage) if i["id"] == "branch_paths"), None)


def linear():
    return survey(page(1, question("q1", required=True)), page(2, question("q2", required=True)))


def branching():
    return survey(page(1, question("q1", required=True)),
                  page(2, question("q2", "Why not?", required=True, conditional=True)),
                  page(3, question("q3", "And why not that?", required=True, conditional=True)))


# --- when it appears -----------------------------------------------------------------------------

def test_a_walked_route_that_is_not_fully_covered_gets_the_item():
    item = branch(linear(), PARTIAL)
    assert item is not None and item["title"] == "Check the other paths"
    assert item["instruction"].count("?") == 1 and item["signal"] == "energy"


def test_branching_the_snapshot_can_see_gets_the_item_even_without_a_walk_record():
    assert branch(branching()) is not None


def test_negative_control_a_fully_walked_survey_gets_no_such_item():
    assert branch(linear(), FULL) is None
    assert branch(branching(), FULL) is None          # even with conditional questions: every path was walked


def test_negative_control_a_linear_survey_nobody_walked_gets_no_such_item():
    assert branch(linear()) is None                   # an import with no branching and no walk: nothing to claim
    assert "branch_paths" not in [i["id"] for i in items(concept_survey())]


def test_a_screen_out_page_is_a_branch_too():
    snapshot = survey(intro(), page(1, question("q1", required=True)), page(2, kind="screen_out", text="Sorry!"),
                      thank_you())
    assert branch(snapshot) is not None


# --- what it says --------------------------------------------------------------------------------

def test_it_names_the_questions_and_screens_that_only_some_members_see():
    item = branch(branching(), PARTIAL)
    assert "Q2 and Q3" in item["instruction"] and item["questions"] == ["Q2", "Q3"]
    assert item["screens"] == [2, 3] and item["where"] == "Screens 2 and 3"
    assert item["instruction"].startswith("We checked one route.")


def test_it_names_a_screen_out_screen_by_its_number():
    snapshot = survey(intro(), page(1, question("q1", required=True)), page(2, kind="screen_out", text="Sorry!"),
                      thank_you())
    item = branch(snapshot, PARTIAL)
    assert "screen-out screen (screen 3)" in item["instruction"]


def test_with_nothing_to_name_it_still_gives_one_concrete_instruction():
    item = branch(linear(), PARTIAL)
    assert item["instruction"] == ("We checked one route. Run it again on your phone and pick different answers: "
                                   "do you reach any screen we didn't show?")
    assert item["where"] == "Whole survey" and item["pages"] == []


def test_the_copy_is_member_language_with_no_banned_words():
    for snapshot in (linear(), branching()):
        item = branch(snapshot, PARTIAL)
        assert banned_words(" ".join([item["title"], item["instruction"], item["where"]])) == []
        assert len(item["instruction"].split()) <= 40


def test_the_fingerprint_follows_the_evidence():
    first, again = branch(branching(), PARTIAL)["fingerprint"], branch(branching(), PARTIAL)["fingerprint"]
    assert first == again and first.startswith("you-check:branch_paths:")
    more = survey(page(1, question("q1", required=True)),
                  page(2, question("q2", required=True, conditional=True)))
    assert branch(more, PARTIAL)["fingerprint"] != first


# --- the budget ----------------------------------------------------------------------------------

def test_it_counts_toward_the_six_item_budget_and_wins_over_the_timed_run():
    snapshot = concept_survey()
    snapshot.pages[1].questions[0].conditional = True        # branching plus every other theme: seven candidates
    out = items(snapshot, PARTIAL)
    assert len(out) == MAX_ITEMS == 6
    assert "branch_paths" in [i["id"] for i in out] and "timed_run" not in [i["id"] for i in out]


def test_items_stay_in_theme_order_with_branch_paths_after_the_others():
    snapshot = survey(intro("Welcome! This takes 3 minutes."), page(1, question(required=True, conditional=True)))
    assert [i["id"] for i in items(snapshot, PARTIAL)] == ["timed_run", "branch_paths"]


# --- end to end: the verdict ---------------------------------------------------------------------

def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "branch.db")
    yield repository
    repository.close()


def clean_survey():
    """Reviews clean: welcome with time and reward, required questions, a thank-you."""
    return survey(intro("Welcome! This takes about 1 minute and you earn points."),
                  page(1, question("q1", "Which flavor do you like best?", required=True)),
                  page(2, question("q2", "Which size do you prefer?", options=("Small", "Large"), required=True)),
                  thank_you(), title="Flavor test")


def saved(repo, coverage=None):
    snapshot = clean_survey()
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], encoded(snapshot))
    if coverage is not None:
        repo.db.execute("INSERT INTO coverage(survey_id,version,data) VALUES (?,?,?)",
                        (created["id"], 1, json.dumps(dict(PARTIAL, **coverage))))
        repo.db.commit()
    return created["id"]


def settle(repo, survey_id, skip="\0"):
    """Keep every open card except the ones named, the way a researcher clears a list."""
    for item in repo.detail(survey_id)["overview"]["items"]:
        if item["open"] and not item["id"].startswith(skip):
            for fingerprint in item["fingerprints"]:
                repo.save_decision(survey_id, 1, fingerprint, {"action": "keep", "reason": "Checked it myself"})


def verdict(repo, survey_id):
    return repo.detail(survey_id)["overview"]["verdict"]["kind"]


def test_ready_for_signoff_waits_for_the_branch_check_then_accepts_it_kept(repo):
    walked_all = saved(repo)                         # control: same survey, nothing partial
    settle(repo, walked_all)
    assert verdict(repo, walked_all) == "ready_for_signoff"
    partial = saved(repo, {})
    settle(repo, partial, skip="you-check:branch_paths")
    assert verdict(repo, partial) == "almost_ready"          # everything else done; the branch check is open
    item = next(i for i in repo.detail(partial)["overview"]["items"] if i["id"].startswith("you-check:branch_paths"))
    repo.save_decision(partial, 1, item["id"], {"action": "keep", "reason": "Walked every path myself"})
    assert verdict(repo, partial) == "ready_for_signoff"


def test_a_fully_walked_saved_survey_never_shows_the_item(repo):
    survey_id = saved(repo, {"full_branching_coverage": True})
    assert "branch_paths" not in [i["id"] for i in repo.detail(survey_id)["overview"]["you_check"]]


def test_the_decisions_api_accepts_the_branch_fingerprint_and_rejects_a_pick(repo):
    survey_id = saved(repo, {})
    fingerprint = next(i["fingerprint"] for i in repo.detail(survey_id)["overview"]["you_check"]
                       if i["id"] == "branch_paths")
    assert repo.save_decision(survey_id, 1, fingerprint, {"action": "original"})["fingerprint"] == fingerprint
    with pytest.raises(ValueError):
        repo.save_decision(survey_id, 1, fingerprint, {"action": "pick", "picked_text": "x"})
