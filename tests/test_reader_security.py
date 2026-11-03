"""Pure policy tests: no DNS resolution or live requests."""
import pytest

from surveycoach.reader import UnsafeSurveyURL, validate_url


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "javascript:alert(1)", "data:text/html,hi",
    "http://localhost/a", "http://127.0.0.1/a", "https://127.1/",
    "https://10.0.0.1/", "https://172.16.0.1/", "https://192.168.1.2/",
    "https://169.254.169.254/latest/meta-data", "https://[::1]/",
    "https://[::ffff:127.0.0.1]/", "https://metadata.google.internal/",
    "https://example.com/", "https://redjade.net.evil.test/",
    "https://evilredjade.net/", "https://user:secret@sensory.redjade.net/a",
    "https://sensory.redjade.net:444/a", "http://sensory.redjade.net/a",
    "https://sensory.redjade.net/a?token=secret", "https://sensory.redjade.net/a#secret",
    "https://sensory.redjade.net/a?enc=secret", "https://sensory.redjade.net/a?member_id=123",
    "https://sensory.redjade.net/a\\@127.0.0.1/", " https://sensory.redjade.net/a",
])
def test_unsafe_url_is_denied_without_echoing_it(url):
    with pytest.raises(UnsafeSurveyURL) as error:
        validate_url(url, approval=True)
    assert url not in str(error.value)
    assert "secret" not in str(error.value)


def test_explicit_approval_is_required():
    with pytest.raises(UnsafeSurveyURL, match="approval"):
        validate_url("https://sensory.redjade.net/survey/example")


def test_redjade_https_and_nonsecret_survey_path_are_allowed():
    url = "https://sensory.redjade.net/survey/example"
    assert validate_url(url, approval=True) == url


def test_local_escape_hatch_only_allows_literal_loopback():
    assert validate_url("http://127.0.0.1:8765/a", allow_test_local=True).endswith("/a")
    assert validate_url("http://[::1]:8765/a", allow_test_local=True).endswith("/a")
    for url in ("http://10.0.0.2/a", "http://localhost/a", "http://169.254.169.254/a"):
        with pytest.raises(UnsafeSurveyURL):
            validate_url(url, allow_test_local=True)


def test_test_mode_cannot_enable_external_requests():
    with pytest.raises(UnsafeSurveyURL):
        validate_url("https://sensory.redjade.net/survey/example", allow_test_local=True, approval=True)
