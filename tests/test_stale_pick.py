"""Stale picks explain the read-time reset without changing saved history."""
from copy import deepcopy

import pytest

from surveycoach.server.rounds import valid_decisions


def detail_with_pick(picked_text):
    return {
        "review": {"findings": [{
            "fingerprint": "wording",
            "suggested_text": "Improved suggestion",
            "options": [{"text": "Another suggestion"}],
        }]},
        "decisions": {"wording": {
            "action": "pick", "picked_text": picked_text, "manual_done": True,
            "revision": 3, "reason": "Saved context",
        }},
    }


def test_stale_pick_explains_reset_without_mutating_saved_decision():
    detail = detail_with_pick("Previously offered wording")
    before = deepcopy(detail)

    projected = valid_decisions(detail)

    assert projected["wording"] == dict(
        before["decisions"]["wording"], action="open", picked_text=None,
        manual_done=False, stale_pick=True, previous_text="Previously offered wording",
    )
    assert projected["wording"] is not detail["decisions"]["wording"]
    assert detail == before
    assert valid_decisions(detail) == projected


@pytest.mark.parametrize("picked_text", ["Improved suggestion", "Another suggestion"])
def test_still_offered_pick_has_no_stale_explanation(picked_text):
    detail = detail_with_pick(picked_text)
    before = deepcopy(detail)

    projected = valid_decisions(detail)

    assert projected == before["decisions"]
    assert "stale_pick" not in projected["wording"]
    assert "previous_text" not in projected["wording"]
    assert detail == before


@pytest.mark.parametrize("action", ["open", "original", "keep"])
def test_non_pick_decisions_are_not_marked_stale(action):
    detail = detail_with_pick(None)
    detail["decisions"]["wording"]["action"] = action
    before = deepcopy(detail)

    assert valid_decisions(detail) == before["decisions"]
    assert detail == before
