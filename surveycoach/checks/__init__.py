"""Registers every check module, then runs them all."""
from __future__ import annotations

from surveycoach.checks import answers, content, experience, images, phone, structure  # noqa: F401  (import registers the checks)
from surveycoach.checks.registry import REGISTRY, ReviewContext
from surveycoach.findings import CheckResult


def run_all(context: ReviewContext) -> dict[str, CheckResult]:
    """Every registered check, keyed by rubric ID. A check that raises propagates: no silent skips."""
    results: dict[str, CheckResult] = {}
    for criterion_id, fn in REGISTRY.items():
        results[criterion_id] = fn(context)
    return results
