"""Checking a survey is one click: AI included, no blocking confirmation dialog."""
import pytest

from tests.test_site_e2e import browser
from tests.site_helpers import open_how_we_check, go_to
from tests.test_workflow_e2e import studio


@pytest.mark.parametrize("value", ["https://example.com/not-redjade", "not-a-url", "https://app.redjade.net/test?member=secret"])
def test_invalid_links_are_explained_before_any_reader_request(browser, studio, value):
    page = browser.new_page()
    page.set_default_timeout(10000)
    page.goto(studio + "/local.html")
    requests = []
    page.route("**/api/reader/jobs", lambda route: (requests.append(route.request.url), route.abort()))
    page.get_by_label("RedJade preview link").fill(value)
    page.get_by_role("button", name="Check survey", exact=True).click()
    page.get_by_text("Use a valid HTTPS RedJade test link without credentials, query parameters, or a fragment.", exact=True).wait_for(timeout=3000)
    assert not requests
    page.close()


def test_link_start_to_saved_review_preserves_partial_coverage(browser, studio, monkeypatch, tmp_path):
    from pathlib import Path
    from surveycoach.reader.models import Capture, Coverage, ReadResult
    from surveycoach.snapshot import SurveySnapshot
    import surveycoach.server.reader as reader_api
    calls = []

    def rendered_capture(page_id):
        # Captured screens are the persisted rendered captures (0B); a bare counter proves nothing.
        image, observation = tmp_path / f'{page_id}.png', tmp_path / f'{page_id}.json'
        image.write_bytes(b'synthetic-png-test')
        observation.write_text('{}')
        return Capture(page_id=page_id, viewport_png=image, observation_json=observation)

    def controlled(url, **kwargs):
        calls.append(kwargs)
        return ReadResult(
            snapshot=SurveySnapshot.model_validate_json((Path(__file__).parents[1] / 'fixtures/boxer-briefs.json').read_text()),
            coverage=Coverage(pages_captured=3, stop_reason='path_end'), capture_dir=tmp_path,
            captures=[rendered_capture(page_id) for page_id in ('p0', 'p1', 'p2')])

    monkeypatch.setenv('SURVEYCOACH_PARTICIPANT_MODE', '1')
    monkeypatch.setattr(reader_api, 'read_survey', controlled)
    page = browser.new_page()
    page.set_default_timeout(10000)
    page.goto(studio + '/local.html')
    page.get_by_label('RedJade preview link').fill('https://example.redjade.net/test')
    page.get_by_role('button', name='Check survey', exact=True).click()
    page.wait_for_url('**/review.html?**', timeout=30000)
    go_to(page, 'improve')
    for reload in (False, True):
        if reload:
            page.reload()
        go_to(page, 'improve')
        page.locator('#all-screens').click()
        jump = page.locator('.screen-row').first
        jump.wait_for(state='visible')
        jump.click()
        page.locator('#coach .card').wait_for()
        open_how_we_check(page)
        summary = page.get_by_role('dialog', name='How we check')
        assert '3 captured screens checked' in summary.inner_text()
        assert 'Reached the end of the observed path.' in summary.inner_text()
        assert 'Unvisited branches and uncaptured screens were not checked.' in summary.inner_text()
        assert 'not launch approval' in summary.inner_text()
        assert 'path_end' not in summary.inner_text()
        summary.get_by_text('Technical details & source evidence', exact=True).click()
        assert 'Reader stop code: path_end' in summary.inner_text()
        assert summary.get_by_role('link', name='Captured screen').count() == 3
        page.keyboard.press('Escape')
    assert len(calls) == 1
    options = calls[0]
    assert options['approval'] is True and options['participate'] is True
    assert callable(options['on_capture'])
    assert set(options) == {'approval', 'participate', 'on_capture'}
    page.close()


def test_start_has_no_checkboxes_or_confirmation_and_includes_ai(browser, studio):
    page = browser.new_page()
    page.set_default_timeout(10000)
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
    page.get_by_role("button", name="Check survey", exact=True).click()
    page.get_by_text("Synthetic test: no external request made", exact=True).wait_for()
    assert not dialogs
    assert submitted[0]["ai"] is True and submitted[0]["approval"] is True
    page.close()
