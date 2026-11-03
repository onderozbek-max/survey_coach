"""Approved test-participant sign-in: exactly one anonymous request, bound to the input survey."""
import json
from unittest.mock import Mock

import pytest

from surveycoach.reader.models import Coverage
from surveycoach.reader.policy import UnsafeSurveyURL, validate_signin
from surveycoach.reader.transport import GuardedTransport

START = "https://app.redjade.net/surveys/demo/example/"
SIGNIN = "https://app.redjade.net/api/v1/surveys/online_sign_in_events"


def body(**changes):
    data = {"participant_code": None, "verification_code": None, "company_token": "demo",
            "static_url": "example", "event_id": 42, "locale": "en_US", "external_id": None, "enc": None}
    data.update(changes)
    return json.dumps(data).encode()


def test_anonymous_signin_for_the_input_survey_is_accepted():
    validate_signin(SIGNIN, body(), START)


@pytest.mark.parametrize("payload", [
    body(company_token="other"), body(static_url="other"), body(participant_code="P123"),
    body(verification_code="999"), body(external_id="member-1"), body(enc="x"),
    body(event_id="42"), body(event_id=True), body(locale="en_US<script>"), body(answers=[1]),
    b"not json", b"",
])
def test_identifying_cross_survey_or_extra_payloads_are_rejected(payload):
    with pytest.raises(UnsafeSurveyURL):
        validate_signin(SIGNIN, payload, START)


@pytest.mark.parametrize("url", [
    "https://app.redjade.net/api/v1/surveys/responses",
    "https://app.redjade.net/api/v1/surveys/online_sign_in_events?x=1",
    "https://other.redjade.net/api/v1/surveys/online_sign_in_events",
])
def test_only_the_exact_signin_endpoint_is_accepted(url):
    with pytest.raises(UnsafeSurveyURL):
        validate_signin(url, body(), START)


def _route(method, url, data=None, headers=None):
    route = Mock()
    route.request.url, route.request.method = url, method
    route.request.headers = headers or {"content-type": "application/json"}
    route.request.post_data = data
    return route


def _transport(monkeypatch, *, test_session):
    monkeypatch.setenv("SURVEYCOACH_CORPORATE_PROXY", "http://proxy-intlho.wal-mart.com:8080")
    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = b'{"ok": true}'
    connection.getresponse.return_value.getheaders.return_value = [("content-type", "application/json")]
    monkeypatch.setattr("http.client.HTTPSConnection", Mock(return_value=connection))
    guard = GuardedTransport(START, local=False, approval=True, coverage=Coverage(), test_session=test_session)
    return guard, connection


def test_signin_is_forwarded_once_then_further_writes_stay_blocked(monkeypatch):
    guard, connection = _transport(monkeypatch, test_session=True)
    first = _route("POST", SIGNIN, body())
    guard(first)
    first.fulfill.assert_called_once()
    assert connection.request.call_args.kwargs["body"] == body()
    assert guard.coverage.test_session_started
    second = _route("POST", SIGNIN, body())
    guard(second)
    second.fulfill.assert_not_called()
    answer = _route("POST", "https://app.redjade.net/api/v1/surveys/responses", b"{}")
    guard(answer)
    answer.fulfill.assert_not_called()


def test_signin_stays_blocked_without_test_session_approval(monkeypatch):
    guard, _ = _transport(monkeypatch, test_session=False)
    route = _route("POST", SIGNIN, body())
    guard(route)
    route.fulfill.assert_not_called()
    assert not guard.coverage.test_session_started


def test_app_issued_session_token_is_forwarded_but_proxy_credentials_never_are(monkeypatch):
    guard, connection = _transport(monkeypatch, test_session=True)
    guard(_route("GET", START, headers={"authorization": "Bearer app-token", "proxy-authorization": "Basic secret"}))
    sent = {key.lower(): value for key, value in connection.request.call_args.kwargs["headers"].items()}
    assert sent["authorization"] == "Bearer app-token"
    assert "proxy-authorization" not in sent


def test_multiple_session_cookies_survive_fulfill(monkeypatch):
    guard, connection = _transport(monkeypatch, test_session=True)
    connection.getresponse.return_value.getheaders.return_value = [
        ("content-type", "text/html"), ("Set-Cookie", "a=1; Secure"), ("Set-Cookie", "b=2; Secure")]
    route = _route("GET", START)
    guard(route)
    assert route.fulfill.call_args.kwargs["headers"]["set-cookie"] == "a=1; Secure\nb=2; Secure"
