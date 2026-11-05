"""The member journey strip (brief 4.4): one segment per screen, sections found only from real structure."""
import pytest

from builders import intro, page, question, survey, thank_you
from concept_fixture import concept_survey
from review_helpers import save_review
from surveycoach.demo_export import build_demo_data
from surveycoach.journey import build_journey
from surveycoach.labels import screen_labels
from surveycoach.server.repository import Repository
from surveycoach.timing import estimate

BODY = "Here is something to read before you answer. It is a few sentences long, so it is real copy."


def journey_for(snapshot, items=()):
    return build_journey(snapshot, screen_labels(snapshot), estimate(snapshot), list(items))


def labels(snapshot):
    return [s["label"] for s in journey_for(snapshot)["sections"]]


def stimulus_page(position, qid, body=BODY):
    q = question(qid, f"Question {qid}?", options=("Yes", "No"))
    return page(position, q, text=f"{body}\n{q.text}\nYes\nNo")


def plain_page(position, qid):
    return page(position, question(qid, f"Question {qid}?", options=("Yes", "No")))


def test_the_concept_test_gets_its_real_sections_in_order():
    j = journey_for(concept_survey())
    assert [(s["label"], s["start_screen"], s["end_screen"]) for s in j["sections"]] == [
        ("Welcome", 1, 1), ("Warm-up", 2, 2), ("The idea", 3, 3), ("Idea 1", 4, 5), ("Idea 2", 6, 7),
        ("Idea 3", 8, 9), ("Wrap-up", 10, 12), ("Thanks", 13, 13)]
    assert [s["kind"] for s in j["segments"]][:4] == ["welcome", "question", "stimulus", "stimulus"]
    assert j["segments"][-1]["kind"] == "ending"


def test_every_segment_names_its_section_and_the_sections_tile_the_screens():
    j = journey_for(concept_survey())
    by_id = {s["id"]: s for s in j["sections"]}
    assert len(j["segments"]) == 13
    for segment in j["segments"]:
        section = by_id[segment["section"]]
        assert segment["section_label"] == section["label"]
        assert section["start_screen"] <= segment["screen"] <= section["end_screen"]
    assert [s["start_screen"] for s in j["sections"]][1:] == [s["end_screen"] + 1 for s in j["sections"]][:-1]


def test_no_stimulus_means_neutral_labels_never_warm_up():
    snap = survey(intro(), *[plain_page(i, f"q{i}") for i in range(1, 5)], thank_you())
    assert labels(snap) == ["Welcome", "Screens 2-5", "Thanks"]


def test_one_screen_gets_a_singular_neutral_label():
    snap = survey(intro(), plain_page(1, "q1"), thank_you())
    assert labels(snap) == ["Welcome", "Screen 2", "Thanks"]


def test_a_single_stimulus_screen_is_the_idea_and_questions_before_it_are_the_warm_up():
    snap = survey(intro(), plain_page(1, "a"), plain_page(2, "b"), stimulus_page(3, "c"), plain_page(4, "d"),
                  thank_you())
    assert labels(snap) == ["Welcome", "Warm-up", "The idea", "Thanks"]
    ranges = [(s["start_screen"], s["end_screen"]) for s in journey_for(snap)["sections"]]
    assert ranges == [(1, 1), (2, 3), (4, 5), (6, 6)]


def test_different_stimulus_blocks_do_not_become_numbered_ideas():
    other = page(5, question("e", "Pick any?", kind="multi_choice", options=("A", "B", "C")),
                 text=f"{BODY} A second, different idea.\nPick any?\nA\nB\nC")
    snap = survey(intro(), stimulus_page(1, "a"), plain_page(2, "b"), other, thank_you())
    # Two unlike concepts: the structure is not understood, so nothing is named.
    assert labels(snap) == ["Welcome", "Screens 2-4", "Thanks"]


def test_two_blocks_where_the_last_runs_long_are_not_guessed_at():
    # The repeat is only confirmed by a third block, so trailing questions are never called a wrap-up here.
    snap = survey(intro(), stimulus_page(1, "a"), plain_page(2, "b"), stimulus_page(3, "c"), plain_page(4, "d"),
                  plain_page(5, "e"), thank_you())
    assert labels(snap) == ["Welcome", "Screens 2-6", "Thanks"]


def test_a_repeated_block_with_no_stimulus_is_not_numbered():
    snap = survey(intro(), *[plain_page(i, f"q{i}") for i in range(1, 7)], thank_you())
    assert not any(n.startswith("Idea") for n in labels(snap))


