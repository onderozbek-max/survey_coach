"""Share contracts on intercepted synthetic reviews; no vendor or saved data access."""
import pytest

from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser
from tests.site_helpers import open_how_we_check, open_recheck


def chosen(detail):
    findings = detail['review']['findings']
    picks = [f for f in findings if not f.get('absorbed_by') and f.get('question_id')][:3]
    for i, f in enumerate(picks):
        detail['decisions'][f['fingerprint']] = {'action': 'pick', 'picked_text': f'Chosen wording {i}'}
    picks[1]['edit_kind'] = 'add_answer'
    detail['decisions'][picks[2]['fingerprint']]['stale_pick'] = True
    keep = next(f for f in findings if f not in picks and not f.get('absorbed_by'))
    detail['decisions'][keep['fingerprint']] = {'action': 'keep', 'reason': 'Required for comparability'}
    detail['plan']['must_fix'] = [
        {'id': 'chosen', 'fingerprints': [picks[0]['fingerprint']]},
        {'id': 'kept', 'fingerprints': [keep['fingerprint']]},
        {'id': 'open', 'fingerprints': [picks[2]['fingerprint']]}]
    detail['plan']['counts']['must_fix'] = 3
    return picks, keep


def test_share_explicit_grouped_changes_copy_and_kept_reasons(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share', prepare=chosen)
    assert page.locator('#share-summary').inner_text() == '2 changes chosen · 1 kept on purpose · 1 to fix before launch still open'
    assert page.locator('#change-list li').count() == 2
    expected = {s['name'] for s in detail['screens'] if any(
        f.get('page_id') == s['page_id'] or any(q['id'] == f.get('question_id') for q in s['questions'])
        for f in detail['review']['findings'] if detail['decisions'].get(f['fingerprint'], {}).get('picked_text') in ('Chosen wording 0', 'Chosen wording 1'))}
    assert set(page.locator('#change-list h3').all_text_contents()) == expected
    assert page.locator('#change-list .diff').count() == 1
    addition = page.locator('#change-list li').filter(has_text='Add answer option')
    assert addition.locator('del').count() == 0
    assert 'Keep question:' in addition.inner_text()
    page.locator('#kept-reasons summary').click()
    assert 'Required for comparability' in page.locator('#kept-reasons').inner_text()
    assert 'accepted risk, not verified fixes' in page.locator('#kept-reasons').inner_text()
    assert page.locator('#chapter-share .btn-primary').count() == 1
    assert page.locator('#copy-all').is_visible()
    addition.get_by_role('button', name='Copy change', exact=True).click()
    page.wait_for_function("document.querySelector('#action-status').textContent.includes('Copied')")
    text = page.evaluate('navigator.clipboard.readText()')
    assert 'Add answer option: Chosen wording 1' in text and 'Replace with:' not in text
    page.locator('#copy-all').click()
    page.wait_for_function("navigator.clipboard.readText().then(t => t.includes('Chosen wording 0'))")
    text = page.evaluate('navigator.clipboard.readText()')
    assert 'Chosen wording 1' in text and 'Chosen wording 2' not in text
    assert 'Required for comparability' not in text
    assert 'fingerprint-' not in text and detail['snapshot']['source_url'] not in text
    assert page.locator('#download-summary').get_attribute('href') == '/api/surveys/synthetic/versions/2/summary?download=1'
    assert not writes and not errors
    context.close()


def test_share_zero_changes_and_honest_version_evidence(browser, base_url):
    def prepare(detail):
        detail['round_changes'] = {'fixed': [{'headline': 'Earlier issue', 'resolution': 'Wording changed', 'old_wording': 'Before', 'new_wording': 'After'}], 'still': [], 'new': [], 'uncertain': [{'reason': 'Path not comparable'}]}
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share', width=390, prepare=prepare)
    assert page.locator('#copy-all').is_hidden()
    assert page.locator('#change-list li').count() == 0
    assert page.get_by_role('heading', name='Since version 1', exact=True).is_visible()
    assert '1 no longer flagged' in page.locator('#version-changes').inner_text()
    assert 'not blanket verification' in page.locator('#version-changes').inner_text()
    assert '#share' in page.locator('.round-timeline a').first.get_attribute('href')
    open_how_we_check(page)
    assert 'not launch approval' in page.get_by_role('dialog', name='How we check').inner_text()
    page.keyboard.press('Escape')
    open_recheck(page)
    assert page.locator('#survey-link').input_value() == detail['snapshot']['source_url']
    assert "The next check compares with the latest saved version, not necessarily the version displayed here." in page.locator('#recheck-form').inner_text()
    page.keyboard.press('Escape')
    timeline = page.get_by_role('navigation', name='Review versions', exact=True)
    assert timeline.get_by_role('link', name='Version 1', exact=True).is_visible()
    assert timeline.get_by_role('link', name='Version 2', exact=True).get_attribute('aria-current') == 'page'
    assert 'round' not in page.locator('#chapter-share').inner_text().lower()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('url', ['https://tests.redjade.net/preview/test?token=secret', 'https://tests.redjade.net/preview/test#secret', 'https://user:secret@tests.redjade.net/preview/test', 'https://evil.example/secret'])
def test_share_never_prefills_or_echoes_unsafe_source(browser, base_url, url):
    def prepare(detail):
        detail['source_url'] = url
        detail['snapshot']['source_url'] = url
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share', prepare=prepare)
    open_recheck(page)
    assert page.locator('#survey-link').input_value() == ''
    assert 'secret' not in page.locator('#chapter-share').inner_text()
    requests = []
    page.on('request', lambda req: requests.append(req) if req.method == 'POST' else None)
    page.locator('#survey-link').fill(url)
    page.locator('#recheck-form button[type=submit]').click()
    assert 'valid HTTPS RedJade test link' in page.locator('#import-status').inner_text()
    assert not requests and not writes and not errors
    context.close()


@pytest.mark.parametrize('version', [1, 2])
def test_historical_share_recheck_discloses_latest_baseline_and_opens_result(browser, base_url, version):
    def prepare(detail):
        detail['version'] = version
        detail['versions'] = [{'version': n} for n in (1, 2, 3)]
        detail['round_changes'] = None
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share', prepare=prepare)
    page.goto(base_url + f'review.html?id=synthetic&version={version}#share')
    page.wait_for_function('SC.reviewReady === true')
    assert page.locator('#download-summary').get_attribute('href') == f'/api/surveys/synthetic/versions/{version}/summary?download=1'
    open_recheck(page)
    assert 'latest saved version, not necessarily the version displayed here' in page.locator('#recheck-form').inner_text()
    assert 'compare it with this version' not in page.locator('#recheck-form').inner_text()
    assert 'round' not in page.locator('#chapter-share').inner_text().lower()
    payloads = []
    def reader(route):
        payloads.append(route.request.post_data_json)
        route.fulfill(json={'job_id': 'historical-job'})
    page.route('**/api/reader/jobs', reader)
    page.route('**/api/jobs/historical-job', lambda r: r.fulfill(json={
        'status': 'completed', 'survey_id': 'synthetic', 'version': 4}))
    page.get_by_role('button', name='Check updated survey', exact=True).click()
    page.wait_for_url('**/review.html?id=synthetic&version=4')
    assert payloads == [{'url': detail['snapshot']['source_url'], 'approval': True, 'ai': True, 'survey_id': 'synthetic'}]
    assert not writes and not errors
    context.close()


def test_share_recheck_uses_existing_reader_job_and_preserves_version(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share')
    payloads = []
    def reader(route):
        payloads.append(route.request.post_data_json)
        route.fulfill(json={'job_id': 'synthetic-job'})
    page.route('**/api/reader/jobs', reader)
    page.route('**/api/jobs/synthetic-job', lambda r: r.fulfill(json={'status': 'failed', 'error': 'Synthetic stop; prior version unchanged'}))
    open_recheck(page)
    page.locator('#recheck-form button[type=submit]').click()
    page.wait_for_function("document.querySelector('#import-status').textContent.includes('prior version unchanged')")
    assert payloads == [{'url': detail['snapshot']['source_url'], 'approval': True, 'ai': True, 'survey_id': 'synthetic'}]
    assert page.url.endswith('id=synthetic#share')
    assert not writes and not errors
    context.close()
