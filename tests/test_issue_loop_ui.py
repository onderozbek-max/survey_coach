"""Isolated browser contracts. Synthetic intercepted detail; no saved/live reviews touched."""
from pathlib import Path

from surveycoach.rubric import load_rubric
from surveycoach.server.present import enrich
from tests.test_site_e2e import base_url, browser
from tests.site_helpers import go_to

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
    fingerprints = {}
    for index, finding in enumerate(detail['review']['findings']):
        fingerprints[finding['fingerprint']] = f'fingerprint-{index}'
        finding['fingerprint'] = f'fingerprint-{index}'
    for finding in detail['review']['findings']:
        if finding.get('also_affects'):
            finding['also_affects'] = [fingerprints[fp] for fp in finding['also_affects']]
        if finding.get('absorbed_by'):
            finding['absorbed_by'] = fingerprints[finding['absorbed_by']]
    for group in ('must_fix', 'quick_wins', 'more'):
        for item in detail['plan'][group]:
            item['fingerprints'] = [fingerprints[fp] for fp in item['fingerprints']]
    overview = detail['overview']       # items and cards point at findings by fingerprint: keep them in step
    for item in overview['items']:
        item['fingerprints'] = [fingerprints.get(fp, fp) for fp in item.get('fingerprints', [])]
    for signal in overview['signals']:
        if signal.get('navigation'):
            signal['navigation']['fingerprints'] = [fingerprints.get(fp, fp) for fp in signal['navigation']['fingerprints']]
    detail['round_changes'] = {'fixed': [], 'still': [], 'new': [], 'uncertain': []}
    metadata = page.evaluate('({criteria:SURVEYCOACH_DEMO.criteria, dimensions:SURVEYCOACH_DEMO.dimensions, ai_batches:SURVEYCOACH_DEMO.ai_batches})')
    if prepare:
        prepare(detail)
    rubric = load_rubric()

    def derive():
        """The server rebuilds queue, plan and My changes from the decisions on every read; so does this stand-in.
        A test's own screen names and page fields (e.g. an injected stimulus_text, which enrich re-derives from the
        page's text and media) stay as the test set them."""
        screens, snapshot = detail['screens'], detail['snapshot']
        detail.update(enrich(detail, rubric))
        detail['screens'], detail['snapshot'] = screens, snapshot
    derive()
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
            derive()
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


def test_adding_a_change_saves_only_after_an_explicit_action_and_feeds_the_tray(browser, base_url):
    """2B: Use became Add to my changes. It saves and moves on; copying is its own explicit button."""
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = next(f for f in detail['review']['findings'] if f.get('suggested_text') or f.get('options'))
    focus(page, finding)
    assert page.get_by_role('tab').count() == 0                 # one ordered list, no tabs
    assert page.locator('#coach .card').count() == 1
    assert not writes                                          # looking never saves
    assert page.locator('#tray-toggle').inner_text().startswith('My changes (0)')
    page.locator('#coach .use-change').first.click()
    page.wait_for_function("document.querySelector('#tray-toggle').textContent.startsWith('My changes (1)')")
    assert writes[-1]['action'] == 'pick'
    assert writes[-1]['revision'] == 1
    assert writes[-1]['client_id']
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    page.locator('#tray-toggle').click()
    page.locator('#tray-copy-all').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.startsWith('Copied')")
    assert page.evaluate('navigator.clipboard.readText()') == page.evaluate('SC.workspaceDetail.my_changes.copy_all_text')
    assert writes[-1]['picked_text'] in page.evaluate('navigator.clipboard.readText()')
    page.locator('#all-screens').click()
    assert page.locator('#screen-drawer select, #screen-drawer textarea').count() == 0
    assert page.locator('#screen-drawer').get_by_text('Ask the coach').count() == 0
    assert 'fingerprint-' not in page.locator('#screen-drawer').inner_text()
    page.get_by_role('button', name='Close all screens').click()
    go_to(page, 'share')
    assert page.locator('#change-list .diff').count() == 1
    page.locator('#copy-all').click()
    page.wait_for_function("navigator.clipboard.readText().then(t => t.includes('Replace with:'))")
    sheet = page.evaluate('navigator.clipboard.readText()')
    assert 'Find:' in sheet and writes[-1]['picked_text'] in sheet
    assert not errors
    context.close()


