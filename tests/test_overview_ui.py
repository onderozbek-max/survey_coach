"""Overview consumes supplied evidence; all writes intercepted, no AI or live DB."""
import pytest

from tests.journey_helpers import add_journey, add_setup, confirm_type_on_patch
from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser
from tests.site_helpers import go_to
from tests.test_workflow_e2e import studio


def overview(browser, base_url, prepare=None, **kwargs):
    def both(detail):
        add_journey(detail)         # what a regenerated site/data.js carries
        if prepare:
            prepare(detail)
    return open_review(browser, base_url, chapter='overview', derived=False, prepare=both, **kwargs)


def test_supplied_overview_signals_strengths_and_energy(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url)
    supplied = detail['overview']
    assert page.locator('#overview-h').inner_text() == supplied['headline']
    assert page.locator('#overview-subline').inner_text() == supplied['subline']
    assert page.locator('#review-title').inner_text() == detail['title']      # the survey name is the page's H1
    assert page.locator('#signals li[data-signal]').count() == 6
    for signal in supplied['signals']:
        tile = page.locator(f'#signals [data-signal={signal["id"]}]')
        assert tile.locator('.signal-state').inner_text() == signal['label']
        assert tile.locator('.signal-state svg').count() == 1
        assert tile.get_attribute('role') != 'button'
        assert tile.locator('button.signal-link').count() == int(bool(signal.get('navigation') and signal['navigation']['fingerprints']))
    assert page.locator('#strengths li').all_text_contents() == supplied['strengths'][:3]
    bars = page.locator('#journey button[data-page]')
    assert bars.count() == len(detail['screens'])
    for i, segment in enumerate(detail['presentation']['journey']):
        assert segment['tooltip'] in bars.nth(i).inner_text()
    assert page.locator('#journey .journey-label').count() >= 1
    assert page.locator('#chapter-overview .btn-primary').get_attribute('id') == 'start-improving'
    assert page.locator('#preview-member.btn-secondary').count() == 1
    assert page.locator('.overview-mini, #chapter-overview .phone').count() == 0     # D15: no unreadable tiny phone
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
    go_to(page, 'overview')
    page.locator('#journey button[data-page]').nth(3).click()
    assert detail['screens'][3]['name'] in page.locator('#stage .phone-bar').inner_text()
    go_to(page, 'overview')
    page.locator('#plan-summary button').nth(0).click()
    assert page.evaluate('SC.improveFilter.state') == 'fix_before_launch'      # 1B tiles route by state, not by tab
    go_to(page, 'overview')
    page.locator('#plan-summary button').nth(1).click()      # Improve opens the Fix flow filtered to Worth improving
    assert page.evaluate('SC.improveFilter.state') == 'worth_improving'
    assert page.locator('#coach .card, #coach [data-fingerprint]').first.is_visible()
    assert not writes and not errors
    context.close()


def test_style_refetches_and_generic_title_uses_patch(browser, base_url):
    def prepare(detail):
        detail['title'] = 'Surveys'
        detail['overview']['strengths'] = []
    context, page, detail, writes, errors = overview(browser, base_url, prepare=lambda d: (prepare(d), add_setup(d)))
    assert page.locator('#strengths').count() == 0
    assert page.get_by_text('What members will like', exact=True).count() == 0
    assert page.locator('#survey-style').count() == 0           # 3B: the type options open from the setup card's Change
    confirm_type_on_patch(page, detail, writes)
    page.locator('#setup-type-change').click()
    assert page.locator('#survey-style input[type=radio]').count() == 5
    requests = []
    page.on('request', lambda r: requests.append((r.method, r.url)))
    page.get_by_label('Community & fun', exact=True).click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Survey type saved'")
    assert writes == [{'survey_type': 'community_pulse'}]
    assert any(method == 'GET' and '/api/surveys/synthetic' in url for method, url in requests)
    assert page.locator('#review-title').inner_text() == 'Untitled survey'      # a generic site title is not a name
    page.locator('#rename-survey').click()
    assert page.get_by_role('textbox', name='Survey name', exact=True).input_value() == ''
    page.get_by_role('textbox', name='Survey name', exact=True).fill('Our next idea')
    page.get_by_role('button', name='Save', exact=True).click()
    page.wait_for_function("document.querySelector('#review-title').textContent === 'Our next idea'")
    assert writes[-1] == {'title': 'Our next idea'}
    assert not errors
    context.close()


@pytest.mark.parametrize('width', [390, 759, 1280])
def test_responsive_layout_and_primary_action(browser, base_url, width):
    context, page, detail, writes, errors = overview(browser, base_url, width=width)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('.overview-mini').count() == 0
    if width < 760:
        assert page.locator('#journey .journey-more').is_visible() == page.locator('#journey .journey-scroll').evaluate('el => el.scrollWidth > el.clientWidth + 1')
        assert page.locator('.overview-actions').evaluate("el => getComputedStyle(el).position") == 'fixed'
        assert page.locator('#signals').evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 1
    else:
        assert page.locator('#signals').evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 3
    page.locator('#start-improving').click()
    assert page.url.endswith('#improve')
    assert not writes and not errors
    context.close()


