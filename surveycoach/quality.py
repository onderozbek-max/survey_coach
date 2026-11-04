"""Read-only, coverage-normalized projection of weighted rubric evidence."""
from __future__ import annotations

from surveycoach.rubric import Rubric

METHOD = "assessed-weight-normalized-v1"
BASIS = "Earned assessed applicable points / assessed applicable points × 100."


def build_quality(review: dict, rubric: Rubric) -> dict:
    """CheckResult.fraction is credit; blockers use findings, not fractions.

    Missing results remain unknown. Explicit N/A is excluded. Neither curated
    findings nor scorecard/readiness nor decisions can change this projection.
    """
    results = review.get("results") or {}
    dimensions = []
    for dimension in rubric.dimensions:
        earned = assessed = applicable = 0
        for criterion in rubric.criteria:
            if not criterion.active or criterion.dimension != dimension.id:
                continue
            result = results.get(criterion.id) or {}
            if result.get("applies", True) is False:
                continue
            applicable += criterion.points
            fraction = result.get("fraction")
            if result.get("assessed", True) and fraction is not None:
                assessed += criterion.points
                earned += criterion.points * fraction
        dimensions.append(dict(id=dimension.id, name=dimension.name, earned_points=earned,
                               assessed_points=assessed, applicable_points=applicable,
                               unchecked_points=applicable - assessed,
                               score=earned / assessed * 100 if assessed else None))
    earned = sum(d["earned_points"] for d in dimensions)
    assessed = sum(d["assessed_points"] for d in dimensions)
    applicable = sum(d["applicable_points"] for d in dimensions)
    flagged = unchecked = 0
    for blocker in rubric.blockers:
        result = results.get(blocker.id)
        if result is None or (result.get("applies", True) and not result.get("assessed", True)):
            unchecked += 1
        if result and any(f.get("severity") == "must_fix" for f in result.get("findings", [])):
            flagged += 1
    return dict(score=earned / assessed * 100 if assessed else None,
                earned_points=earned, assessed_points=assessed, applicable_points=applicable,
                unchecked_points=applicable - assessed,
                coverage_percent=assessed / applicable * 100 if applicable else 0,
                provisional=not assessed or assessed < applicable or unchecked > 0,
                dimensions=dimensions, blockers=dict(flagged=flagged, unchecked=unchecked,
                                                     total=len(rubric.blockers)),
                basis=BASIS, method_version=METHOD, rubric_version=rubric.version)
