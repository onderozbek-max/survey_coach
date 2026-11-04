"""Presentation is a repeatable projection, never a rewrite of stored findings."""
from copy import deepcopy

import pytest

from surveycoach.server.present import ABSORBS, humanize, present_findings

TITLES = {
    "4.1": "Every member can find their answer",
    "4.3": "A way out when needed",
    "8.4": "Only relevant questions",
    "B2": "An honest answer for everyone",
}


def f(fp, cid, sev="worth_improving", q="q5", expl="Why.", **extra):
    return dict(fingerprint=fp, criterion_id=cid, severity=sev,
                question_id=q, explanation=expl, headline=fp, **extra)


def by_fingerprint(findings):
    return {item["fingerprint"]: item for item in present_findings(findings, TITLES)}


def test_bookkeeping_sentence_becomes_also_covers():
    text, covered = humanize(
        "Add a non-shopper answer. This finding also covers 4.1 and 4.3.", TITLES)
    assert text == "Add a non-shopper answer."
    assert covered == ["Every member can find their answer", "A way out when needed"]


@pytest.mark.parametrize("text", [
    "The estimate is 4.1 minutes and covers 4.3 topics.",
    "This question covers 4.1 topics. Keep the wording.",
    "Insurance covers 4.1 dollars of the cost.",
    "This finding also covers 4.1 minutes of effort.",
    "Keep 4.1 and B2 in this ordinary explanation.",
    "First sentence.\n\nKeep this  spacing!",
    "This finding also covers 99.9.",
])
def test_ordinary_prose_and_unknown_bookkeeping_are_preserved(text):
    assert humanize(text, TITLES) == (text, [])


def test_bookkeeping_titles_are_ordered_and_deduplicated_without_losing_prose():
    text, covered = humanize(
        "This finding also covers 4.3, 4.1 and 4.3. "
        "Use an exit. This finding also covers B2 and 4.1. Keep 4.1 minutes.", TITLES)
    assert text == "Use an exit. Keep 4.1 minutes."
    assert covered == [TITLES["4.3"], TITLES["4.1"], TITLES["B2"]]


@pytest.mark.parametrize("text", ["", None])
def test_empty_explanation(text):
    assert humanize(text, TITLES) == ("", [])


def test_absorption_families_are_exact():
    assert ABSORBS == {
        "B1": {"5.1", "5.2", "5.3"}, "B2": {"4.1", "4.3", "8.4"},
        "B5": {"1.4"}, "B7": {"7.1", "7.3", "7.6"},
    }


@pytest.mark.parametrize("blocker,cid", [
    ("B1", "5.1"), ("B1", "5.2"), ("B1", "5.3"),
    ("B2", "4.1"), ("B2", "4.3"), ("B2", "8.4"),
    ("B5", "1.4"), ("B7", "7.1"), ("B7", "7.3"), ("B7", "7.6"),
])
def test_blocker_absorbs_each_same_root_at_same_place(blocker, cid):
    out = by_fingerprint([f("child", cid), f("blocker", blocker, "must_fix")])
    assert out["child"]["absorbed_by"] == "blocker"
    assert out["blocker"]["also_affects"] == ["child"]
    assert list(out) == ["child", "blocker"]


def test_blocker_absorbs_same_root_at_same_place_only():
    out = by_fingerprint([
        f("b2", "B2", "must_fix"), f("r84", "8.4"), f("o41", "4.1", q="q9"),
        f("unrelated", "5.1"), f("another-blocker", "4.1", "must_fix"),
    ])
    assert out["r84"]["absorbed_by"] == "b2"
    assert out["b2"]["also_affects"] == ["r84"]
    for key in ("o41", "unrelated", "another-blocker"):
        assert "absorbed_by" not in out[key]


@pytest.mark.parametrize("left,right,absorbed", [
    ({"question_id": None, "page_id": "p1"}, {"question_id": None, "page_id": "p1"}, True),
    ({"question_id": None, "page_id": "p1"}, {"question_id": None, "page_id": "p2"}, False),
    ({"question_id": "p1"}, {"question_id": None, "page_id": "p1"}, False),
    ({"question_id": "q1", "page_id": "p1"}, {"question_id": "q1", "page_id": "p2"}, False),
    ({"question_id": "q1", "page_id": "p1"}, {"question_id": None, "page_id": "p1"}, False),
    ({"question_id": None}, {"question_id": None}, True),
    ({"question_id": None}, {"question_id": "q1"}, False),
])
def test_place_is_scoped_without_question_page_or_survey_collisions(left, right, absorbed):
    blocker = f("b5", "B5", "must_fix") | left
    child = f("child", "1.4") | right
    out = by_fingerprint([blocker, child])
    assert (out["child"].get("absorbed_by") == "b5") is absorbed


@pytest.mark.parametrize("severity", ["worth_improving", "polish"])
def test_non_blocking_severity_cannot_absorb(severity):
    out = by_fingerprint([f("b2", "B2", severity), f("child", "4.1")])
    assert "absorbed_by" not in out["child"]
    assert "also_affects" not in out["b2"]


def test_first_matching_blocker_owns_child_once():
    out = by_fingerprint([
        f("first", "B2", "must_fix"), f("second", "B2", "must_fix"),
        f("child", "4.1"), f("other", "4.3"),
    ])
    assert out["first"]["also_affects"] == ["child", "other"]
    assert out["child"]["absorbed_by"] == "first"
    assert "also_affects" not in out["second"]


def test_projection_preserves_findings_and_does_not_mutate_nested_input():
    original = [
        f("b2", "B2", "must_fix", expl="Add an answer. This finding also covers 4.1.",
          options=[{"text": "Not applicable"}], evidence="Exact quote", source="ai"),
        f("r84", "8.4"),
    ]
    before = deepcopy(original)
    out = present_findings(original, TITLES)
    assert original == before
    assert len(out) == len(original)
    assert out[0] == before[0] | {
        "explanation": "Add an answer.", "also_covers": [TITLES["4.1"]], "also_affects": ["r84"],
    }
    out[0]["options"][0]["text"] = "Changed by consumer"
    assert original == before


def test_projection_is_idempotent_including_humanized_titles():
    original = [f("b2", "B2", "must_fix", expl="Why. This finding also covers 4.1."),
                f("r84", "8.4")]
    once = present_findings(original, TITLES)
    before = deepcopy(once)
    assert present_findings(once, TITLES) == once
    assert once == before


def test_absorption_is_recomputed_not_carried_across_projections():
    original = [f("b2", "B2", "must_fix"), f("r84", "8.4")]
    projected = present_findings(original, TITLES)
    projected[1]["question_id"] = "elsewhere"
    out = by_fingerprint(projected)
    assert "absorbed_by" not in out["r84"]
    assert "also_affects" not in out["b2"]


def test_empty_findings_and_missing_explanation():
    assert present_findings([], TITLES) == []
    finding = f("one", "4.1")
    del finding["explanation"]
    assert present_findings([finding], TITLES) == [finding | {"explanation": "", "also_covers": []}]
