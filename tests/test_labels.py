"""Canonical labels are a read-only projection shared by screen and round views."""
from copy import deepcopy
import json

import pytest

from surveycoach.labels import finding_label, screen_labels
from surveycoach.server.repository import Repository
from surveycoach.server.rounds import change_sheet, compare_rounds, locations
from surveycoach.snapshot import SurveySnapshot
from surveycoach.timing import reading_basis


def snap():
    def question(identifier, text="Pick one"):
        return {"id": identifier, "text": text, "kind": "single_choice",
                "options": [{"id": "a", "label": "A"}]}

    return SurveySnapshot.model_validate({"title": "T", "pages": [
        {"id": "p0", "position": 0, "kind": "info", "text": "Welcome to our survey about snacks."},
        {"id": "p1", "position": 1, "kind": "question",
         "questions": [question("s1", "How often do you snack?")]},
        {"id": "p2", "position": 2, "kind": "question",
         "questions": [question("g1"), question("g2"), question("g3")]},
        {"id": "p3", "position": 3, "kind": "info", "text": "Almost done."},
        {"id": "p4", "position": 4, "kind": "info", "text": "Thank you for sharing!"}]})


def test_every_view_uses_the_same_names():
    labels = screen_labels(snap())
    assert [s["name"] for s in labels] == ["Welcome", "Q1", "Q2–Q4", "Message", "Thank you"]
    assert labels[2]["questions"][1] == {"id": "g2", "number": 3, "label": "Q3"}
    assert finding_label({"question_id": "g2"}, labels) == "Q3 · Screen 3"
    assert finding_label({"page_id": "p3"}, labels) == "Message · Screen 4"
    assert finding_label({}, labels) == "Whole survey"
    places = locations(snap().model_dump())
    place = next(p for p in places if p["question_id"] == "g2")
    assert place["screen_label"] == "Q3 · Screen 3"
    assert next(p for p in places if p["page_id"] == "p2" and p["slot"] is None)["screen_label"] == "Q2–Q4 · Screen 3"


def test_researcher_question_labels_win_when_captured():
    snapshot = snap()
    snapshot.pages[1].questions[0].label = "Q7a"
    snapshot.pages[2].questions[0].label = "Section B"
    labels = screen_labels(snapshot)
    assert labels[1]["name"] == "Q7a"
    assert labels[2]["name"] == "Section B–Q4"
    assert labels[2]["questions"][1]["number"] == 3
    place = next(p for p in locations(snapshot.model_dump()) if p["question_id"] == "s1")
    assert place["screen_label"] == "Q7a · Screen 2"


def test_info_questions_keep_locations_without_consuming_numbers():
    snapshot = snap()
    instruction = snapshot.pages[1].questions[0].model_copy(
        update={"id": "instruction", "text": "Choose carefully", "kind": "info"})
    snapshot.pages[2].questions.insert(0, instruction)
    before = snapshot.model_dump()
    labels = screen_labels(snapshot)
    places = locations(before)
    assert labels[2]["name"] == "Q2–Q4"
    assert [q["id"] for q in labels[2]["questions"]] == ["g1", "g2", "g3"]
    instruction = next(p for p in places if p["question_id"] == "instruction")
    assert instruction["screen_label"] == "Q2–Q4 · Screen 3"
    assert instruction["slot"] == 0 and instruction["wording"] == "Choose carefully"
    assert next(p for p in places if p["question_id"] == "g2")["screen_label"] == "Q3 · Screen 3"
    assert snapshot.model_dump() == before


@pytest.mark.parametrize("kind,name", [("intro", "Welcome"), ("thank_you", "Thank you"),
                                      ("screen_out", "Screen-out"), ("end", "Last screen"),
                                      ("info", "Message")])
def test_explicit_screen_roles_and_topic_truncation(kind, name):
    snapshot = SurveySnapshot.model_validate({"title": "T", "pages": [
        {"id": "p", "position": 42, "kind": kind, "text": "One two three four five six"}]})
    assert screen_labels(snapshot) == [{"page_id": "p", "screen": 1, "name": name,
                                        "topic": "One two three four five…", "questions": []}]


def test_unknown_findings_and_empty_surveys_are_whole_survey():
    assert screen_labels(SurveySnapshot(title="Empty", pages=[])) == []
    assert finding_label({}, []) == "Whole survey"
    assert finding_label({"question_id": "missing", "page_id": "p1"}, screen_labels(snap())) == "Whole survey"
    assert screen_labels(snap())[1]["topic"] == "How often do you snack?"


def test_round_changes_and_change_sheet_share_canonical_labels_without_mutation():
    finding = {"fingerprint": "f", "criterion_id": "9.1", "question_id": "g2",
               "evidence": "Pick one", "current_text": "Pick one", "suggested_text": "Choose one"}
    detail = {"snapshot": snap().model_dump(), "version": 1, "coverage": None,
              "review": {"findings": [finding], "checked_criteria": ["9.1"]},
              "decisions": {"f": {"action": "pick", "picked_text": "Choose one"}}}
    before = deepcopy(detail)
    changes, carried = compare_rounds(detail, detail)
    assert changes["still"][0]["screen_label"] == "Q3 · Screen 3"
    assert carried["f"]["action"] == "pick"
    assert change_sheet(detail)[0]["screen_label"] == "Q3 · Screen 3"
    assert detail == before


def test_repository_projects_screens_for_each_round_without_writing_history():
    repo = Repository(":memory:")
    try:
        snapshot = snap()
        first = repo.submit(snapshot, ai=False)
        second_snapshot = snapshot.model_copy(deep=True)
        second_snapshot.pages[1].questions[0].label = "Q7a"
        repo.submit(second_snapshot, ai=False, survey_id=first["id"])
        before = list(repo.db.iterdump())
        for version, expected in [(1, snapshot), (2, second_snapshot)]:
            detail = repo.detail(first["id"], version)
            assert detail["screens"] == screen_labels(expected)
            projected = deepcopy(detail["snapshot"])
            for page, original in zip(projected["pages"], expected.pages, strict=True):
                assert page.pop("reading_basis") == reading_basis(original)
            # Only the named derived field is removed: all capture values must
            # still match exactly, not merely survive permissive model validation.
            assert projected == expected.model_dump()
            restored = SurveySnapshot.model_validate(detail["snapshot"])
            assert restored.review_hash == detail["review_hash"] == expected.review_hash
            assert restored.content_hash == detail["content_hash"] == expected.content_hash
            stored = repo.db.execute("SELECT snapshot,content_hash FROM versions WHERE survey_id=? AND version=?",
                                     (first["id"], version)).fetchone()
            assert json.loads(stored["snapshot"]) == expected.model_dump()
            assert stored["content_hash"] == expected.review_hash
            # Mutating a response's derived evidence cannot taint a later read.
            detail["snapshot"]["pages"][0]["reading_basis"]["fields"].clear()
            assert repo.detail(first["id"], version)["snapshot"]["pages"][0]["reading_basis"] == reading_basis(expected.pages[0])
        assert repo.detail(first["id"])["screens"][1]["name"] == "Q7a"
        assert list(repo.db.iterdump()) == before
    finally:
        repo.close()
