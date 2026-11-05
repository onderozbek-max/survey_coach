"""The review pipeline: snapshot in, scored review out. Pure and deterministic."""
from __future__ import annotations

from pydantic import BaseModel

from surveycoach.checks import run_all
from surveycoach.checks.registry import ReviewContext
from surveycoach.findings import CheckResult, Finding
from surveycoach.judge import AiRunInfo, JudgeCache, run_judge
from surveycoach.judge.grounding import CREDIT_CAP_WITH_FINDING
from surveycoach.llm import LlmProvider
from surveycoach.rubric import Rubric, load_rubric
from surveycoach.scoring import ScoreCard, score
from surveycoach.snapshot import SurveySnapshot
from surveycoach.timing import Timing


# Criteria that need rendered images to be judged at all (surveycoach/checks/images.py).
MEDIA_CRITERIA = ("7.2", "7.3", "7.5", "7.6", "B7")


class Review(BaseModel):
    survey_title: str
    content_hash: str
    rubric_version: str
    scorecard: ScoreCard
    findings: list[Finding]
    unchecked: list[str]            # titles of active criteria no check could judge yet
    est_minutes: float
    promised_minutes: float | None
    timing: Timing
    results: dict[str, CheckResult]
    ai: AiRunInfo | None = None     # None means the AI step did not run at all


def _merge(results: dict[str, CheckResult], rubric: Rubric) -> list[Finding]:
    """Only exact root duplicates collapse; must-fix wins, then rubric order."""
    order = {cid: i for i, cid in enumerate([b.id for b in rubric.blockers] + [c.id for c in rubric.criteria])}
    unique: dict[tuple[str, str, str], Finding] = {}
    findings = sorted([f for result in results.values() for f in result.findings],
                      key=lambda f: (f.severity != "must_fix", order.get(f.criterion_id, 999)))
    for f in findings:
        unique.setdefault(f.root_identity, f)
    return list(unique.values())


def _with_ai(code: dict[str, CheckResult], ai: dict[str, CheckResult]) -> dict[str, CheckResult]:
    """Preserve code evidence and independent AI problems; a cosmetic check never vetoes a semantic issue."""
    merged = dict(code)
    for cid, theirs in ai.items():
        mine = code.get(cid)
        if mine is None:
            merged[cid] = theirs
        elif theirs.findings or not mine.assessed or (mine.fraction is None and theirs.fraction is not None):
            known = {f.root_identity for f in mine.findings}
            findings = [*mine.findings, *[f for f in theirs.findings if f.root_identity not in known]]
            fractions = [f for f in (mine.fraction, theirs.fraction) if f is not None]
            fraction = min(fractions) if fractions else None
            if findings and fraction is not None:
                fraction = min(fraction, CREDIT_CAP_WITH_FINDING)
            merged[cid] = CheckResult(criterion_id=cid, fraction=fraction, applies=mine.applies,
                                      assessed=mine.assessed or theirs.assessed, findings=findings)
    return merged


def _withhold_unverified_media(results: dict[str, CheckResult], snapshot: SurveySnapshot) -> dict[str, CheckResult]:
    """Unrendered screens have unknown images: image checks cannot pass or be N/A on them.

    "No images verified" is not "verified no images". Findings on rendered screens stay.
    """
    if snapshot.all_pages_rendered or not snapshot.pages:
        return results
    withheld = dict(results)
    for criterion_id in MEDIA_CRITERIA:
        if criterion_id in results:
            withheld[criterion_id] = results[criterion_id].model_copy(
                update={"assessed": False, "applies": True, "fraction": None})
    return withheld


def run_review(snapshot: SurveySnapshot, rubric: Rubric | None = None, kept_blockers: frozenset[str] = frozenset(),
               provider: LlmProvider | None = None, cache: JudgeCache | None = None) -> Review:
    rubric = rubric or load_rubric()
    context = ReviewContext.build(snapshot, rubric)
    results = run_all(context)
    ai: AiRunInfo | None = None
    if provider is not None:
        known = [f for r in results.values() for f in r.findings]
        ai_results, ai = run_judge(snapshot, rubric, provider, cache, known=known)
        results = _with_ai(results, ai_results)
    results = _withhold_unverified_media(results, snapshot)
    unchecked = [c.title for c in rubric.criteria if c.active
                 and ((r := results.get(c.id)) is None or not r.assessed or (r.applies and r.fraction is None))]
    return Review(
        survey_title=snapshot.title, content_hash=snapshot.content_hash, rubric_version=rubric.version,
        scorecard=score(rubric, results, kept_blockers), findings=_merge(results, rubric), unchecked=unchecked,
        est_minutes=context.timing.minutes, promised_minutes=context.promised_minutes,
        timing=context.timing, results=results, ai=ai)
