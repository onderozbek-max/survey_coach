"""Plan curation is a pure projection, not a decision or stored-review rewrite."""
from copy import deepcopy

import pytest

from surveycoach.server.plan import build_plan


def finding(fp, cid="4.1", severity="worth_improving", question="q1", **extra):
    return {
        "fingerprint": fp, "criterion_id": cid, "severity": severity,
        "question_id": question, "headline": fp, **extra,
    }


def screens(count=12):
    return [
        {"page_id": f"p{n}", "screen": n, "questions": [{"id": f"q{n}"}]}
        for n in range(1, count + 1)
    ]


def test_sentence_case_pattern_is_one_nice_to_have_idea():
    findings = [finding(str(n), "9.2", question=f"q{n}",
                        headline="Question isn't in sentence case")
                for n in range(12, 0, -1)]
    plan = build_plan(findings, {}, {"9.2": 100}, screens())
    assert plan["must_fix"] == plan["quick_wins"] == []
    assert plan["more"] == [{
        "id": "pattern-1", "fingerprints": [str(n) for n in range(1, 13)],
        "criterion_id": "9.2", "headline": "Question isn't in sentence case",
        "count": 12, "tier": "nice_to_have", "screen": 1, "decided": False,
    }]


def test_must_fix_findings_are_individual_even_with_same_pattern():
    findings = [finding("second", "B2", "must_fix", "q2", headline="Add an exit"),
                finding("first", "B2", "must_fix", "q1", headline="Add an exit")]
    plan = build_plan(findings, {"first": {"action": "pick"}}, {}, screens())
    assert [item["id"] for item in plan["must_fix"]] == ["first", "second"]
    assert all(item["count"] == 1 and item["tier"] == "must_fix"
               for item in plan["must_fix"])
    assert plan["counts"] == {
        "must_fix": 2, "quick_wins": 0, "more": 0, "open_must_fix": 1,
    }


def test_quick_wins_are_capped_ranked_by_points_then_screen_with_overflow():
    findings = [finding(f"f{n}", f"4.{n}", question=f"q{n}")
                for n in range(8, 0, -1)]
    findings.append(finding("polish", "9.1"))
    points = {f"4.{n}": 1 for n in range(1, 9)} | {"4.8": 10, "9.1": 1000}
    plan = build_plan(findings, {}, points, screens())
    assert [item["id"] for item in plan["quick_wins"]] == [
        "f8", "f1", "f2", "f3", "f4", "f5",
    ]
    assert all(item["tier"] == "improve" for item in plan["quick_wins"])
    assert [item["id"] for item in plan["more"]] == ["f6", "f7", "polish"]
    assert plan["counts"] == {
        "must_fix": 0, "quick_wins": 6, "more": 3, "open_must_fix": 0,
    }


def test_absorbed_findings_are_excluded_from_every_list_and_count():
    findings = [finding("blocker", "B2", "must_fix", absorbed_by="other"),
                finding("improve", absorbed_by="other"),
                finding("polish", "9.2", absorbed_by="other")]
    assert build_plan(findings, {}, {}, []) == {
        "must_fix": [], "quick_wins": [], "more": [],
        "counts": {"must_fix": 0, "quick_wins": 0, "more": 0, "open_must_fix": 0},
    }


@pytest.mark.parametrize("decision,expected", [
    (None, False), ({}, False),
    ({"action": "pick"}, True), ({"action": "original"}, True),
    ({"action": "keep", "reason": "Member needs this wording"}, True),
    ({"action": "keep"}, False), ({"action": "keep", "reason": " \n\t"}, False),
    ({"action": "pending", "reason": "Not an explicit choice"}, False),
    ({"pick": "option-1"}, False),
])
def test_only_explicit_choices_or_reasoned_keep_mark_an_item_decided(decision, expected):
    decisions = {"f": decision} if decision is not None else {}
    plan = build_plan([finding("f", "B2", "must_fix")], decisions, {}, [])
    assert plan["must_fix"][0]["decided"] is expected
    assert plan["counts"]["open_must_fix"] == int(not expected)


@pytest.mark.parametrize("last_decision,expected", [
    (None, False), ({"action": "keep", "reason": " "}, False),
    ({"action": "keep", "reason": "Keep the member's voice"}, True),
    ({"action": "original"}, True),
])
def test_group_is_decided_only_when_every_member_is_decided(last_decision, expected):
    findings = [finding(str(n), "9.2", headline="Sentence case") for n in range(3)]
    decisions = {"0": {"action": "pick"}, "1": {"action": "original"},
                 "2": last_decision}
    plan = build_plan(findings, decisions, {}, [])
    assert plan["more"][0]["decided"] is expected
    assert plan["more"][0]["count"] == 3


def test_patterns_normalize_case_and_whitespace_but_not_criterion_or_meaning():
    findings = [finding("a", headline="Improve  this LABEL"),
                finding("b", headline=" improve this\nlabel "),
                finding("c", "4.3", headline="Improve this label"),
                finding("d", headline="Different suggestion")]
    plan = build_plan(findings, {}, {}, [])
    assert [item["fingerprints"] for item in plan["quick_wins"]] == [
        ["a", "b"], ["c"], ["d"],
    ]


def test_screen_order_uses_question_then_page_then_survey_fallback():
    findings = [finding("page", question=None, page_id="p2"),
                finding("question", question="q1", page_id="p2"),
                finding("survey", question=None),
                finding("unknown-question", question="unknown", page_id="p1")]
    plan = build_plan(findings, {}, {}, screens(2))
    assert [(item["id"], item["screen"]) for item in plan["quick_wins"]] == [
        ("survey", 0), ("question", 1), ("unknown-question", 1), ("page", 2),
    ]


def test_empty_plan_has_zero_counts():
    assert build_plan([], {}, {}, []) == {
        "must_fix": [], "quick_wins": [], "more": [],
        "counts": {"must_fix": 0, "quick_wins": 0, "more": 0, "open_must_fix": 0},
    }


def test_projection_is_repeatable_and_does_not_mutate_or_alias_inputs():
    findings = [finding("b", "9.2", question="q2", headline="Sentence case"),
                finding("a", "9.2", headline="Sentence case")]
    decisions = {"a": {"action": "pick", "pick": {"text": "New wording"}},
                 "b": {"action": "keep", "reason": "Preserve voice"}}
    args = (findings, decisions, {"9.2": 1}, screens(2))
    before = deepcopy(args)
    first = build_plan(*args)
    assert first == build_plan(*args)
    assert args == before
    first["more"][0]["fingerprints"].append("not-stored")
    first["more"][0]["headline"] = "not-stored"
    assert args == before
    assert build_plan(*args)["more"][0]["fingerprints"] == ["a", "b"]
