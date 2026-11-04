"""Isolated browser contracts. Synthetic intercepted detail; no saved/live reviews touched."""
from pathlib import Path

from tests.test_site_e2e import base_url, browser

SITE = Path(__file__).parent.parent / 'site'


def open_review(browser, base_url, width=1280, chapter='improve', prepare=None):
    context = browser.new_context(viewport={'width': width, 'height': 900},
                                  permissions=['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    page.goto(base_url + 'data.js')
    page.add_script_tag(url=base_url + 'data.js')
    detail = page.evaluate('structuredClone(SURVEYCOACH_DEMO.surveys[0])')
    detail.update(id='synthetic', version=2, versions=[{'version': 1}, {'version': 2}], decisions={})
    detail['snapshot']['source_url'] = 'https://tests.redjade.net/preview/synthetic'
    for index, finding in enumerate(detail['review']['findings']):
        finding['fingerprint'] = f'fingerprint-{index}'
    detail['round_changes'] = {'fixed': [], 'still': [], 'new': [], 'uncertain': []}
    metadata = page.evaluate('({criteria:SURVEYCOACH_DEMO.criteria, dimensions:SURVEYCOACH_DEMO.dimensions, ai_batches:SURVEYCOACH_DEMO.ai_batches})')
    if prepare:
        prepare(detail)
    writes = []
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def api(route):
        url = route.request.url
        if url.endswith('/api/metadata'):
            route.fulfill(json=metadata)
        elif '/decisions/' in url:
            payload = route.request.post_data_json
            writes.append(payload)
            fingerprint = url.rsplit('/', 1)[-1]
            detail['decisions'][fingerprint] = payload
            route.fulfill(json=payload)
        elif route.request.method == 'PATCH':
            payload = route.request.post_data_json
            writes.append(payload)
            detail.update(payload)
            route.fulfill(json=payload)
        else:
            route.fulfill(json=detail)
    page.route('**/api/**', api)
    page.goto(base_url + f'review.html?id=synthetic#{chapter}')
    page.wait_for_function('SC.reviewReady === true')
    return context, page, detail, writes, errors


def open_overview(browser, base_url, width=1280):
    return open_review(browser, base_url, width=width, chapter='overview')


def focus(page, finding):
    page.evaluate("fingerprint => dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:fingerprint}))", finding['fingerprint'])
    page.locator('#coach .card').wait_for()


def test_contextual_use_copies_only_after_explicit_choice(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = next(f for f in detail['review']['findings'] if f.get('suggested_text') or f.get('options'))
    focus(page, finding)
    assert page.get_by_role('tab').count() == 0
    assert page.locator('#coach .card').count() == 1
    assert not writes
    assert page.locator('#copy-all').inner_text() == 'Copy all changes (0)'
    page.locator('#coach .issue-rewrite .btn').first.click()
    page.wait_for_function("document.querySelector('#copy-all').textContent === 'Copy all changes (1)'")
    assert writes[-1]['action'] == 'pick'
    assert writes[-1]['revision'] == 1
    assert writes[-1]['client_id']
    page.wait_for_function("document.querySelector('.issue-save-status').textContent.includes('Copied')")
    assert page.evaluate('navigator.clipboard.readText()') == writes[-1]['picked_text']
    page.locator('#issues-view > summary').click()
    assert page.locator('#fix-list select, #fix-list textarea, #fix-list input').count() == 0
    assert page.locator('#fix-list').get_by_text('Ask the coach').count() == 0
    assert 'fingerprint-' not in page.locator('#fix-list').inner_text()
    page.locator('.change-sheet > summary').click()
    sheet = page.locator('.change-sheet pre').inner_text()
    assert 'Find:' in sheet and 'Replace with:' in sheet
    assert writes[-1]['picked_text'] in sheet
    assert not errors
    context.close()


def test_action_only_keep_requires_reason_and_mobile_finish_loop(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390)
    finding = next(f for f in detail['review']['findings'] if not f.get('suggested_text') and not f.get('options'))
    focus(page, finding)
    page.get_by_role('button', name='Keep mine', exact=True).click()
    page.get_by_role('button', name='Save reason & keep mine').click()
    assert not writes
    page.get_by_role('button', name='Intentional research design', exact=True).click()
    page.get_by_role('button', name='Save reason & keep mine').click()
    page.wait_for_function("document.querySelector('.accepted-risk') !== null")
    assert writes[-1]['action'] == 'keep'
    assert writes[-1]['reason'] == 'Intentional research design'
    assert 'accepted risk' in page.locator('#decision-verdict').inner_text()
    assert page.locator('#copy-all').is_disabled()
    page.locator('#check-again').click()
    assert page.locator('#survey-link').input_value() == detail['snapshot']['source_url']
    assert not page.locator('#snapshot').is_visible()
    page.get_by_role('button', name='Rename', exact=True).click()
    page.get_by_role('textbox', name='Survey title', exact=True).fill('Member experience round')
    page.get_by_role('button', name='Save title', exact=True).click()
    page.wait_for_function("document.querySelector('#review-title').textContent === 'Member experience round'")
    assert page.locator('.round-timeline a').count() == 2
    assert 'no longer flagged' in page.locator('.round-comparison').inner_text()
    assert '/versions/2/summary' in page.locator('#sign-off').get_attribute('href')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors
    context.close()


def test_issue_tiers_locations_and_risk_are_shared_helpers(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    result = page.evaluate('''() => {
      const d = {snapshot:{pages:[{id:'hash-page',questions:[{id:'hash-q',options:[]},{id:'second',options:[]}]}]}, review:{findings:[]}, decisions:{}};
      const f = {fingerprint:'x', criterion_id:'9.1', severity:'worth_improving', question_id:'second'};
      d.review.findings = [f];
      const place = SC.issueLocation(f,d.snapshot);
      d.decisions.x = {action:'keep',reason:''};
      const empty = SC.acceptedRisk(f,d);
      d.decisions.x.reason = 'Required';
      return {tier:SC.issueTier(f),label:place.label,empty,kept:SC.issueCounts(d).kept};
    }''')
    assert result == {'tier': 'polish', 'label': 'Q2 · Screen 1', 'empty': False, 'kept': 1}
    context.close()


def test_stale_use_this_response_does_not_copy_over_newer_keep(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = next(f for f in detail['review']['findings'] if f.get('suggested_text') or f.get('options'))
    focus(page, finding)
    pending = []

    def hold_first(route):
        if not pending:
            pending.append(route)
        else:
            route.fallback()
    page.route('**/decisions/*', hold_first)
    page.evaluate("navigator.clipboard.writeText('unchanged clipboard')")
    page.locator('#coach .issue-rewrite .btn').first.click()
    page.wait_for_timeout(100)
    assert pending
    # Navigating away/back can replace the busy card while a request is pending.
    focus(page, finding)
    page.get_by_role('button', name='Keep mine', exact=True).click()
    page.get_by_role('button', name='Required wording', exact=True).click()
    page.get_by_role('button', name='Save reason & keep mine').click()
    page.wait_for_function("document.querySelector('.accepted-risk') !== null")
    pending[0].fulfill(json=pending[0].request.post_data_json)
    page.wait_for_timeout(100)
    assert writes[-1]['action'] == 'keep'
    assert writes[-1]['revision'] == 2
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged clipboard'
    assert page.locator('#copy-all').is_disabled()
    assert not errors
    context.close()


def test_failed_save_never_copies_and_round_evidence_is_readable(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = next(f for f in detail['review']['findings'] if f.get('suggested_text') or f.get('options'))
    focus(page, finding)
    page.route('**/decisions/*', lambda route: route.fulfill(status=503, json={'detail': 'Unavailable'}))
    page.evaluate("navigator.clipboard.writeText('unchanged clipboard')")
    page.locator('#coach .issue-rewrite .btn').first.click()
    page.wait_for_function("document.querySelector('.issue-save-status').textContent.includes('could not be saved')")
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged clipboard'
    assert page.locator('#copy-all').is_disabled()
    text = page.evaluate('''() => {
      const d = SC.workspaceDetail;
      const f = d.review.findings[0];
      return SC.renderRounds({...d, round_changes:{fixed:[{prior_finding:f,current_finding:null,screen_label:'Q1 · Screen 2',old_wording:'Old question',new_wording:'New question',resolution:'No longer flagged'}],still:[],new:[],uncertain:[]}}, 'synthetic').map(n=>n.textContent).join(' ');
    }''')
    assert 'Q1 · Screen 2' in text
    assert 'Before: Old question' in text and 'Now: New question' in text
    assert 'not blanket verification' in text
    assert not errors
    context.close()
