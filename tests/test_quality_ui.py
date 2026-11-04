"""Synthetic browser evidence; no network survey, AI, or persistent user data."""
import pytest

from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser


@pytest.mark.parametrize('width', [390, 1280])
def test_score_context_methodology_keyboard_and_energy_tap(browser, base_url, width):
    context, page, detail, writes, errors = open_review(browser, base_url, width=width, chapter='overview')
    card = page.locator('#chapter-overview .quality-card')
    assert card.is_visible()
    assert 'coverage' in card.inner_text().lower()
    assert str(round(detail['quality']['score'])) in card.inner_text()
    trigger = card.get_by_role('button', name='How quality is calculated')
    trigger.click()
    dialog = page.get_by_role('dialog', name='Quality methodology')
    assert dialog.is_visible()
    assert 'assessed applicable points' in dialog.inner_text()
    assert 'old raw score' in dialog.inner_text().lower()
    page.keyboard.press('Tab')
    assert dialog.get_by_role('button', name='Close').evaluate('el => el === document.activeElement')
    page.keyboard.press('Escape')
    assert trigger.evaluate('el => el === document.activeElement')
    page.get_by_role('button', name='About the energy map').click()
    energy = page.get_by_role('dialog', name='Energy map estimates')
    for text in ['0.3', '180', '420', '10 questions', '20 questions', 'Uncalibrated', 'captured']:
        assert text in energy.inner_text()
    page.keyboard.press('Escape')
    assert page.get_by_role('button', name='About the energy map').evaluate('el => el === document.activeElement')
    assert page.locator('#survey-style').evaluate("el => Boolean(el.compareDocumentPosition(document.querySelector('.quality-card')) & Node.DOCUMENT_POSITION_FOLLOWING)")
    assert 'does not rerun saved AI advice' in page.locator('#survey-style').inner_text()
    page.locator('[data-chapter=improve]').click()
    assert page.locator('#topbar .quality-compact').inner_text() == page.locator('#chapter-overview .quality-context').inner_text()
    page.locator('[data-chapter=share]').click()
    assert page.locator('#share-quality .quality-compact').is_visible()
    page.get_by_role('button', name='Quality methodology', exact=True).click()
    assert dialog.is_visible()
    page.keyboard.press('Escape')
    assert page.evaluate("(() => {const ids=[...document.querySelectorAll('[id]')].map(el=>el.id);return ids.length===new Set(ids).size})()")
    assert not writes and not errors
    context.close()


def test_null_and_provisional_quality_do_not_claim_perfect_score(browser, base_url):
    def prepare(detail):
        detail['quality'] = dict(score=None, coverage_percent=0, provisional=True,
                                 assessed_points=0, applicable_points=100, unchecked_points=100,
                                 blockers={'flagged':0, 'unchecked':2})
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview', prepare=prepare)
    text = page.locator('.quality-card').inner_text()
    assert 'Not assessed' in text and 'Provisional' in text and '0% coverage' in text
    assert '2 risk checks unverified' in text
    assert '100/100' not in text
    assert not writes and not errors
    context.close()


def test_home_compact_score_and_footer_methodology_use_supplied_evidence(browser, base_url):
    context = browser.new_context(viewport={'width':390, 'height':844})
    page = context.new_page()
    quality = dict(score=82.4, coverage_percent=76, provisional=True)
    page.route('**/api/surveys', lambda route: route.fulfill(json={'surveys':[
        dict(id='synthetic', title='Synthetic only', version=1, created_at='2026-11-04 00:00:00',
             quality=quality, signals=[], job={'status':'completed'}, must_fix=2, ready_to_share=False)]}))
    page.route('**/api/reader/mode', lambda route: route.fulfill(json={}))
    page.goto(base_url + 'local.html')
    compact = page.locator('.survey-card .quality-compact')
    assert compact.inner_text() == 'Survey Quality · 82/100 · Provisional · 76% coverage'
    assert page.locator('.survey-card button').count() == 0  # no nested interactive link controls
    trigger = page.get_by_role('button', name='Quality methodology', exact=True)
    trigger.click()
    page.get_by_role('dialog', name='Quality methodology').get_by_role('button', name='Close').click()
    assert trigger.evaluate('el => el === document.activeElement')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    context.close()


def test_methodology_reopen_route_closing_and_sample_header(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview')
    trigger = page.get_by_role('button', name='How quality is calculated')
    for _ in range(2):
        trigger.click()
        page.keyboard.press('Shift+Tab')
        assert page.get_by_role('dialog').get_by_role('button', name='Close').evaluate('el => el === document.activeElement')
        page.keyboard.press('Escape')
        assert trigger.evaluate('el => el === document.activeElement')
    trigger.click()
    page.evaluate("SC.goChapter('improve')")
    assert page.locator('dialog[open]').count() == 0
    assert page.locator('#improve-h').evaluate('el => el === document.activeElement')
    page.goto(base_url + 'index.html#improve')
    page.wait_for_function('SC.reviewReady === true')
    assert page.locator('#topbar .quality-compact').is_visible()
    assert 'coverage' in page.locator('#topbar .quality-compact').inner_text()
    assert not errors
    context.close()


@pytest.mark.parametrize('width', [390, 1280])
def test_energy_tooltip_hover_focus_escape_and_full_formula(browser, base_url, width):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview', width=width)
    trigger = page.get_by_role('button', name='About the energy map')
    tooltip = page.get_by_role('tooltip')
    trigger.hover()
    assert tooltip.is_visible()
    assert trigger.get_attribute('aria-describedby') == tooltip.get_attribute('id')
    assert 'Bar height' in tooltip.inner_text() and 'cumulative' in tooltip.inner_text()
    assert page.locator('dialog[open]').count() == 0
    tooltip.hover()
    assert tooltip.is_visible()  # pointer can move onto the explanation
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.keyboard.press('Escape')
    assert not tooltip.is_visible()
    page.mouse.move(0, 0)
    trigger.focus()
    assert tooltip.is_visible()
    assert page.locator('dialog[open]').count() == 0
    page.keyboard.press('Escape')
    assert not tooltip.is_visible()
    assert trigger.evaluate('el => el === document.activeElement')
    page.keyboard.press('Enter')
    dialog = page.get_by_role('dialog', name='Energy map estimates')
    assert dialog.is_visible()
    assert 'each question image and each answer option with media adds 3s' in dialog.inner_text()
    assert not tooltip.is_visible()
    page.keyboard.press('Escape')
    assert trigger.evaluate('el => el === document.activeElement')
    assert not tooltip.is_visible()
    page.keyboard.press('Tab')
    trigger.focus()
    assert tooltip.is_visible()
    page.keyboard.press('Tab')
    assert not tooltip.is_visible()
    assert not writes and not errors
    context.close()


def test_energy_touch_opens_full_dialog_without_hover_dependency(browser, base_url):
    context = browser.new_context(viewport={'width':390, 'height':844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    page.goto(base_url + 'index.html#overview')
    page.wait_for_function('SC.reviewReady === true')
    trigger = page.get_by_role('button', name='About the energy map')
    assert not page.get_by_role('tooltip').is_visible()
    trigger.tap()
    dialog = page.get_by_role('dialog', name='Energy map estimates')
    assert dialog.is_visible()
    assert 'answer option with media' in dialog.inner_text()
    assert not page.get_by_role('tooltip').is_visible()
    dialog.get_by_role('button', name='Close').tap()
    assert trigger.evaluate('el => el === document.activeElement')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    context.close()
