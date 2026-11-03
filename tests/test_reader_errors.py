"""Browser failures are diagnosable without leaking token-bearing links."""
from surveycoach.reader.session import describe_error


def test_describe_error_keeps_cause_and_strips_links():
    error = TimeoutError("Page.goto: Timeout 60000ms exceeded.\nCall log:\n  - navigating to \"https://app.redjade.net/s/x?token=secret\"")
    text = describe_error(error)
    assert text.startswith("TimeoutError: Page.goto: Timeout 60000ms exceeded.")
    assert "secret" not in text and "redjade" not in text and "Call log" not in text


def test_describe_error_strips_inline_links_and_truncates():
    text = describe_error(RuntimeError("failed at https://app.redjade.net/a?member=42 " + "x" * 500))
    assert "member" not in text and "[link]" in text
    assert len(text) <= 200