def test_info_screens_split_sections_but_neutral_runs_merge():
    mid = page(3, kind="info", text="Quick break. Next we ask about something new.")
    snap = survey(intro(), plain_page(1, "a"), plain_page(2, "b"), mid, plain_page(4, "c"), thank_you())
    j = journey_for(snap)
    assert [s["label"] for s in j["sections"]] == ["Welcome", "Screens 2-5", "Thanks"]
    assert j["segments"][3]["kind"] == "info"


def test_no_pages_is_an_empty_journey():
    empty = survey()
    assert build_journey(empty, [], estimate(empty), []) == {"segments": [], "sections": []}


def test_seconds_add_up_to_the_estimate_and_running_is_the_start_second():
    snap = concept_survey()
    j = journey_for(snap)
    total = estimate(snap).total_seconds
    assert round(sum(s["seconds"] for s in j["segments"]), 1) == total
    assert j["segments"][0]["running"] == 0
    for before, after in zip(j["segments"], j["segments"][1:]):
        assert after["running"] == pytest.approx(before["running"] + before["seconds"], abs=1e-9)
    for section in j["sections"]:
        members = [s for s in j["segments"] if s["section"] == section["id"]]
        assert section["running"] == members[0]["running"]
        assert section["seconds"] == pytest.approx(sum(s["seconds"] for s in members), abs=1e-9)


def test_state_counts_and_tooltip_come_from_open_items_on_the_screen():
    snap = concept_survey()
    items = [{"open": True, "state": "worth_improving", "pages": ["p3"]},
             {"open": True, "state": "fix_before_launch", "pages": ["p3", "p4"]},
             {"open": False, "state": "fix_before_launch", "pages": ["p5"]},
             {"open": True, "state": "you_check", "pages": []}]
    j = journey_for(snap, items)
    by_page = {s["page_id"]: s for s in j["segments"]}
    assert (by_page["p3"]["state"], by_page["p3"]["n_items"]) == ("fix_before_launch", 2)
    assert (by_page["p4"]["state"], by_page["p4"]["n_items"]) == ("fix_before_launch", 1)
    assert (by_page["p5"]["state"], by_page["p5"]["n_items"], by_page["p5"]["n_done"]) == (None, 0, 1)
    assert (by_page["p1"]["state"], by_page["p1"]["n_items"]) == (None, 0)
    assert by_page["p3"]["tooltip"].startswith(f"{by_page['p3']['label']} · ~")
    assert by_page["p3"]["tooltip"].endswith("1 thing to fix, 1 thing to improve")
    assert by_page["p4"]["tooltip"].endswith("1 thing to fix")
    assert by_page["p5"]["tooltip"].endswith("all handled")
    assert " · " not in by_page["p1"]["tooltip"].split("sec")[-1]


def test_tooltip_reads_like_the_brief():
    snap = survey(intro(), plain_page(1, "q1"), thank_you())
    items = [{"open": True, "state": "worth_improving", "pages": ["p1"]}]
    tip = journey_for(snap, items)["segments"][1]["tooltip"]
    assert tip.startswith("Q1 · ~") and tip.endswith(" sec · 1 thing to improve")
    many = [{"open": True, "state": "you_check", "pages": ["p1"]}] * 2
    assert journey_for(snap, many)["segments"][1]["tooltip"].endswith("2 things to check")


def _details(tmp_path):
    repo = Repository(tmp_path / "j.db")
    snap = concept_survey()
    found = {"concept": repo.detail(save_review(repo, snap))}
    for index, entry in enumerate(build_demo_data()["surveys"]):
        found[f"demo-{index}"] = entry
    repo.close()
    return found


def test_detail_presentation_carries_the_journey_and_it_matches_the_verdict_time(tmp_path):
    for name, detail in _details(tmp_path).items():
        presentation = detail["presentation"]
        segments, sections = presentation["journey"], presentation["journey_sections"]
        assert len(segments) == len(detail["snapshot"]["pages"]), name
        total = round(sum(s["seconds"] for s in segments), 1)
        assert total == detail["overview"]["energy"]["total_seconds"], name
        assert round(total / 60, 1) == detail["overview"]["verdict"]["time"]["minutes"], name
        assert sections[0]["start_screen"] == 1 and sections[-1]["end_screen"] == len(segments), name
        marks = {s["page_id"]: s["state"] for s in detail["overview"]["energy"]["screens"]}
        assert {s["page_id"]: s["state"] for s in segments} == marks, name
