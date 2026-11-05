"""The one state mapping table (brief 4.2). Everything that renders a state calls this module.

Four user-facing states, worst first. Nothing else in the code base names a state, so a card,
a tile, a screen marker and the verdict can never disagree about what a finding means.

| Source                                                               | State              |
|----------------------------------------------------------------------|--------------------|
| finding severity `must_fix` (confirmed)                              | fix_before_launch  |
| finding that only a human can judge (unverified image, long list)    | you_check          |
| finding severity `worth_improving` with a concrete fix               | worth_improving    |
| curated You check item (see you_check.py)                            | you_check          |
| assessed, applicable, full credit, nothing open                      | looks_good         |
| unassessed and not on the curated list                               | NOT a state: listed under `not_checked_automatically` |

A category (signal) takes the worst state among its *open* items. It may be `looks_good` only when
real evidence exists: at least MIN_ASSESSED checks passed, covering at least half of the checks
that apply, with nothing open and no partial credit left unexplained. Otherwise it has no state
(`None`, "Not checked automatically"), never a positive one.
"""
from __future__ import annotations

from surveycoach.recommendations import action_kind_of

FIX_BEFORE_LAUNCH = "fix_before_launch"
IMPROVE = "worth_improving"
YOU_CHECK = "you_check"
LOOKS_GOOD = "looks_good"
STATES = (FIX_BEFORE_LAUNCH, IMPROVE, YOU_CHECK, LOOKS_GOOD)   # worst first
STATE_LABELS = {FIX_BEFORE_LAUNCH: "Fix before launch", IMPROVE: "Worth improving",
                YOU_CHECK: "You check", LOOKS_GOOD: "Looks good"}
NOT_CHECKED_LABEL = "Not checked automatically"
MIN_ASSESSED = 2          # one passing check is not a verdict on a whole category
MIN_ASSESSED_SHARE = .5   # ...and neither is a small slice of it

_SEVERITY_STATE = {"must_fix": FIX_BEFORE_LAUNCH, "worth_improving": IMPROVE}


def worst_state(states) -> str | None:
    """Most urgent of the given states, or None when there are none."""
    present = set(states)
    return next((state for state in STATES if state in present), None)


def is_decided(decision: dict | None) -> bool:
    """An explicit choice closes an item; a kept item needs a stated reason."""
    decision = decision or {}
    action = decision.get("action")
    return action in {"pick", "original"} or (
        action == "keep" and bool((decision.get("reason") or "").strip()))


def finding_state(finding: dict) -> str:
    """Map one finding. A confirmed must-fix stays a fix even if its action is a human check."""
    if finding.get("severity") == "must_fix":
        return FIX_BEFORE_LAUNCH
    if action_kind_of(finding) == "you_check":
        return YOU_CHECK
    return _SEVERITY_STATE.get(finding.get("severity"), IMPROVE)


def duration_state(minutes: float, target_high: float) -> str:
    """Time is duration only. Over target is worth improving, never an alarm."""
    return LOOKS_GOOD if minutes <= target_high else IMPROVE


def criterion_passed(result: dict) -> bool:
    """Full credit on a check that ran and applies. Old or partial JSON never gets a default pass."""
    return (result.get("assessed") is True and result.get("applies") is True
            and result.get("fraction") == 1.0)


def signal_state(open_states, *, assessed: int, applicable: int, unexplained: bool = False) -> str | None:
    """Worst open state, else `looks_good` only on real evidence, else no state."""
    worst = worst_state(open_states)
    if worst:
        return worst
    if (unexplained or assessed < MIN_ASSESSED
            or assessed < applicable * MIN_ASSESSED_SHARE):
        return None
    return LOOKS_GOOD
