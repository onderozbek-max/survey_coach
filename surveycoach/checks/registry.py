"""Check registry. A check is a pure function of ReviewContext, registered by rubric ID."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple

from surveycoach.findings import CheckResult, Finding, Severity
from surveycoach.rubric import Rubric
from surveycoach.snapshot import SurveySnapshot
from surveycoach.timing import Timing, estimate, parse_promised_minutes


@dataclass(frozen=True)
class ReviewContext:
    snapshot: SurveySnapshot
    rubric: Rubric
    timing: Timing
    promised_minutes: float | None

    @classmethod
    def build(cls, snapshot: SurveySnapshot, rubric: Rubric) -> "ReviewContext":
        return cls(snapshot, rubric, estimate(snapshot), parse_promised_minutes(snapshot.intro_text))


CheckFn = Callable[[ReviewContext], CheckResult]
REGISTRY: dict[str, CheckFn] = {}


def check(criterion_id: str) -> Callable[[CheckFn], CheckFn]:
    def register(fn: CheckFn) -> CheckFn:
        if criterion_id in REGISTRY:
            raise ValueError(f"check {criterion_id} registered twice")
        REGISTRY[criterion_id] = fn
        return fn
    return register


def finding(criterion_id: str, severity: Severity, headline: str, evidence: str, explanation: str,
            member_impact: str, **extras: Any) -> Finding:
    """One finding. Keyword extras: page_id, question_id, element_id, current_text, suggested_text, highlight,
    options, field_location, and the action: `steps=[...]` (1-3), `you_check="question?"`, or pasteable
    `suggested_text` / `options`. Exactly one action is required, so no check can forget it (brief 6.3).

    `headline`, `member_impact` and the action are the card the researcher reads (member language, no jargon);
    `explanation` is the details, where the technical nuance lives.
    """
    extras = {key: value for key, value in extras.items() if value not in (None, [], ())}
    present = [kind for kind, there in (("paste", extras.get("suggested_text") or extras.get("options")),
                                        ("steps", extras.get("steps")), ("you_check", extras.get("you_check")))
               if there]
    if len(present) != 1:
        raise ValueError(f"{criterion_id}: a finding needs exactly one action (paste, steps or you_check), got {present}")
    if "steps" in extras:
        extras["steps"] = list(extras["steps"])
    return Finding(criterion_id=criterion_id, severity=severity, headline=headline, evidence=evidence,
                   explanation=explanation, member_impact=member_impact, action_kind=present[0], **extras)


class Problem(NamedTuple):
    """What a check found wrong with one thing, before it is tied to a rubric criterion and a place.

    `fix` is the details (why and how, with nuance); `steps` or `you_check` is the action on the card.
    With neither, a `suggested` text is the paste. `impact` overrides the check's shared impact line.
    """
    headline: str
    evidence: str
    fix: str
    current: str | None = None
    suggested: str | None = None
    highlight: str | None = None
    steps: tuple[str, ...] = ()
    you_check: str | None = None
    impact: str | None = None


def problem_finding(criterion_id: str, problem: Problem, impact: str, severity: Severity = "worth_improving",
                    **where: str | None) -> Finding:
    return finding(criterion_id, severity, problem.headline, problem.evidence, problem.fix, problem.impact or impact,
                   current_text=problem.current, suggested_text=problem.suggested, highlight=problem.highlight,
                   steps=problem.steps, you_check=problem.you_check, **where)


def result(criterion_id: str, fraction: float | None, *findings: Finding) -> CheckResult:
    return CheckResult(criterion_id=criterion_id, fraction=fraction, findings=list(findings))


def passed(criterion_id: str) -> CheckResult:
    return result(criterion_id, 1.0)


def not_applicable(criterion_id: str) -> CheckResult:
    return CheckResult(criterion_id=criterion_id, applies=False)


def blocker_ok(blocker_id: str) -> CheckResult:
    return CheckResult(criterion_id=blocker_id)


def clip(text: str, limit: int = 120) -> str:
    """Shorten evidence at a word boundary, with an ellipsis, so it never ends mid-word."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip(" ,;:") + "..."


def share_fraction(failing: int, total: int) -> float:
    """Proportional credit: the share of items that pass. There must be something to judge.

    Zero items is not a pass: callers go through `share_result`, which answers N/A instead.
    """
    if total <= 0:
        raise ValueError("share_fraction needs at least one eligible item; use share_result for N/A")
    return round(max(0.0, 1 - failing / total), 2)


def share_result(criterion_id: str, failing: int, total: int, *findings: Finding, assessed: bool = True) -> CheckResult:
    """Proportional credit over eligible items; explicit N/A when none exist.

    `assessed=False` keeps the findings that could be evaluated but withholds credit, because
    some evidence the criterion needs was not captured.
    """
    if total == 0 and not findings:
        return not_applicable(criterion_id)
    fraction = share_fraction(failing, total) if assessed else None
    return CheckResult(criterion_id=criterion_id, fraction=fraction, assessed=assessed, findings=list(findings))


def absent_or_unknown(criterion_id: str, *, kind_present: bool) -> CheckResult:
    """Nothing eligible to judge. Truly absent content is N/A; present-but-unreadable content is unknown."""
    return CheckResult(criterion_id=criterion_id, assessed=False) if kind_present else not_applicable(criterion_id)
