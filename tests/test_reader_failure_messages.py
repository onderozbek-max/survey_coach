"""Failure diagnostics must help the owner without leaking preview links or tokens."""
from fastapi.testclient import TestClient
from types import SimpleNamespace
from surveycoach.snapshot import SurveySnapshot, Page

import pytest

from surveycoach.reader.policy import UnsafeSurveyURL
from surveycoach.reader import transport, proxy
from surveycoach.server import create_app


def test_dns_failure_is_actionable_and_does_not_leak_link(tmp_path):
    app = create_app(tmp_path / "db")
    def unavailable(*args, **kwargs):
        raise transport.ReaderDNSFailure("Survey host could not be safely resolved.")
    app.state.reader = unavailable
    with TestClient(app, base_url="http://localhost") as client:
        started = client.post("/api/reader/jobs", json={"url": "https://sample.redjade.net/private-preview", "approval": True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert job["status"] == "failed"
        assert "local reader" in job["error"].lower()
        assert "DNS" in job["error"]
        assert "SURVEYCOACH_CORPORATE_PROXY=http://proxy-intlho.wal-mart.com:8080" in job["error"]
        assert "README" in job["error"]
        assert "off VPN" not in job["error"]
        assert "private-preview" not in job["error"]
        assert "previous review" not in job["error"]  # no previous survey exists


def test_loading_only_page_is_not_a_completed_review(tmp_path):
    app = create_app(tmp_path / "db")
    app.state.reader = lambda *a, **k: SimpleNamespace(coverage=SimpleNamespace(warnings=[]), snapshot=SurveySnapshot(title="Survey", pages=[Page(id="loading", position=0, kind="info", text="Loading")]))
    with TestClient(app, base_url="http://localhost") as client:
        started = client.post("/api/reader/jobs", json={"url": "https://sample.redjade.net/test", "approval": True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert job["status"] == "failed"
        assert "startup" in job["error"].lower()
        assert client.get("/api/surveys").json()["surveys"] == []


def test_unexpected_failure_exposes_only_reference_not_exception(tmp_path):
    app = create_app(tmp_path / "db")
    def broken(*args, **kwargs):
        raise RuntimeError("sensitive local path and survey text")
    app.state.reader = broken
    with TestClient(app, base_url="http://localhost") as client:
        started = client.post("/api/reader/jobs", json={"url": "https://sample.redjade.net/test", "approval": True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert "reference" in job["error"].lower()
        assert "sensitive" not in job["error"]


@pytest.mark.parametrize('failure,expected,absent', [
    (lambda: UnsafeSurveyURL('Survey host did not resolve exclusively to public addresses.'),
     'safely', 'SURVEYCOACH_CORPORATE_PROXY'),
    (lambda: proxy.ReaderProxyConfigurationError('untrusted secret proxy'),
     'proxy configuration', 'untrusted secret'),
    (lambda: TimeoutError('sensitive path'), 'timed out', 'sensitive'),
    (lambda: transport.ReaderNetworkFailure('timeout'), 'timed out', 'DNS lookup'),
    (lambda: transport.ReaderNetworkFailure('connection'), 'connection failed', 'DNS lookup'),
])
def test_failure_categories_remain_distinct(tmp_path, failure, expected, absent):
    app = create_app(tmp_path / 'db')
    def unavailable(*args, **kwargs):
        raise failure()
    app.state.reader = unavailable
    with TestClient(app, base_url='http://localhost') as client:
        started = client.post('/api/reader/jobs', json={
            'url': 'https://app.redjade.net/private-preview', 'approval': True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert job['status'] == 'failed'
        assert expected in job['error']
        assert absent not in job['error']
        assert 'private-preview' not in job['error']
        assert client.get('/api/surveys').json()['surveys'] == []


@pytest.mark.parametrize('kind,expected', [('timeout', 'timed out'), ('connection', 'connection failed')])
def test_initial_connection_failure_from_transport_coverage_is_actionable(tmp_path, kind, expected):
    app = create_app(tmp_path / 'db')
    app.state.reader = lambda *a, **k: SimpleNamespace(
        coverage=SimpleNamespace(warnings=[f'Reader initial connection failed: {kind}.']),
        snapshot=SurveySnapshot(title='', pages=[]))
    with TestClient(app, base_url='http://localhost') as client:
        started = client.post('/api/reader/jobs', json={
            'url': 'https://app.redjade.net/test', 'approval': True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert expected in job['error']
        assert client.get('/api/surveys').json()['surveys'] == []


@pytest.mark.parametrize('failure,expected', [
    (TimeoutError('secret'), 'timed out'), (OSError('secret'), 'connection failed'),
])
def test_host_only_normalized_route_failure_creates_no_review(tmp_path, monkeypatch, failure, expected):
    from unittest.mock import Mock
    from surveycoach.reader.models import Coverage
    monkeypatch.setenv('SURVEYCOACH_CORPORATE_PROXY', 'http://proxy-intlho.wal-mart.com:8080')
    app = create_app(tmp_path / 'db')
    def unavailable(url, **kwargs):
        coverage = Coverage()
        guard = transport.GuardedTransport(url, local=False, approval=True, coverage=coverage)
        monkeypatch.setattr(guard, '_exchange', Mock(side_effect=failure))
        route = Mock()
        route.request.url = url + '/'
        route.request.method = 'GET'
        route.request.headers = {}
        guard(route)
        assert guard._exchange.call_count == 2
        return SimpleNamespace(coverage=coverage, snapshot=SurveySnapshot(title='', pages=[]))
    app.state.reader = unavailable
    with TestClient(app, base_url='http://localhost') as client:
        started = client.post('/api/reader/jobs', json={
            'url': 'https://app.redjade.net', 'approval': True}).json()
        job = client.get(f"/api/jobs/{started['job_id']}").json()
        assert job['status'] == 'failed'
        assert expected in job['error']
        assert 'secret' not in job['error']
        assert client.get('/api/surveys').json()['surveys'] == []
