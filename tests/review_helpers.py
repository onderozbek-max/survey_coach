"""Store a finished synthetic review without running a job: shared by the finish-line suites."""
from surveycoach.review import run_review


def encoded(snapshot) -> dict:
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


def save_review(repo, snapshot, survey_id=None) -> str:
    """Submit `snapshot` (as a new survey, or a new version of `survey_id`) and finish its review; return the id."""
    created = repo.submit(snapshot, ai=False, survey_id=survey_id)
    repo.finish(created["job_id"], encoded(snapshot))
    return created["id"]