def test_keep_needs_a_reason_chip_and_mobile_finish_loop(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390)
    finding = next(f for f in detail['review']['findings'] if not f.get('suggested_text') and not f.get('options'))
    focus(page, finding)
    page.get_by_role('button', name='Keep as is…', exact=True).click()
    assert page.get_by_role('button', name='Keep as is', exact=True).is_disabled()      # no reason chip, no save
    assert not writes
    page.get_by_role('button', name='Intentional', exact=True).click()
    page.get_by_role('button', name='Keep as is', exact=True).click()
    page.wait_for_function("document.querySelector('#toast') !== null")
    focus(page, finding)
    page.wait_for_function("document.querySelector('.fix-handled') !== null")
    assert writes[-1]['action'] == 'keep'
    assert writes[-1]['keep_reason'] == 'intentional'
    assert 'Kept as is' in page.locator('.fix-handled').inner_text()
    assert 'accepted risk' in page.locator('#decision-verdict').inner_text()
    assert page.locator('#copy-all').is_disabled()
    page.locator('#check-again').click()
    assert page.locator('#survey-link').input_value() == detail['snapshot']['source_url']
    assert not page.locator('#snapshot').is_visible()
    page.locator('#recheck-cancel').click()
    go_to(page, 'improve')
    page.get_by_role('button', name='Rename survey', exact=True).click()
    page.get_by_role('textbox', name='Survey name', exact=True).fill('Member experience round')
    page.get_by_role('button', name='Save', exact=True).click()
    page.wait_for_function("document.querySelector('#review-title').textContent === 'Member experience round'")
    go_to(page, 'share')
    assert page.locator('.round-timeline a').count() == 2
    assert 'no longer flagged' in page.locator('.round-comparison').inner_text()
    assert '/versions/2/summary?download=1' in page.locator('#download-summary').get_attribute('href')
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


def test_a_late_add_does_not_overwrite_a_newer_keep(browser, base_url):
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
    page.locator('#coach .use-change').first.click()
    page.wait_for_function("document.querySelector('#coach .issue-save-status')?.textContent === 'Saving…'")
    assert pending
    # Controls stay locked while a save runs; emulate a newer authoritative edit instead.
    assert page.locator('#coach .decision-actions button, #coach .fix-handled button').evaluate_all('bs => bs.every(b => b.disabled)')
    page.evaluate("""async fp => {
      SC.decisionRevisions.set(fp, 2);
      const response = await fetch(`/api/surveys/synthetic/versions/2/decisions/${fp}`, {
        method:'PUT', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'keep', keep_reason:'owner_decided', reason:'Stakeholder requirement', revision:2, client_id:SC.decisionClient})});
      SC.workspaceDetail.decisions[fp] = await response.json();
      dispatchEvent(new CustomEvent('surveycoach-decisions', {detail:SC.workspaceDetail}));
    }""", finding['fingerprint'])
    pending[0].fulfill(json=pending[0].request.post_data_json)
    page.wait_for_timeout(300)
    assert writes[-1]['action'] == 'keep'
    assert writes[-1]['revision'] == 2
    assert page.locator('#tray-toggle').inner_text().startswith('My changes (0)')       # the stale add never reached My changes
    assert not errors
    context.close()


def test_failed_save_changes_nothing_and_round_evidence_is_readable(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = next(f for f in detail['review']['findings'] if f.get('suggested_text') or f.get('options'))
    focus(page, finding)
    page.route('**/decisions/*', lambda route: route.fulfill(status=503, json={'detail': 'Unavailable'}))
    page.locator('#coach .use-change').first.click()
    page.locator('#coach .fix-error').wait_for()
    assert 'Not saved' in page.locator('#coach .fix-error').inner_text()
    assert page.locator('#tray-toggle').inner_text().startswith('My changes (0)')
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
