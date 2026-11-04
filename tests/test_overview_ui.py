"""Overview consumes supplied evidence; all writes intercepted, no AI or live DB."""
import pytest

from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser
from tests.test_workflow_e2e import studio


def overview(browser, base_url, **kwargs):
    return open_review(browser, base_url, chapter='overview', **kwargs)


def test_supplied_overview_signals_strengths_and_energy(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url)
    supplied = detail['overview']
    assert page.locator('#overview-headline').inner_text() == supplied['headline']
    assert page.locator('#overview-subline').inner_text() == supplied['subline']
    assert page.locator('#overview-h').inner_text() == detail['title']
    assert page.locator('#signals li[data-signal]').count() == 6
    for signal in supplied['signals']:
        tile = page.locator(f'#signals [data-signal={signal["id"]}]')
        assert tile.locator('.signal-state').inner_text() == signal['label']
        assert tile.locator('.signal-state svg').count() == 1
        assert tile.get_attribute('role') != 'button'
        assert tile.locator('button.signal-link').count() == 1
    assert page.locator('#strengths li').all_text_contents() == supplied['strengths'][:3]
    bars = page.locator('#energy-map button.energy-bar')
    assert bars.count() == len(detail['screens'])
    for i, screen in enumerate(supplied['energy']['screens']):
        label = bars.nth(i).get_attribute('aria-label')
        assert label.startswith(f'{screen["name"]}, about {round(screen["seconds"])} seconds, estimate,')
        assert 'must-fix' in label
        assert bars.nth(i).locator('.energy-label').get_attribute('title') == screen['name']
    assert 'estimate' in page.locator('#energy-map .energy-caption').inner_text()
    assert page.locator('#chapter-overview .btn-primary').get_attribute('id') == 'start-improving'
    assert page.locator('#preview-member.btn-secondary').count() == 1
    assert page.locator('.overview-mini[aria-hidden=true][inert] .phone').count() == 1
    assert page.locator('#chapter-overview').get_by_text('Scope-limited', exact=True).count() == 0
    assert 'checked points' not in page.locator('#chapter-overview').inner_text()
    assert not writes and not errors
    context.close()


def test_signal_energy_and_plan_routes_select_canonical_screen(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url)
    signal = next(s for s in detail['overview']['signals'] if s['pages'])
    page.locator(f'[data-signal={signal["id"]}] .signal-link').click()
    assert page.url.endswith('#improve')
    assert page.evaluate('SC.improveFilter.signal') == signal['id']
    assert detail['screens'][next(i for i,s in enumerate(detail['screens']) if s['page_id'] == signal['pages'][0])]['name'] in page.locator('#stage .phone-bar').inner_text()
    page.locator('[data-chapter=overview]').click()
    page.locator('#energy-map .energy-bar').nth(3).click()
    assert detail['screens'][3]['name'] in page.locator('#stage .phone-bar').inner_text()
    page.locator('[data-chapter=overview]').click()
    page.locator('#plan-summary button').nth(1).click()
    assert page.evaluate('SC.improveFilter.tab') == 'quick_wins'
    assert not writes and not errors
    context.close()


def test_style_refetches_and_generic_title_uses_patch(browser, base_url):
    def prepare(detail):
        detail['title'] = 'Surveys'
        detail['overview']['strengths'] = []
    context, page, detail, writes, errors = overview(browser, base_url, prepare=prepare)
    assert page.locator('#strengths').count() == 0
    assert page.get_by_text('What members will like', exact=True).count() == 0
    assert page.locator('#survey-style input[type=radio]').count() == 5
    requests = []
    page.on('request', lambda r: requests.append((r.method, r.url)))
    page.get_by_label('Community & fun', exact=True).check()
    page.wait_for_function("document.querySelector('#status').textContent === 'Survey style saved'")
    assert writes == [{'survey_type': 'community_pulse'}]
    assert any(method == 'GET' and '/api/surveys/synthetic' in url for method, url in requests)
    page.locator('#name-survey').click()
    page.get_by_role('textbox', name='Survey title', exact=True).fill('Our next idea')
    page.get_by_role('button', name='Save title', exact=True).click()
    page.wait_for_function("document.querySelector('#overview-h').textContent === 'Our next idea'")
    assert writes[-1] == {'title': 'Our next idea'}
    assert not errors
    context.close()


@pytest.mark.parametrize('width', [390, 759, 1280])
def test_responsive_layout_and_primary_action(browser, base_url, width):
    context, page, detail, writes, errors = overview(browser, base_url, width=width)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('.overview-mini').is_visible() == (width >= 760)
    if width < 760:
        assert page.locator('.energy-swipe').is_visible()
        assert page.locator('.overview-actions').evaluate("el => getComputedStyle(el).position") == 'fixed'
        assert page.locator('#signals').evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 1
    else:
        assert page.locator('#signals').evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 3
    page.locator('#start-improving').click()
    assert page.url.endswith('#improve')
    assert not writes and not errors
    context.close()


