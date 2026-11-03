"""One problem, one rewrite per text: the AI sees each batch alone, so overlaps across criteria are removed here."""
from __future__ import annotations

from surveycoach.findings import CheckResult, Finding
from surveycoach.judge.grounding import norm
from surveycoach.rubric import Rubric


def _where(f: Finding) -> str:
    return f.question_id or f.page_id or "survey"


def dedupe(results: dict[str, CheckResult], rubric: Rubric) -> tuple[dict[str, CheckResult], list[str]]:
    """Blockers are judged first, then criteria in rubric order, so a blocker always wins and the outcome never
    depends on which batch finished first.

    1. A finding that repeats a blocker finding (same place, same quote) is dropped; the criterion keeps its points
       verdict, because the blocker is the visible reason for it.
    2. Only the first finding to rewrite a piece of text keeps its rewrite. Later ones stay as problems with advice,
       but offer no competing replacement, so the researcher never has to choose between rewrites that exclude each other.
    """
    blockers = {b.id for b in rubric.blockers}
    rank = {cid: i for i, cid in enumerate([b.id for b in rubric.blockers] + [c.id for c in rubric.criteria])}
    notes: list[str] = []
    blocked_by: dict[tuple[str, str], str] = {}
    rewritten_by: dict[tuple[str, str], str] = {}
    out: dict[str, CheckResult] = {}
    for result in sorted(results.values(), key=lambda r: rank.get(r.criterion_id, len(rank))):
        kept: list[Finding] = []
        for f in result.findings:
            place = (_where(f), norm(f.evidence))
            if result.criterion_id in blockers:
                blocked_by.setdefault(place, result.criterion_id)
            elif place in blocked_by:
                notes.append(f"{result.criterion_id}: repeats {blocked_by[place]} on {place[0]}")
                continue
            if f.current_text and (f.suggested_text or f.options):
                owner = rewritten_by.setdefault((_where(f), norm(f.current_text)), result.criterion_id)
                if owner != result.criterion_id:
                    notes.append(f"{result.criterion_id}: its rewrite of this text was dropped, {owner} already rewrites it")
                    f = f.model_copy(update={"suggested_text": None, "options": [], "current_text": None, "structural": False})
            kept.append(f)
        out[result.criterion_id] = result.model_copy(update={"findings": kept})
    return out, notes
