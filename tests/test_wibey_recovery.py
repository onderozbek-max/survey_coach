"""Local Wibey recovery: no real authentication or external traffic."""
import pytest
from surveycoach.llm.recovery import classify_failure, start_authentication


@pytest.mark.parametrize('detail,expected', [
    ('HTTP 401 unauthorized: token expired', 'auth'),
    ('Not authenticated. Run wibey --auth', 'auth'),
    ('getaddrinfo ENOTFOUND service.internal', 'network'),
    ('connect ETIMEDOUT', 'network'),
    ('invalid JSON', 'other'),
    ('request timed out', 'other'),
    ('HTTP 403 forbidden', 'other'),
])
def test_evidence_based_failure_classification(detail, expected):
    assert classify_failure(detail) == expected


def test_network_and_unknown_failures_never_start_auth(monkeypatch):
    import surveycoach.llm.recovery as module
    monkeypatch.setattr(module, 'start_authentication', lambda binary: pytest.fail('unexpected authentication'))
    assert 'VPN' in str(module.failure_error('ENOTFOUND', 'wibey'))
    assert 'No sign-in was started' in str(module.failure_error('invalid JSON', 'wibey'))


def test_auth_failure_starts_cli_and_returns_only_safe_guidance(monkeypatch):
    import surveycoach.llm.recovery as module
    calls = []
    monkeypatch.setattr(module, 'start_authentication', lambda binary: calls.append(binary) or True)
    error = module.failure_error('HTTP 401 token expired https://secret.invalid/token', '/trusted/wibey')
    assert calls == ['/trusted/wibey']
    assert '--auth' in str(error) and 'secret.invalid' not in str(error)


def test_auth_is_background_singleflight_and_never_captures_secrets(monkeypatch):
    import surveycoach.llm.recovery as module
    calls = []
    class Process:
        def poll(self): return None
    monkeypatch.setattr(module, '_auth_process', None)
    monkeypatch.setattr(module, '_auth_started', 0)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda command, **kwargs: (calls.append((command, kwargs)) or Process()))
    monkeypatch.setattr(module, '_schedule_expiry', lambda process: None)
    assert start_authentication('/trusted/wibey')
    assert start_authentication('/trusted/wibey')
    assert len(calls) == 1
    assert calls[0][0] == ['/trusted/wibey', '--auth']
    assert calls[0][1]['stdout'] == module.subprocess.DEVNULL
    assert calls[0][1]['stderr'] == module.subprocess.DEVNULL
