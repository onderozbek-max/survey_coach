"""Start review is one click: AI included, no blocking confirmation dialog."""
import pytest

from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


@pytest.mark.parametrize("value", ["https://example.com/not-redjade", "not-a-url", "https://app.redjade.net/test?member=secret"])
def test_invalid_links_are_explained_before_any_reader_request(browser, studio, value):
    page = browser.new_page()
    page.goto(studio + "/local.html")
    requests = []
    page.route("**/api/reader/jobs", lambda route: (requests.append(route.request.url), route.abort()))
    page.get_by_label("RedJade preview link").fill(value)
    page.get_by_role("button", name="Start review", exact=True).click()
    page.get_by_text("Use a valid HTTPS RedJade test link without credentials, query parameters, or a fragment.", exact=True).wait_for(timeout=3000)
    assert not requests
    page.close()


def test_link_start_to_saved_review_preserves_partial_coverage(browser, studio, monkeypatch, tmp_path):
    from pathlib import Path
    from surveycoach.reader.models import Coverage, ReadResult
    from surveycoach.snapshot import SurveySnapshot
    import surveycoach.server.reader as reader_api
    calls = []

    def controlled(url, **kwargs):
        calls.append(kwargs)
        return ReadResult(
            snapshot=SurveySnapshot.model_validate_json((Path(__file__).parents[1] / 'fixtures/coffee-pods.json').read_text()),
            coverage=Coverage(pages_captured=3, stop_reason='path_end'), capture_dir=tmp_path)

    monkeypatch.setenv('SURVEYCOACH_PARTICIPANT_MODE', '1')
    monkeypatch.setattr(reader_api, 'read_survey', controlled)
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.get_by_label('RedJade preview link').fill('https://example.redjade.net/test')
    page.get_by_role('button', name='Start review', exact=True).click()
    page.wait_for_url('**/review.html?**', timeout=30000)
    page.get_by_role('tab', name='All issues', exact=True).click()
    page.get_by_role('heading', name='Your fix checklist').wait_for()
    page.locator('details.review-details > summary').filter(has_text='Coverage, checks').click()
    assert 'path_end' in page.locator('body').inner_text()
    assert 'one deterministic path' in page.locator('body').inner_text()
    assert calls == [{'approval': True, 'participate': True}]
    page.reload()
    page.get_by_role('tab', name='All issues', exact=True).click()
    page.get_by_role('heading', name='Your fix checklist').wait_for()
    page.locator('details.review-details > summary').filter(has_text='Coverage, checks').click()
    assert 'path_end' in page.locator('body').inner_text()
    page.close()


def test_start_has_no_checkboxes_or_confirmation_and_includes_ai(browser, studio):
    page = browser.new_page()
    page.goto(studio + "/local.html")
    assert page.locator("input[type=checkbox]").count() == 0
    page.get_by_label("RedJade preview link").fill("https://sample.redjade.net/test")
    submitted = []
    def intercept(route):
        submitted.append(route.request.post_data_json)
        route.fulfill(status=422, content_type="application/json", body='{"detail":"Synthetic test: no external request made"}')
    page.route("**/api/reader/jobs", intercept)
    dialogs = []
    def unexpected_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()
    page.on("dialog", unexpected_dialog)
    page.get_by_role("button", name="Start review", exact=True).click()
    page.get_by_text("Synthetic test: no external request made", exact=True).wait_for()
    assert not dialogs
    assert submitted[0]["ai"] is True and submitted[0]["approval"] is True
    page.close()
