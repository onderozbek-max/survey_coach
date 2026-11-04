"""A pinned worked example; no provider, live read or AI request is involved."""
from pathlib import Path

from surveycoach.judge import JudgeCache
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.server.present import enrich
from surveycoach.snapshot import SurveySnapshot

ROOT = Path(__file__).resolve().parents[2]
# Human-reviewed v4 responses intentionally pinned independently of new prompt/cache keys.
PINNED = {'wording':'bb2f6eed757f0750e04e879bef7ce59e',
          'story':'960e54153565b60542a34646dc587cad',
          'flow':'32cdb258ebcd102cff2b5477fa724f64'}


class ExampleCache(JudgeCache):
    def key(self, snapshot, rubric, batch, known=()):
        return PINNED[batch.id]


class OfflineOnly:
    def complete_json(self, *args, **kwargs):
        from surveycoach.llm import LlmError
        raise LlmError('Worked example cache unavailable; no live AI requested.')


def run_example(repository, job_id):
    if not repository.start(job_id):
        return
    try:
        job = repository.job(job_id)
        detail = repository.detail(job['survey_id'], job['version'])
        snapshot = SurveySnapshot.model_validate(detail['snapshot'])
        result = run_review(snapshot, provider=OfflineOnly(), cache=ExampleCache(ROOT/'fixtures/ai-cache'))
        encoded = result.model_dump(mode='json',exclude={'timing'})
        for finding, item in zip(result.findings,encoded['findings']):
            item['fingerprint'] = finding.fingerprint
        payload = {'review':encoded,
            'timeline':[{'page_id':page.page_id,'seconds':round(page.cumulative_seconds)} for page in result.timing.pages],
            'total_seconds':round(result.timing.total_seconds),
            'example':True}
        # Persist raw assessment evidence, never derived screens or curation.
        projected = enrich({**detail, **payload}, load_rubric())
        repository.finish(job_id, payload)
        return projected
    except Exception:
        repository.finish(job_id,error='The worked example could not load. No live survey or AI request was made.')
