"""Focused Improve contracts, intercepted synthetic payloads only."""
from tests.test_issue_loop_ui import open_review, focus
from tests.test_site_e2e import base_url, browser


def curated(detail):
    findings = detail['review']['findings']
    picks = [f for f in findings if f.get('suggested_text') or f.get('options')][:3]
    detail['plan'] = dict(must_fix=[dict(id=f['fingerprint'], fingerprints=[f['fingerprint']],
        headline=f['headline'], count=1, tier='must_fix', screen=1, decided=False) for f in picks],
        quick_wins=[], more=[], counts=dict(must_fix=3, quick_wins=0, more=0, open_must_fix=3))
    return picks


def test_queue_saves_copies_advances_and_undo_reopens(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    assert page.locator('#queue-tabs [role=tab]').all_inner_texts() == ['Must-fix 0/3', 'Quick wins 0/0', 'More ideas']
    assert page.locator('#rail, .journey, #review-toolbar, .next-issue').count() == 0
    assert page.locator('#coach .location').inner_text() in page.locator('#stage .phone-bar').inner_text()
    assert page.locator('#coach .pill').first.inner_text() == 'Must-fix'
    assert page.locator('#coach details.more').count() == 1
    assert page.locator('.studio').evaluate('e => getComputedStyle(e).columnGap') == '48px'
    columns = page.locator('.studio').evaluate('e => getComputedStyle(e).gridTemplateColumns').split()
    assert 340 <= float(columns[0].removesuffix('px')) <= 400
    assert page.locator('#coach .card > :first-child').get_attribute('class') == 'location'
    first = page.locator('#coach h3.headline').inner_text()
    assert not writes
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied. Paste it into RedJade.')")
    assert writes[-1]['action'] == 'pick' and writes[-1]['revision'] == 1 and writes[-1]['client_id']
    assert page.evaluate('navigator.clipboard.readText()') == writes[-1]['picked_text']
    assert page.locator('#coach h3.headline').inner_text() != first
    assert page.locator('#coach h3.headline').evaluate('e => e === document.activeElement')
    assert page.locator('#status').inner_text().startswith('Next: ')
    page.locator('#undo').click()
    page.wait_for_function("document.querySelector('#queue-tabs [role=tab]').textContent === 'Must-fix 0/3'")
    assert writes[-1]['action'] == 'open' and writes[-1]['revision'] == 2
    assert not errors
    context.close()


def test_keep_requires_reason_skip_does_not_save_and_drawer_searches_labels(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    first = page.locator('#coach h3.headline').inner_text()
    page.locator('#keep-as-is').click()
    assert not writes
    page.get_by_role('button', name='Other…', exact=True).click()
    page.get_by_role('button', name='Save reason', exact=True).click()
    assert not writes
    page.get_by_label('Reason for keeping', exact=False).fill('Required for comparability')
    page.get_by_role('button', name='Save reason', exact=True).click()
    page.wait_for_function("document.querySelector('#queue-tabs [role=tab]').textContent === 'Must-fix 1/3'")
    assert writes[-1]['reason'] == 'Required for comparability'
    assert page.locator('#coach h3.headline').inner_text() != first
    page.locator('#skip').click()
    assert len(writes) == 1
    page.locator('#all-screens').click()
    drawer = page.get_by_role('dialog', name='All screens')
    assert drawer.is_visible()
    screen = detail['screens'][2]
    drawer.get_by_role('searchbox').fill(screen['name'])
    assert drawer.locator('.screen-row:visible').count() >= 1
    drawer.locator('.screen-row:visible').first.click()
    assert not drawer.is_visible()
    assert screen['name'] in page.locator('#stage .phone-bar').inner_text()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors
    context.close()


def test_clipboard_failure_is_honest_and_keeps_saved_decision(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    page.evaluate("() => { navigator.clipboard.writeText = async () => {throw Error('denied')}; }")
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copy unavailable')")
    assert writes[-1]['action'] == 'pick'
    assert 'Copied.' not in page.locator('#toast').inner_text()
    assert page.locator('#undo').is_visible()
    assert not errors
    context.close()


def pattern(detail):
    picks = curated(detail)
    detail['plan']['must_fix'] = []
    detail['plan']['more'] = [dict(id='pattern-test', fingerprints=[f['fingerprint'] for f in picks],
        headline='Shared wording pattern', count=3, tier='nice_to_have', screen=1, decided=False)]
    detail['plan']['counts'].update(must_fix=0, more=1, open_must_fix=0)


def test_pattern_individual_writes_and_undo_restores_prior_objects(browser, base_url):
    def prepare(detail):
        pattern(detail)
        fp = detail['plan']['more'][0]['fingerprints'][0]
        detail['decisions'][fp] = dict(action='keep', reason='Tracker', manual_done=True)
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    page.get_by_role('tab', name='More ideas', exact=True).click()
    assert page.locator('.pattern-row .suggested').count() == 3
    assert page.locator('.pattern-row .use-change').count() == 3
    page.locator('#use-all').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    assert len(writes) == 3 and all(w['action'] == 'pick' for w in writes)
    page.locator('#undo').click()
    page.wait_for_timeout(200)
    assert len(writes) == 6
    assert writes[3]['action'] == 'keep' and writes[3]['reason'] == 'Tracker' and writes[3]['manual_done'] is True
    assert [w['action'] for w in writes[4:]] == ['open', 'open']
    assert not errors
    context.close()


def test_pattern_partial_save_never_claims_all_success(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=pattern)
    page.get_by_role('tab', name='More ideas', exact=True).click()
    failing = detail['plan']['more'][0]['fingerprints'][1]
    page.route('**/decisions/' + failing, lambda r: r.fulfill(status=503, json={}))
    page.evaluate("navigator.clipboard.writeText('unchanged')")
    page.locator('#use-all').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('1 of 3')")
    assert len(writes) == 1
    assert 'Copied.' not in page.locator('#toast').inner_text()
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged'
    page.locator('#undo').click()
    page.wait_for_timeout(100)
    assert writes[-1]['action'] == 'open'
    assert not errors
    context.close()


def test_stale_alternatives_absorbed_and_completed_section(browser, base_url):
    def prepare(detail):
        picks = curated(detail)
        picks[0]['options'] = [dict(text='New recommended', label='Precise'), dict(text='Short text')]
        picks[0]['also_affects'] = [detail['review']['findings'][-1]['fingerprint']]
        detail['decisions'][picks[0]['fingerprint']] = dict(action='open', stale_pick=True)
        for item in detail['plan']['must_fix'][1:]:
            detail['decisions'][item['id']] = dict(action='keep', reason='Tracker')
            item['decided'] = True
        detail['plan']['counts']['open_must_fix'] = 1
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    assert page.locator('#queue-tabs [role=tab]').first.inner_text() == 'Must-fix 2/3'
    assert page.get_by_text('We improved this suggestion since you chose it. Choose again.', exact=True).is_visible()
    assert page.locator('.also-affects').inner_text().endswith(detail['review']['findings'][-1]['headline'])
    assert page.locator('.alternatives button').all_inner_texts() == ['Precise', 'Shorter']
    page.get_by_role('button', name='Shorter', exact=True).click()
    assert not writes
    page.locator('#use-change').click()
    page.get_by_role('heading', name='All 3 must-fixes handled', exact=True).wait_for()
    assert writes[-1]['picked_text'] == 'Short text'
    assert page.get_by_role('button', name='Continue to quick wins', exact=True).is_visible()
    assert page.get_by_role('button', name='Go to Share', exact=True).is_visible()
    assert not errors
    context.close()