def test_dialog_scrub_pause_escape_and_visibility_cleanup(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now() + 1000'))
    page.locator('#preview-member').click()
    dialog = page.get_by_role('dialog', name='Preview as a member')
    assert dialog.is_visible()
    assert dialog.locator('.phone').evaluate('el => el.getBoundingClientRect().width') == 390
    page.get_by_role('button', name='Pause', exact=True).click()
    page.clock.run_for(100000)
    assert dialog.locator('.energy-bar[aria-current=step]').get_attribute('data-page') == 'p0'
    dialog.locator('.energy-bar').nth(2).click()
    assert 'Q2' in dialog.locator('.phone-bar').inner_text()
    page.get_by_role('button', name='Play', exact=True).click()
    page.clock.run_for(15000)
    assert 'Q3' in dialog.locator('.phone-bar').inner_text()
    page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))")
    assert page.get_by_role('button', name='Play', exact=True).is_visible()
    before = dialog.locator('.phone-bar').inner_text()
    page.clock.run_for(100000)
    assert dialog.locator('.phone-bar').inner_text() == before
    page.keyboard.press('Escape')
    assert not dialog.is_visible()
    assert page.locator('#preview-member').evaluate('el => el === document.activeElement')
    page.clock.run_for(100000)
    assert not writes and not errors
    context.close()


def test_high_energy_uses_canonical_name_and_sparse_labels(browser, base_url):
    def prepare(detail):
        screens = detail['overview']['energy']['screens']
        screens[0].update(name='Q8–Q18', zone='high', seconds=188)
        screens.extend([{**screens[0], 'page_id': f'extra-{i}', 'screen': 14 + i} for i in range(3)])
    context, page, detail, writes, errors = overview(browser, base_url, prepare=prepare)
    first = page.locator('#energy-map .energy-bar').first
    assert first.get_attribute('aria-label').startswith('Q8–Q18, about 188 seconds, estimate, tiring,')
    assert page.locator('#energy-map .energy-label.sparse').count() == 8
    assert not errors
    context.close()


def test_failed_style_patch_keeps_evidence_and_restores_radio(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url)
    original = page.locator('#overview-headline').inner_text()
    page.route('**/api/surveys/synthetic', lambda r: r.fulfill(status=503, json={'detail':'Style unavailable'}))
    page.get_by_label('Product test', exact=True).check()
    page.wait_for_function("document.querySelector('#status').textContent === 'Style unavailable'")
    assert page.locator('#overview-headline').inner_text() == original
    assert not page.get_by_label('Product test', exact=True).is_checked()
    assert not writes and not errors
    context.close()


