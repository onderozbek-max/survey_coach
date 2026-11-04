"""Participant-session gates must remain actionable even before a first page exists."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from surveycoach.reader.models import Coverage
from surveycoach.server import create_app
from surveycoach.snapshot import SurveySnapshot


def test_zero_page_participant_gate_is_not_reported_as_unknown_empty(tmp_path):
    app = create_app(tmp_path / 'test.db')
    app.state.reader = lambda *args, **kwargs: SimpleNamespace(
        snapshot=SurveySnapshot(title='', pages=[]),
        coverage=Coverage(stop_reason='blocked', blocked_requests=1, warnings=[
            'Survey requires participant sign-in; the reader is not in participant mode.']))
    with TestClient(app, base_url='http://localhost') as client:
        started = client.post('/api/reader/jobs', json={
            'url':'https://app.redjade.net/private-preview', 'approval':True}).json()
        result = client.get(f"/api/jobs/{started['job_id']}").json()
        assert result['status'] == 'failed'
        assert 'participant session' in result['error']
        assert 'has not created' in result['error']
        assert 'private-preview' not in result['error']
        assert client.get('/api/surveys').json()['surveys'] == []
