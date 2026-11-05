"""The one state mapping table (brief 4.2): four states, one place."""
import pytest

from surveycoach import status
from surveycoach.status import (FIX_BEFORE_LAUNCH, IMPROVE, LOOKS_GOOD, STATE_LABELS, STATES, YOU_CHECK,
                                criterion_passed, duration_state, finding_state, is_decided,
                                signal_state, worst_state)


def test_exactly_four_states_with_user_facing_labels():
    assert STATES == ("fix_before_launch", "worth_improving", "you_check", "looks_good")
    assert STATE_LABELS == {"fix_before_launch": "Fix before launch", "worth_improving": "Worth improving",
                            "you_check": "You check", "looks_good": "Looks good"}


def f(**extra):
    return {"criterion_id": "3.2", "severity": "worth_improving", "headline": "Hard word", **extra}


@pytest.mark.parametrize("finding,expected", [
    (f(severity="must_fix"), FIX_BEFORE_LAUNCH),
    (f(severity="worth_improving"), IMPROVE),
    (f(severity="worth_improving", suggested_text="Do this"), IMPROVE),
    (f(criterion_id="B7", severity="worth_improving", headline="Reader could not verify image loading: Hero"), YOU_CHECK),
    (f(criterion_id="B7", severity="must_fix", headline="Image options are too small to judge (80 px)"), FIX_BEFORE_LAUNCH),
    (f(criterion_id="6.2", headline="10 answer choices; review the phone layout"), YOU_CHECK),
    (f(criterion_id="6.2", headline="Answer text is too long to tap comfortably"), IMPROVE),
    (f(action_kind="you_check", you_check="Does it show?"), YOU_CHECK),
    (f(severity="must_fix", action_kind="you_check", you_check="Does it show?"), FIX_BEFORE_LAUNCH),
])
def test_finding_mapping(finding, expected):
    assert finding_state(finding) == expected


def test_worst_state_is_the_most_urgent_and_empty_has_none():
    assert worst_state([LOOKS_GOOD, YOU_CHECK, IMPROVE]) == IMPROVE
    assert worst_state([LOOKS_GOOD, FIX_BEFORE_LAUNCH, YOU_CHECK]) == FIX_BEFORE_LAUNCH
    assert worst_state([LOOKS_GOOD]) == LOOKS_GOOD
    assert worst_state([]) is None


@pytest.mark.parametrize("decision,expected", [
    (None, False), ({}, False), ({"action": "open"}, False), ({"action": "pending"}, False),
    ({"action": "pick"}, True), ({"action": "original"}, True),
    ({"action": "keep", "reason": "Study need"}, True),
    ({"action": "keep", "reason": "  "}, False), ({"action": "keep"}, False),
])
def test_decided_means_an_explicit_choice(decision, expected):
    assert is_decided(decision) is expected


@pytest.mark.parametrize("minutes,expected", [(0, LOOKS_GOOD), (6, LOOKS_GOOD), (10, LOOKS_GOOD),
                                              (10.01, IMPROVE), (30, IMPROVE)])
def test_duration_over_the_target_is_worth_improving_never_a_fix(minutes, expected):
    assert duration_state(minutes, 10) == expected


@pytest.mark.parametrize("result,expected", [
    ({"assessed": True, "applies": True, "fraction": 1.0}, True),
    ({"assessed": True, "applies": True, "fraction": .99}, False),
    ({"assessed": False, "applies": True, "fraction": 1.0}, False),
    ({"assessed": True, "applies": False, "fraction": 1.0}, False),
    ({"assessed": True, "applies": True, "fraction": None}, False),
    ({"fraction": 1.0}, False), ({}, False),
])
def test_only_full_credit_on_an_assessed_applicable_check_is_a_pass(result, expected):
    assert criterion_passed(result) is expected


def test_signal_takes_the_worst_open_state():
    assert signal_state([IMPROVE, YOU_CHECK], assessed=7, applicable=7) == IMPROVE
    assert signal_state([YOU_CHECK], assessed=0, applicable=7) == YOU_CHECK


def test_one_of_seven_checks_can_never_look_good():
    assert signal_state([], assessed=1, applicable=7) is None
    assert signal_state([], assessed=3, applicable=8) is None   # the old "3 of 8 Looking good"


def test_looks_good_needs_real_evidence_and_nothing_unexplained():
    assert signal_state([], assessed=4, applicable=7) == LOOKS_GOOD
    assert signal_state([], assessed=2, applicable=2) == LOOKS_GOOD
    assert signal_state([], assessed=1, applicable=1) is None      # a single check is not a verdict
    assert signal_state([], assessed=0, applicable=5) is None
    assert signal_state([], assessed=5, applicable=5, unexplained=True) is None


def test_this_module_is_the_only_place_that_names_states():
    # signals/verdict/report import the table instead of re-declaring it.
    assert set(status.STATE_LABELS) == set(status.STATES)
