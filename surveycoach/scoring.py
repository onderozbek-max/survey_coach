"""Scoring: a plain weighted sum over active criteria (exactly 100 points), plus readiness."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from surveycoach.findings import CheckResult
from surveycoach.rubric import Rubric

Readiness = Literal["ready", "almost_ready", "needs_work"]


class DimensionScore(BaseModel):
    name: str
    earned: float
    possible: int


class ScoreCard(BaseModel):
    score: float
    provisional: bool
    unchecked_points: int
    by_dimension: dict[str, DimensionScore]
    open_blockers: list[str]
    kept_blockers: list[str]
    pending_blockers: list[str]   # blockers no check has judged yet (the AI judge); 'ready' needs none
    readiness: Readiness
    strengths: list[str]
    checked_points: int = 0
    not_applicable_points: int = 0
    score_explanation: str = (
        "Score is earned points out of 100 rubric points: checked criterion points × fraction. "
        "Unchecked and not-applicable criteria earn no points; this is evidence coverage, not a failure verdict."
    )


def score(rubric: Rubric, results: dict[str, CheckResult], kept_blockers: frozenset[str] = frozenset()) -> ScoreCard:
    """Only checked, applicable criteria earn points; unknowns never masquerade as positive evidence."""
    earned: dict[str, float] = {}
    unchecked = 0
    checked = 0
    not_applicable = 0
    for criterion in rubric.criteria:
        if not criterion.active:
            continue
        result = results.get(criterion.id)
        if result is not None and result.assessed and not result.applies:
            earned[criterion.id] = 0.0
            not_applicable += criterion.points
        elif result is None or result.fraction is None or not result.assessed:
            unchecked += criterion.points
            earned[criterion.id] = 0.0
        else:
            checked += criterion.points
            earned[criterion.id] = criterion.points * result.fraction

    by_dimension = {
        d.id: DimensionScore(
            name=d.name,
            earned=sum(earned[c.id] for c in rubric.criteria if c.dimension == d.id and c.active),
            possible=d.points,
        )
        for d in rubric.dimensions
    }
    total = sum(earned.values())
    # Only the two explicitly deferred image judgments may remain on a ready review.
    # Missing wording/story/flow judgments are incomplete evidence, not a passing score.
    incomplete = any(
        c.active and c.id not in {"7.1", "7.4"}
        and ((r := results.get(c.id)) is None or not r.assessed or (r.applies and r.fraction is None))
        for c in rubric.criteria
    )
    flagged = [b.id for b in rubric.blockers if _is_failed(results.get(b.id))]
    open_blockers = [b for b in flagged if b not in kept_blockers]
    kept = [b for b in flagged if b in kept_blockers]
    pending = [b.id for b in rubric.blockers if b.id not in results or not results[b.id].assessed]

    return ScoreCard(
        score=total,
        provisional=unchecked > 0,
        unchecked_points=unchecked,
        checked_points=checked,
        not_applicable_points=not_applicable,
        by_dimension=by_dimension,
        open_blockers=open_blockers,
        kept_blockers=kept,
        pending_blockers=pending,
        readiness=_readiness(rubric, total, bool(open_blockers), bool(pending) or incomplete),
        strengths=_strengths(rubric, results),
    )


def _is_failed(result: CheckResult | None) -> bool:
    return bool(result) and any(f.severity == "must_fix" for f in result.findings)


def _readiness(rubric: Rubric, total: float, has_open_blocker: bool, has_pending_blocker: bool) -> Readiness:
    if has_open_blocker or total < rubric.readiness.almost_min:
        return "needs_work"
    if total >= rubric.readiness.ready_min and not has_pending_blocker:
        return "ready"
    return "almost_ready"


def _strengths(rubric: Rubric, results: dict[str, CheckResult]) -> list[str]:
    """Top 3 criteria that were actually checked and earned full credit, heaviest first."""
    full = [
        c for c in rubric.criteria
        if c.active and (r := results.get(c.id)) is not None and r.applies and r.assessed and r.fraction == 1.0 and not r.findings
    ]
    full.sort(key=lambda c: (-c.points, c.id))
    return [c.title for c in full[:3]]
