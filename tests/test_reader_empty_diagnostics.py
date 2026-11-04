"""Empty reads distinguish blocked startup from unsupported rendered content."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from surveycoach.reader.models import Coverage
from surveycoach.reader.transport import GuardedTransport
from surveycoach.server import create_app
from surveycoach.snapshot import SurveySnapshot


@pytest.mark.parametrize('status,code', [(302, 'redirect_blocked'), (401, 'http_401'), (403, 'http_403')])
def test_initial_http_failure_retained_without_following_or_echoing_location(monkeypatch, status, code):
    from http.client import HTTPConnection
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = status
    response.getheaders.return_value = [('location', 'https://private.example/token-secret')]
    response.read.return_value = b''
    monkeypatch.setattr('http.client.HTTPConnection', Mock(return_value=connection))
    coverage = Coverage()
    guard = GuardedTransport('http://127.0.0.1:9000/start', local=True, approval=False, coverage=coverage)
    route = Mock()
    route.request.url = guard.start_url
    route.request.method = 'GET'
    route.request.headers = {}
    guard(route)
    assert f'Reader initial document unavailable: {code}.' in coverage.warnings
    assert 'token-secret' not in str(coverage.warnings)
    assert connection.request.call_count == 1


@pytest.mark.parametrize('warning,expected', [
    ('Reader initial document unavailable: redirect_blocked.', 'redirect'),
    ('Reader initial document unavailable: http_403.', '403'),
    ('Reader initial document unavailable: http_401.', '401'),
    ('', 'empty'),
])
def test_empty_job_has_specific_safe_diagnostic(tmp_path, warning, expected):
    app = create_app(tmp_path / 'test.db')
    coverage = Coverage(stop_reason='reader_error', warnings=[warning] if warning else [])
    app.state.reader = lambda *a, **k: SimpleNamespace(
        snapshot=SurveySnapshot(title='', pages=[]), coverage=coverage)
    with TestClient(app, base_url='http://localhost') as client:
        started = client.post('/api/reader/jobs', json={
            'url':'https://app.redjade.net/private-preview', 'approval':True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert job['status'] == 'failed'
        assert expected in job['error'].lower()
        assert 'private-preview' not in job['error']
        assert client.get('/api/surveys').json()['surveys'] == []
