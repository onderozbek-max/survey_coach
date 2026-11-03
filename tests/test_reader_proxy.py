"""Corporate proxy is an explicit trusted transport, never a caller-selected destination."""
import socket
from unittest.mock import Mock

import pytest

from surveycoach.reader.models import Coverage
from surveycoach.reader.policy import UnsafeSurveyURL
from surveycoach.reader.transport import GuardedTransport


@pytest.mark.parametrize("asset_size", [24, 6 * 1024 * 1024])
def test_approved_proxy_resolves_target_at_proxy_and_keeps_tls_hostname(monkeypatch, asset_size):
    monkeypatch.setenv("SURVEYCOACH_CORPORATE_PROXY", "http://proxy-intlho.wal-mart.com:8080")
    def dns(host, *args, **kwargs):
        assert host != "app.redjade.net", "Target DNS must be handled by the corporate proxy"
        return [(socket.AF_INET, 1, 6, "", ("10.0.0.10", 8080))]
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = b"x" * asset_size
    connection.getresponse.return_value.getheaders.return_value = [("content-type", "application/javascript")]
    factory = Mock(return_value=connection)
    monkeypatch.setattr("http.client.HTTPSConnection", factory)
    guard = GuardedTransport("https://app.redjade.net/surveys/test/", local=False, approval=True, coverage=Coverage())
    route = Mock()
    route.request.url = "https://app.redjade.net/surveys/test/"
    route.request.method = "GET"
    route.request.headers = {}
    guard(route)
    factory.assert_called_once_with("proxy-intlho.wal-mart.com", 8080, timeout=3)
    connection.set_tunnel.assert_called_once_with("app.redjade.net", 443)
    route.fulfill.assert_called_once()


@pytest.mark.parametrize("proxy", ["http://evil.example:8080", "http://user:secret@proxy-intlho.wal-mart.com:8080", "http://127.0.0.1:8080"])
def test_arbitrary_proxy_configuration_is_rejected(monkeypatch, proxy):
    monkeypatch.setenv("SURVEYCOACH_CORPORATE_PROXY", proxy)
    with pytest.raises(UnsafeSurveyURL):
        GuardedTransport("https://app.redjade.net/test", local=False, approval=True, coverage=Coverage())


def test_corporate_route_gets_more_patience_than_direct(monkeypatch):
    """Fonts/assets via the corporate proxy take seconds; 3s screenshot waits flaked."""
    import time
    from surveycoach.reader.session import patience
    monkeypatch.setenv("SURVEYCOACH_CORPORATE_PROXY", "http://proxy-intlho.wal-mart.com:8080")
    proxied = GuardedTransport("https://app.redjade.net/surveys/a/b/", local=False, approval=True, coverage=Coverage())
    local = GuardedTransport("http://127.0.0.1:9000/start", local=True, approval=False, coverage=Coverage())
    assert patience(proxied) == 5 and patience(local) == 1
    assert proxied.deadline - time.monotonic() > 250
    assert local.deadline - time.monotonic() < 100