def test_failed_style_patch_keeps_evidence_and_restores_radio(browser, base_url):
    context, page, detail, writes, errors = overview(browser, base_url, prepare=add_setup)
    original = page.locator('#overview-h').inner_text()
    page.route('**/api/surveys/synthetic', lambda r: r.fulfill(status=503, json={'detail':'Style unavailable'}) if r.request.method == 'PATCH' else r.fallback())
    page.locator('#setup-type-change').click()
    page.get_by_label('Product test', exact=True).click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Style unavailable'")
    assert page.locator('#overview-h').inner_text() == original
    assert page.locator('#setup-card .setup-error').inner_text().startswith('Style unavailable')       # error and a way to retry
    assert page.locator('#setup-retry').is_visible()
    assert not page.get_by_label('Product test', exact=True).is_checked()
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('width', [390, 1280])
def test_long_category_lists_fold_behind_a_keyboard_operable_control(browser, base_url, width):
    long_text = 'This finding headline is deliberately long so it has to wrap inside its card. ' * 3

    def prepare(detail):
        detail['overview']['signals'][0]['items'] = [
            {'kind': 'finding', 'state': 'worth_improving', 'open': True, 'headline': f'{long_text}{i}', 'fingerprints': []}
            for i in range(6)]
    context, page, detail, writes, errors = overview(browser, base_url, width=width, prepare=prepare)
    card = page.locator('#signals > li').first
    assert card.locator('ul.signal-items').first.locator('li').count() == 3        # three shown, the rest folded
    fold = card.locator('details.signal-more')
    control = fold.locator('summary')
    assert control.inner_text() == 'Show 3 more' and not fold.get_attribute('open')
    assert control.bounding_box()['height'] >= 44
    control.focus()
    page.keyboard.press('Enter')
    assert fold.locator('li').count() == 3 and fold.locator('li').first.is_visible()
    assert control.evaluate('el => el === document.activeElement')
    page.keyboard.press('Space')
    assert not fold.locator('li').first.is_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not writes and not errors
    context.close()


def test_card_text_is_escaped_and_cards_without_a_route_have_no_link(browser, base_url):
    quote = '<img src=x onerror="window.injected=true">'

    def prepare(detail):
        detail['overview']['signals'][1]['items'] = [
            {'kind': 'finding', 'state': 'worth_improving', 'open': True, 'headline': quote, 'fingerprints': []}]
        detail['overview']['signals'][2]['navigation'] = None
    context, page, detail, writes, errors = overview(browser, base_url, prepare=prepare)
    clarity = page.locator('[data-signal=clarity]')
    assert clarity.locator('.signal-items li').first.inner_text().endswith(quote)
    assert clarity.locator('img').count() == 0
    assert not page.evaluate('Boolean(window.injected)')
    assert page.locator('[data-signal=honest] .signal-link').count() == 0
    assert not writes and not errors
    context.close()


def test_done_items_are_ticked_and_open_items_name_their_state(browser, base_url):
    def prepare(detail):
        detail['overview']['signals'][0]['items'] = [
            {'kind': 'finding', 'state': 'you_check', 'open': True, 'headline': 'Open one', 'fingerprints': []},
            {'kind': 'finding', 'state': 'worth_improving', 'open': False, 'headline': 'Done one', 'fingerprints': []}]
    context, page, detail, writes, errors = overview(browser, base_url, prepare=prepare)
    rows = page.locator('#signals > li').first.locator('.signal-items li')
    assert ' '.join(rows.nth(0).inner_text().split()) == 'You check: Open one'
    assert ' '.join(rows.nth(1).inner_text().split()) == 'Done: Done one'
    assert rows.nth(0).locator('svg').count() == rows.nth(1).locator('svg').count() == 1
    assert not writes and not errors
    context.close()


def test_absorbed_energy_link_opens_actual_primary_issue(browser, base_url):
    from tests.test_evidence_cards import cross_dimension_detail

    def prepare(detail):
        from surveycoach.server.present import enrich
        from surveycoach.rubric import load_rubric
        supplied = cross_dimension_detail()
        detail['snapshot'] = supplied['snapshot']
        detail['review']['findings'] = supplied['review']['findings']
        detail.update(enrich(detail, load_rubric()))
    context, page, detail, writes, errors = overview(browser, base_url, prepare=prepare)
    page.locator('[data-signal=energy] .signal-link').click()
    assert page.url.endswith('#improve')
    assert page.locator('#coach .card').is_visible()
    assert page.locator('#coach .card [data-fingerprint=primary]').count() == 1      # 2B: the finding sits in the card's collapsed Details
    assert 'Add a valid answer' in page.locator('#coach').inner_text()
    assert 'Nothing more in this view' not in page.locator('#coach').inner_text()
    assert not writes and not errors
    context.close()


def test_style_reprojects_on_temp_server(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#setup-type-change').click()
    page.locator('#survey-style').wait_for()
    page.get_by_label('Home-use test', exact=True).click()
    page.wait_for_function("SC.workspaceDetail.survey_type === 'ihut'")
    page.wait_for_function("SC.workspaceDetail.survey_type_detection.confirmed === true")
    page.reload()
    assert 'Home-use test' in page.locator('#setup-card').inner_text()      # the confirmed type survives a reload
    page.close()
