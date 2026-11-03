"""No external sockets: DNS answers are synthetic and routes are test doubles."""
import socket

import pytest

from surveycoach.reader import Coverage, UnsafeSurveyURL
from surveycoach.reader.policy import public_addresses
from surveycoach.reader.transport import GuardedTransport
from surveycoach.reader.session import external_progression_stop


@pytest.mark.parametrize("addresses,allowed", [
    ([], False), (["8.8.8.8"], True), (["8.8.8.8", "127.0.0.1"], False),
    (["224.0.0.1"], False), (["ff02::1"], False),
    (["10.1.2.3"], False), (["169.254.169.254"], False), (["::1"], False),
    (["::ffff:8.8.8.8"], False), (["garbage"], False),
])
def test_public_dns_requires_every_address_to_be_public(addresses, allowed):
    assert public_addresses(addresses) is allowed


def test_private_dns_is_rejected_before_browser_launch(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(UnsafeSurveyURL, match="public"):
        GuardedTransport("https://sensory.redjade.net/survey/example", local=False,
                         approval=True, coverage=Coverage())


def test_dns_failure_is_url_free(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("secret DNS diagnostics")
    monkeypatch.setattr(socket, "getaddrinfo", unavailable)
    with pytest.raises(UnsafeSurveyURL) as error:
        GuardedTransport("https://sensory.redjade.net/survey/example", local=False,
                         approval=True, coverage=Coverage())
    assert "secret" not in str(error.value)


def test_external_next_is_not_trusted_as_nonfinal():
    assert external_progression_stop(allow_test_local=False) is True
    assert external_progression_stop(allow_test_local=True) is False


@pytest.mark.parametrize("url,method", [
    ("http://127.0.0.1:9000/save", "POST"),
    ("http://127.0.0.1:9000/s%75bmit", "GET"),
    ("http://127.0.0.1:9001/a", "GET"),
    ("http://127.0.0.1:9000/a?token=secret", "GET"),
    ("http://169.254.169.254/a", "GET"),
])
def test_denied_requests_never_open_a_socket(url, method, monkeypatch):
    def no_socket(*args, **kwargs):
        pytest.fail("blocked request attempted a socket")
    monkeypatch.setattr(socket, "create_connection", no_socket)

    class Request:
        headers = {}

    class Route:
        request = Request()
        blocked = False

        def abort(self, *_):
            self.blocked = True

    route = Route()
    route.request.url, route.request.method = url, method
    coverage = Coverage()
    guard = GuardedTransport("http://127.0.0.1:9000/start", local=True, approval=False, coverage=coverage)
    guard(route)
    assert route.blocked
    assert coverage.blocked_requests == 1
