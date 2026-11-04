"""Precompute the demo site's data from the real engine, so the page only displays results.

Run: .venv/bin/python -m surveycoach.demo_export
The AI findings come from real, human-reviewed model answers committed in fixtures/ai-cache, replayed offline, so
building (and CI) never touch the network. To re-run the real model: ... demo_export --ai-refresh
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from surveycoach.judge import JudgeCache
from surveycoach.judge.batches import BATCHES
from surveycoach.llm import LlmError, WibeyProvider
from surveycoach.llm.base import ASSESSMENT_MODEL
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot
from surveycoach.server.present import enrich

ROOT = Path(__file__).parent.parent
SITE_DATA = ROOT / "site" / "data.js"
AI_CACHE = ROOT / "fixtures" / "ai-cache"
DISCLAIMER = ("Sample data: two made-up surveys. SurveyCoach never reads or changes anything in RedJade; "
              "you copy the fixes and apply them yourself.")
DISCLAIMER_SHORT = "Sample data. SurveyCoach never reads or edits RedJade; you copy fixes yourself."
SAMPLES = [
    ("boxer-briefs", "A deliberately flawed sample. Shows what a review catches and how it explains each fix."),
    ("coffee-pods", "A clean sample. It still cannot be called Ready to launch, because the AI step has not run."),
]


class CacheOnlyProvider:
    """Stands in for the model when building the demo: every answer must already be in the committed cache."""

    def complete_json(self, system, data, schema, images=()):
        raise LlmError("not in the committed AI cache; run: .venv/bin/python -m surveycoach.demo_export --ai-refresh")


class ReviewedDemoCache(JudgeCache):
    """Replay pinned, human-reviewed v4 example answers, then run current grounding.

    Examples are historical fixtures, not evidence of a new live model assessment.
    Production JudgeCache still invalidates all v4 answers on prompt version 5.
    """

    def key(self, snapshot, rubric, batch, known=()):
        # Select only exact committed fixture content, never a user's survey sharing a title.
        for sample_id in ('boxer-briefs','coffee-pods'):
            fixture = SurveySnapshot.model_validate_json((ROOT/'fixtures'/f'{sample_id}.json').read_text())
            if snapshot.review_hash == fixture.review_hash:
                if sample_id == 'boxer-briefs':
                    from surveycoach.server.example import PINNED
                    return PINNED[batch.id]
                return {'wording':'652d35dc2f4649fa433d693e11d96a2b','story':'ff14876d7b968336adf6f6f94bc1ac4f','flow':'3f09544b22ea2d0570a654690f6708c7'}[batch.id]
        return super().key(snapshot,rubric,batch,known)


def _survey(sample_id: str, blurb: str, provider=None) -> dict:
    snapshot = SurveySnapshot.model_validate_json((ROOT / "fixtures" / f"{sample_id}.json").read_text())
    review = run_review(snapshot, provider=provider or CacheOnlyProvider(), cache=ReviewedDemoCache(AI_CACHE))
    encoded = review.model_dump(mode="json", exclude={"timing"})
    encoded["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint}
                           for f in review.findings]
    return enrich({
        "id": sample_id, "title": snapshot.title, "blurb": blurb,
        "review": encoded,
        "timeline": [{"page_id": p.page_id, "seconds": round(p.cumulative_seconds)} for p in review.timing.pages],
        "total_seconds": round(review.timing.total_seconds),
        "snapshot": snapshot.model_dump(mode="json", exclude_defaults=True),
    }, load_rubric())


def build_demo_data(provider=None) -> dict:
    rubric = load_rubric()
    return {
        "disclaimer": DISCLAIMER, "disclaimer_short": DISCLAIMER_SHORT,
        "surveys": [_survey(sample_id, blurb, provider) for sample_id, blurb in SAMPLES],
        "dimensions": {d.id: d.name for d in rubric.dimensions},
        "ai_batches": {b.id: b.title for b in BATCHES},
        "criteria": {**{c.id: {"title": c.title, "dimension": c.dimension, "points": c.points} for c in rubric.criteria},
                     **{b.id: {"title": b.title, "dimension": "blocker", "points": 0} for b in rubric.blockers}},
    }


def render_data_js(data: dict) -> str:
    """ASCII-only (emoji and accents become escapes), stable output."""
    return "window.SURVEYCOACH_DEMO = " + json.dumps(data, ensure_ascii=True, separators=(",", ":")) + ";\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="surveycoach.demo_export")
    parser.add_argument("--ai-refresh", action="store_true", help="Re-run the real AI judge and replace the committed cache")
    args = parser.parse_args(argv)
    if args.ai_refresh:
        for stale in AI_CACHE.glob("*.json"):    # old answers (and answers for old prompts) must not linger
            stale.unlink()
        build_demo_data(WibeyProvider())     # fills the cache from the real model; the output itself is discarded
    SITE_DATA.parent.mkdir(exist_ok=True)
    SITE_DATA.write_text(render_data_js(build_demo_data()))   # always written through the offline replay path
    print(f"wrote {SITE_DATA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
