"""Review orchestration, engine-to-Studio serialization, and safe summary packets."""
from html import escape
from pathlib import Path

from surveycoach.judge.batches import BATCHES
from surveycoach.llm import WibeyProvider
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot


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
        snapshot = SurveySnapshot.model_validate(detail["snapshot"])
        selected = (provider if provider is not None else WibeyProvider()) if job["ai_requested"] else None
        result = run_review(snapshot, provider=selected)
        review = result.model_dump(mode="json", exclude={"results", "timing"})
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


def summary_packet(detail: dict) -> str:
    def text(value):
        return escape(str(value if value is not None else ""), quote=True)

    review = detail["review"]
    site = Path(__file__).resolve().parents[2] / "site"
    styles = "\n".join((site / name).read_text() for name in ("styles.css", "design-system.css"))
    parts = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             f"<title>SurveyCoach review report</title><style>{styles}</style><body>",
             "<header class='app-header'><span class='app-brand'><span class='brand-mark'></span>SurveyCoach</span><span class='pill'>Exported review · not launch approval</span></header><main class='report-shell'>",
             f"<h1>{text(detail['title'])}</h1><p>Version {detail['version']}</p>",
             "<p>SurveyCoach does not edit RedJade. Manual completion is researcher-reported, not verified.</p>"]
    if review is None:
        parts.append("<p>Review not available. Readiness has not been checked.</p>")
    else:
        card = review["scorecard"]
        earned = round(card['score'] - card['unchecked_points'], 2)
        checked = 100 - card['unchecked_points']
        parts.append(f"<h2>Readiness: {text(card['readiness'])}</h2><p>{earned:g} of {checked} checked points earned; "
                     f"{card['unchecked_points']} points unchecked. This is not an automatic launch approval.</p>")
        coverage = detail.get("coverage")
        parts.append("<h2>Source and coverage</h2>")
        parts.append(f"<p>{text('Captured link' if coverage else 'Imported survey snapshot; capture completeness not independently verified.')}</p>")
        if coverage:
            parts.append(f"<p>Captured pages: {coverage['pages_captured']}; stopped: {text(coverage['stop_reason'])}</p>")
            parts.extend(f"<p>{text(warning)}</p>" for warning in coverage['warnings'])
        ai = review.get("ai")
        parts.append(f"<p>AI: {text('not requested / unchecked' if ai is None else 'requested')}</p>")
        if ai:
            parts.append(f"<p>AI checked: {text(', '.join(ai['checked']))}; "
                         f"failed: {text(', '.join(ai['failed']))}</p>")
        parts.append(f"<p>Unchecked: {text('; '.join(review['unchecked']))}</p>")
        parts.append(f"<p>Pending blockers: {text(', '.join(card['pending_blockers']))}</p>")
        parts.append("<h2>Findings and decisions</h2><ol>")
        for finding in review["findings"]:
            decision = detail["decisions"].get(finding["fingerprint"], {})
            rewrites = finding.get("options") or ([{"label": "Suggested rewrite", "text": finding["suggested_text"]}]
                                                  if finding.get("suggested_text") else [])
            recommendations = "".join(f"<p><strong>{text(option['label'])}:</strong> {text(option['text'])}</p>"
                                      for option in rewrites)
            if not recommendations:
                recommendations = "<p>Action required — no ready-to-use rewrite. Follow the guidance above.</p>"
            parts.append(f"<li><h3>{text(finding['headline'])}</h3>"
                         f"<p>{text(finding['severity'])}: {text(finding['evidence'])}</p>"
                         f"<p>{text(finding['explanation'])}</p>{recommendations}"
                         f"<p>Decision: {text(decision.get('action', 'open'))}</p>"
                         f"<p>Original: {text(decision.get('original', finding.get('current_text')))}</p>"
                         f"<p>Picked text: {text(decision.get('picked_text'))}</p>"
                         f"<p>Reason: {text(decision.get('reason'))}</p>"
                         f"<p>Manual completion: {text(decision.get('manual_done', False))}</p></li>")
        parts.append("</ol>")
    return "\n".join([*parts, "</main></body></html>"])