def test_dialog_keyboard_trap_close_and_reopen_has_no_duplicate_clock(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now() + 1000'))
    page.locator('#preview-member').click()
    dialog = page.locator('#member-preview')
    page.keyboard.press('Shift+Tab')
    assert dialog.evaluate('el => el.contains(document.activeElement)')
    for _ in range(20):
        page.keyboard.press('Tab')
        assert dialog.evaluate('el => el.contains(document.activeElement)')
    page.get_by_role('button', name='Close preview').click()
    page.clock.run_for(100000)
    page.locator('#preview-member').click()
    page.clock.run_for(5000)
    assert 'Q1' in dialog.locator('.phone-bar').inner_text()
    page.clock.run_for(13000)
    assert 'Q2' in dialog.locator('.phone-bar').inner_text()
    page.get_by_role('button', name='Close preview').click()
    assert page.locator('#member-preview').count() == 0
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('width', [390, 1280])
def test_long_signal_summary_has_keyboard_details(browser, base_url, width):
    summary = 'Supplied evidence, not rewritten. ' * 40 + 'Final evidence remains available.'
    support = 'Captured evidence: Exact saved words, with no invented conclusion.'

    def prepare(detail):
        detail['overview']['signals'][0]['summary'] = summary
        detail['overview']['signals'][0]['details'] = [support, 'Not assessed: Branch-specific pacing']
    context, page, detail, writes, errors = overview(browser, base_url, width=width, prepare=prepare)
    tile = page.locator('#signals > li').first
    preview = tile.locator('.signal-summary')
    assert preview.inner_text() == summary
    assert preview.evaluate('el => el.clientHeight <= 2 * parseFloat(getComputedStyle(el).lineHeight)')
    expansion = tile.locator('details')
    control = expansion.locator('summary')
    assert control.inner_text() == 'Details'
    assert not expansion.get_attribute('open')
    control.focus()
    page.keyboard.press('Enter')
    full = expansion.locator('p').first
    assert full.is_visible() and full.inner_text() == support
    assert summary not in expansion.inner_text()
    assert 'Not assessed: Branch-specific pacing' in expansion.inner_text()
    assert full.evaluate('el => el.clientHeight >= el.scrollHeight')
    assert not preview.is_visible()
    assert control.evaluate('el => el === document.activeElement')
    page.keyboard.press('Space')
    assert not full.is_visible() and preview.is_visible()
    assert not writes and not errors
    context.close()


def test_evidence_details_escape_saved_text_and_do_not_guess_legacy_evidence(browser, base_url):
    quote = 'Captured evidence: <img src=x onerror="window.injected=true">'

    def prepare(detail):
        detail['overview']['signals'][1]['details'] = [quote, 'Not assessed: One idea per question']
        detail['overview']['signals'][2].pop('details', None)
    context, page, detail, writes, errors = overview(browser, base_url, prepare=prepare)
    clarity = page.locator('[data-signal=clarity]')
    clarity.locator('summary').click()
    assert clarity.locator('.signal-details p').first.inner_text() == quote
    assert clarity.locator('.signal-details img').count() == 0
    assert not page.evaluate('Boolean(window.injected)')
    honest = page.locator('[data-signal=honest]')
    honest.locator('summary').click()
    assert honest.locator('.signal-details p').inner_text() == 'No supporting check details were saved.'
    assert not writes and not errors
    context.close()


def test_uncertain_path_qualifies_energy_and_suppresses_elapsed_route(browser, base_url):
    def prepare(detail):
        detail['overview']['energy']['path_uncertain'] = True
    context, page, detail, writes, errors = overview(browser, base_url, prepare=prepare)
    caption = page.locator('#energy-map .energy-caption').inner_text()
    assert 'Captured-screen walkthrough' in caption and 'route uncertain' in caption
    page.locator('#preview-member').click()
    dialog = page.locator('#member-preview')
    page.get_by_role('button', name='Pause', exact=True).click()
    dialog.locator('.energy-bar').nth(2).click()
    timing = dialog.locator('.member-playback').inner_text()
    assert 'route uncertain' in timing and 'Screen estimate:' in timing
    assert 'Elapsed' not in timing
    assert 'route uncertain' in dialog.locator('.energy-caption').inner_text()
    assert 'seconds, estimate,' in dialog.locator('.energy-bar').nth(2).get_attribute('aria-label')
    page.keyboard.press('Escape')
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('key', ['Enter', 'Space'])
def test_keyboard_scrub_restores_page_focus_and_tab_order(browser, base_url, key):
    context, page, detail, writes, errors = overview(browser, base_url)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now() + 1000'))
    page.locator('#preview-member').click()
    dialog = page.locator('#member-preview')
    page.get_by_role('button', name='Pause', exact=True).click()
    bars = dialog.locator('.energy-bar')
    bars.nth(2).focus()
    page.keyboard.press(key)
    assert bars.nth(2).evaluate('el => el === document.activeElement')
    assert bars.nth(2).get_attribute('aria-current') == 'step'
    assert 'Elapsed estimate:' in dialog.locator('.member-playback').inner_text()
    page.keyboard.press('Tab')
    assert bars.nth(3).evaluate('el => el === document.activeElement')
    page.keyboard.press('Shift+Tab')
    assert bars.nth(2).evaluate('el => el === document.activeElement')
    bars.last.focus()
    page.keyboard.press('Tab')
    assert page.get_by_role('button', name='Close preview').evaluate('el => el === document.activeElement')
    page.keyboard.press('Shift+Tab')
    assert bars.last.evaluate('el => el === document.activeElement')
    page.keyboard.press('Escape')
    assert page.locator('#preview-member').evaluate('el => el === document.activeElement')
    assert not writes and not errors
    context.close()


def test_auto_advance_preserves_scrubber_focus_without_stealing_controls(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now() + 1000'))
    page.locator('#preview-member').click()
    dialog = page.locator('#member-preview')
    bars = dialog.locator('.energy-bar')
    bars.nth(2).focus()
    page.clock.run_for(5000)
    assert bars.nth(1).get_attribute('aria-current') == 'step'
    assert bars.nth(2).evaluate('el => el === document.activeElement')
    for control_name in ['Pause', 'Close preview']:
        control = page.get_by_role('button', name=control_name, exact=True)
        control.focus()
        page.clock.run_for(15000)
        assert control.evaluate('el => el === document.activeElement')
    page.keyboard.press('Escape')
    page.clock.run_for(100000)
    assert page.locator('#member-preview').count() == 0
    assert not writes and not errors
    context.close()


def test_style_reprojects_on_temp_server(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#survey-style').wait_for()
    page.get_by_label('Home-use test', exact=True).check()
    page.wait_for_function("SC.workspaceDetail.survey_type === 'ihut'")
    assert page.get_by_label('Home-use test', exact=True).is_checked()
    assert page.get_by_label('Home-use test', exact=True).evaluate('el => el === document.activeElement')
    page.reload()
    page.get_by_label('Home-use test', exact=True).wait_for()
    assert page.get_by_label('Home-use test', exact=True).is_checked()
    page.close()
