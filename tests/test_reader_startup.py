"""Allow only the observed read-only startup schema bound to the input survey."""
import pytest
from surveycoach.reader.policy import request_url, UnsafeSurveyURL

START = "https://app.redjade.net/surveys/demo/example/"


@pytest.mark.parametrize("path", [
    "/static/locales/languages.json?cache=abc123",
    "/static/locales/localized_languages.json?cache=abc123",
    "/static/locales/client.en_US.json?cache=abc123",
    "/api/v1/surveys/event_meta?company_token=demo&static_url=example",
])
def test_readonly_startup_queries_are_tightly_scoped(path):
    assert request_url("https://app.redjade.net" + path, START) == "https://app.redjade.net" + path


@pytest.mark.parametrize("path", [
    "/api/v1/surveys/event_meta?company_token=other&static_url=example",
    "/api/v1/surveys/event_meta?company_token=demo&static_url=example&member=secret",
    "/static/locales/languages.json?cache=abc&token=secret",
    "/other?cache=abc",
    "/api/v1/surveys/event_meta?company_token=demo&company_token=other&static_url=example",
])
def test_unknown_or_cross_survey_queries_remain_blocked(path):
    with pytest.raises(UnsafeSurveyURL):
        request_url("https://app.redjade.net" + path, START)
