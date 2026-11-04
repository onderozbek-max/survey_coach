"""Focused Improve contracts, intercepted synthetic payloads only."""
import pytest

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
    assert page.get_by_label('Saved text for manual copy', exact=True).input_value() == writes[-1]['picked_text']
    assert page.locator('#use-change').is_visible()
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


def test_signal_route_intersects_page_and_fingerprints_and_stays_scoped(browser, base_url):
    def prepare(detail):
        picks = curated(detail)
        for f in picks:
            f['page_id'] = detail['screens'][0]['page_id']
            f['question_id'] = None
        picks[2]['page_id'] = detail['screens'][1]['page_id']
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    items = detail['plan']['must_fix']
    page.evaluate("o => SC.goChapter('improve', o)", dict(page_id=detail['screens'][0]['page_id'],
        fingerprints=[items[1]['id'], items[2]['id']]))
    assert page.locator('#coach h3').inner_text() == items[1]['headline']
    page.locator('#skip').click()
    assert page.locator('#coach h3').inner_text() == 'Nothing more in this view'
    page.evaluate("o => SC.goChapter('improve', o)", dict(page_id=detail['screens'][0]['page_id']))
    assert page.locator('#coach h3').inner_text() == items[0]['headline']
    page.locator('#skip').click()
    assert page.locator('#coach h3').inner_text() == items[1]['headline']
    page.locator('#skip').click()
    assert page.locator('#coach h3').inner_text() == items[0]['headline']
    page.evaluate("o => SC.goChapter('improve', o)", dict(fingerprints=[]))
    assert page.locator('#coach h3').inner_text() == 'Nothing more in this view'
    assert not writes and not errors
    context.close()


def hold_puts(page):
    page.evaluate("""() => {
      window.pendingPuts = []; window.putCalls = [];
      const original = window.fetch;
      window.fetch = (url, options) => {
        if (options?.method !== 'PUT') return original(url, options);
        putCalls.push(JSON.parse(options.body));
        return new Promise(resolve => pendingPuts.push(() => resolve(new Response(options.body, {status:200}))));
      };
    }""")


def test_pending_lock_survives_replacement_controls(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    hold_puts(page)
    page.locator('#use-change').click()
    assert page.locator('#use-change').is_disabled()
    assert page.locator('#keep-as-is').is_disabled()
    page.evaluate("document.querySelector('#use-change').dispatchEvent(new MouseEvent('click'))")
    page.get_by_role('tab', name='More ideas', exact=True).click()
    page.get_by_role('tab', name='Must-fix 0/3', exact=True).click()
    assert page.locator('#use-change').is_disabled()
    assert page.evaluate('putCalls.length') == 1
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    assert page.locator('#use-change').is_enabled()
    assert not errors
    context.close()


@pytest.mark.parametrize('pending_count, changed_index', [(2, 0), (3, 0), (2, 2)])
def test_pattern_superseded_earlier_row_stops_before_later_write_or_copy(browser, base_url, pending_count, changed_index):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=pattern)
    page.get_by_role('tab', name='More ideas', exact=True).click()
    hold_puts(page)
    page.evaluate("navigator.clipboard.writeText('unchanged')")
    page.locator('#use-all').click()
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function('putCalls.length === 2')
    if pending_count == 3:
        page.evaluate('pendingPuts.shift()()')
        page.wait_for_function('putCalls.length === 3')
    assert page.locator('.pattern-row .keep-as-is').first.is_disabled()
    # Simulate an authoritative newer edit arriving outside the locked panel.
    fp = detail['plan']['more'][0]['fingerprints'][changed_index]
    page.evaluate("fp => { SC.decisionRevisions.set(fp, 2); SC.workspaceDetail.decisions[fp] = {action:'keep', reason:'Newer choice'}; }", fp)
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("n => document.querySelector('#toast')?.textContent.includes(`${n} of 3`)", arg=pending_count)
    assert page.evaluate('putCalls.length') == pending_count
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged'
    page.locator('#undo').click()
    restores = pending_count - (changed_index < pending_count)
    for index in range(1, restores + 1):
        page.wait_for_function('n => putCalls.length === n', arg=pending_count + index)
        assert page.evaluate('putCalls.at(-1).action') == 'open'
        page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('restored')")
    assert page.evaluate('SC.workspaceDetail.decisions')[fp]['reason'] == 'Newer choice'
    assert not errors
    context.close()


def test_pattern_keyboard_row_focus_survives_pending_success_failure_and_undo(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=pattern)
    page.get_by_role('tab', name='More ideas', exact=True).click()
    hold_puts(page)
    page.locator('.pattern-row .use-change').first.focus()
    page.keyboard.press('Enter')
    assert page.locator('.pattern-row').first.locator('h4').first.evaluate('e => e === document.activeElement')
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    assert page.locator('.pattern-row').first.locator('h4').first.evaluate('e => e === document.activeElement')
    page.locator('#undo').click()
    page.wait_for_function('pendingPuts.length === 1')
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Previous decisions restored')")
    assert page.locator('.pattern-row').first.locator('h4').first.evaluate('e => e === document.activeElement')
    page.locator('.pattern-row .keep-as-is').nth(1).focus()
    page.keyboard.press('Enter')
    page.keyboard.press('Enter')
    assert page.locator('.pattern-row').nth(1).locator('h4').first.evaluate('e => e === document.activeElement')
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Kept on purpose')")
    assert page.locator('.pattern-row').nth(1).locator('h4').first.evaluate('e => e === document.activeElement')
    assert page.evaluate('putCalls[2].reason') == 'Intentional for this study'
    # A real failed PUT must also restore the affected row's focus.
    page.evaluate("window.fetch = async () => new Response('{}', {status:503})")
    page.locator('.pattern-row .use-change').nth(2).focus()
    page.keyboard.press('Enter')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('could not be saved')")
    assert page.locator('.pattern-row').nth(2).locator('h4').first.evaluate('e => e === document.activeElement')
    assert not errors
    context.close()


def test_signal_route_selects_server_tab_without_rebuilding_pattern(browser, base_url):
    def prepare(detail):
        pattern(detail)
        # An unrelated item appears first on the same page in another tier.
        row = detail['plan']['more'][0]
        detail['plan']['must_fix'] = [dict(row, id='unrelated', count=1,
            fingerprints=[row['fingerprints'][0]], headline='Unrelated signal')]
        detail['plan']['counts']['must_fix'] = 1
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    item = detail['plan']['more'][0]
    f = next(f for f in detail['review']['findings'] if f['fingerprint'] == item['fingerprints'][1])
    page.evaluate("o => SC.goChapter('improve', o)", dict(fingerprints=[f['fingerprint']], page_id=f['page_id']))
    assert page.get_by_role('tab', name='More ideas', exact=True).get_attribute('aria-selected') == 'true'
    assert page.locator('#coach h3').inner_text() == item['headline']
    assert page.locator('.pattern-row').count() == item['count']
    assert page.locator('.pattern-row').evaluate_all('rows => rows.map(r => r.dataset.fingerprint)') == item['fingerprints']
    assert not writes and not errors
    context.close()
