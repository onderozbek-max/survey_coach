"""Participant mode: behave like a respondent on the survey's own site, but never complete."""
from unittest.mock import Mock

import pytest

from surveycoach.reader.models import Coverage
from surveycoach.reader.session import external_progression_stop
from surveycoach.reader.transport import GuardedTransport

START = "https://app.redjade.net/surveys/demo/example/"
API = "https://app.redjade.net/api/v1/surveys"


def _route(method, url, data=None, headers=None):
    route = Mock()
    route.request.url, route.request.method = url, method
    route.request.headers = headers or {"content-type": "application/json"}
    route.request.post_data = data
    return route


def _transport(monkeypatch, *, participate):
    monkeypatch.setenv("SURVEYCOACH_CORPORATE_PROXY", "http://proxy-intlho.wal-mart.com:8080")
    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = b'{"ok": true}'
    connection.getresponse.return_value.getheaders.return_value = [("content-type", "application/json")]
    monkeypatch.setattr("http.client.HTTPSConnection", Mock(return_value=connection))
    guard = GuardedTransport(START, local=False, approval=True, coverage=Coverage(), participate=participate)
    return guard, connection


@pytest.mark.parametrize("method,path", [
    ("POST", "/online_sign_in_events"), ("POST", "/responses"), ("PUT", "/responses/42"),
    ("PATCH", "/participants/7"), ("GET", "/current_participant?lite=true&page=3"),
    # Observed RedJade per-answer save: "submit" here is not survey completion.
    ("PUT", "https://app.redjade.net/api/v1/answer_submit_events/1347073403"),
    ("POST", "https://app.redjade.net/api/v1/page_start_events"),
    # Observed on Next. Owner approved submitting answers; the reader still never clicks Submit/Finish.
    ("POST", "/questionnaire_submit_events"),
])
def test_participant_requests_are_forwarded(monkeypatch, method, path):
    guard, connection = _transport(monkeypatch, participate=True)
    route = _route(method, path if path.startswith("https") else API + path,
                   b'{"answer": 1}' if method != "GET" else None)
    guard(route)
    route.fulfill.assert_called_once()
    if method != "GET":
        assert connection.request.call_args.kwargs["body"] == b'{"answer": 1}'
        assert guard.coverage.participated


@pytest.mark.parametrize("method,url", [
    ("POST", "https://other.redjade.net/api/v1/surveys/responses"),
    ("POST", "https://evil.example/collect"), ("DELETE", API + "/responses/42"),
])
def test_cross_origin_and_deletes_stay_blocked(monkeypatch, method, url):
    guard, _ = _transport(monkeypatch, participate=True)
    route = _route(method, url, b"{}")
    guard(route)
    route.fulfill.assert_not_called()


@pytest.mark.parametrize("path", ["/complete", "/questionnaire_submit_events", "/answer_submit_events/1"])
def test_without_participant_mode_completion_endpoints_stay_blocked_even_for_reads(monkeypatch, path):
    guard, _ = _transport(monkeypatch, participate=False)
    route = _route("GET", API + path)
    guard(route)
    route.fulfill.assert_not_called()


def test_oversized_write_is_blocked(monkeypatch):
    guard, _ = _transport(monkeypatch, participate=True)
    route = _route("POST", API + "/responses", b"x" * (256 * 1024 + 1))
    guard(route)
    route.fulfill.assert_not_called()


def test_without_participant_mode_writes_stay_blocked_and_are_explained(monkeypatch):
    guard, _ = _transport(monkeypatch, participate=False)
    route = _route("POST", API + "/online_sign_in_events", b"{}")
    guard(route)
    route.fulfill.assert_not_called()
    assert not guard.coverage.participated
    assert any("participant" in warning for warning in guard.coverage.warnings)


def test_participant_mode_permits_external_next_but_test_mode_rules_are_unchanged():
    assert external_progression_stop(allow_test_local=False, participate=True) is False
    assert external_progression_stop(allow_test_local=False, participate=False) is True
    assert external_progression_stop(allow_test_local=True, participate=False) is False


def test_app_issued_session_token_is_forwarded_but_proxy_credentials_never_are(monkeypatch):
    guard, connection = _transport(monkeypatch, participate=True)
    guard(_route("GET", START, headers={"authorization": "Bearer app-token", "proxy-authorization": "Basic secret"}))
    sent = {key.lower(): value for key, value in connection.request.call_args.kwargs["headers"].items()}
    assert sent["authorization"] == "Bearer app-token"
    assert "proxy-authorization" not in sent


def test_multiple_session_cookies_survive_fulfill(monkeypatch):
    guard, connection = _transport(monkeypatch, participate=True)
    connection.getresponse.return_value.getheaders.return_value = [
        ("content-type", "text/html"), ("Set-Cookie", "a=1; Secure"), ("Set-Cookie", "b=2; Secure")]
    route = _route("GET", START)
    guard(route)
    assert route.fulfill.call_args.kwargs["headers"]["set-cookie"] == "a=1; Secure\nb=2; Secure"


def test_flaky_download_is_retried_once_and_logged_without_link(monkeypatch, caplog):
    import socket
    guard, connection = _transport(monkeypatch, participate=True)
    good = connection.getresponse.return_value
    connection.getresponse.side_effect = [socket.timeout("timed out"), good]
    route = _route("GET", START + "chunk.js")
    guard(route)
    route.fulfill.assert_called_once()
    assert "timeout" in caplog.text.lower() and "redjade" not in caplog.text


def test_failed_write_is_never_retried(monkeypatch):
    import socket
    guard, connection = _transport(monkeypatch, participate=True)
    connection.getresponse.side_effect = [socket.timeout("timed out"), connection.getresponse.return_value]
    route = _route("POST", API + "/questionnaire_submit_events", b"{}")
    guard(route)
    route.fulfill.assert_not_called()
    assert connection.request.call_count == 1


def test_corporate_route_tolerates_slow_downloads(monkeypatch):
    import http.client
    guard, _ = _transport(monkeypatch, participate=True)
    guard(_route("GET", START))
    assert http.client.HTTPSConnection.call_args.kwargs["timeout"] >= 15
