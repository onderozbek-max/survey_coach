"""Review orchestration, engine-to-Studio serialization, and safe summary packets."""

from surveycoach.judge.batches import BATCHES
from surveycoach.llm import WibeyProvider
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot
from surveycoach.server.report import summary_packet


def metadata() -> dict:
    """Same metadata shape as build_demo_data, without loading fixtures or caches."""
    rubric = load_rubric()
    return {
        "dimensions": {d.id: d.name for d in rubric.dimensions},
        "ai_batches": {b.id: b.title for b in BATCHES},
        "criteria": {**{c.id: {"title": c.title, "dimension": c.dimension, "points": c.points}
                        for c in rubric.criteria},
                     **{b.id: {"title": b.title, "dimension": "blocker", "points": 0}
                        for b in rubric.blockers}},
    }


def run_job(repository, job_id: str, provider=None):
    if not repository.start(job_id):
        return
    try:
        job = repository.job(job_id)
        detail = repository.detail(job["survey_id"], job["version"])
        snapshot = SurveySnapshot.model_validate(dict(detail["snapshot"], survey_type=detail["survey_type"]))
        selected = (provider if provider is not None else WibeyProvider()) if job["ai_requested"] else None
        result = run_review(snapshot, provider=selected)
        review = result.model_dump(mode="json", exclude={"timing"})
        review["checked_criteria"] = sorted(cid for cid, check in result.results.items()
                                            if getattr(check, "assessed", True)
                                            and (check.fraction is not None or cid.startswith("B")))
        for finding, encoded in zip(result.findings, review["findings"]):
            encoded["fingerprint"] = finding.fingerprint
        # Unknown checks and failed batches must never produce an unqualified Ready.
        if (review["unchecked"] or result.scorecard.pending_blockers or
                (result.ai and result.ai.failed)) and review["scorecard"]["readiness"] == "ready":
            review["scorecard"]["readiness"] = "almost_ready"
        repository.finish(job_id, {
            "review": review,
            "timeline": [{"page_id": p.page_id, "seconds": round(p.cumulative_seconds)}
                         for p in result.timing.pages],
            "total_seconds": round(result.timing.total_seconds),
        })
    except Exception:
        # Do not leak arbitrary exception strings (paths, prompts, credentials) to browser clients.
        repository.finish(job_id, error="Review could not finish. Retry the review; previous results are unchanged.")
