"""D15: the focus rectangle on the Verdict heading appears only for keyboard-initiated focus (workstream 3B)."""
from tests.journey_helpers import open_verdict
from tests.test_site_e2e import base_url, browser  # noqa: F401  (fixtures)


def ring(page):
    return page.locator('#overview-h').evaluate("el => ({focused: el === document.activeElement, style: getComputedStyle(el).outlineStyle, width: parseFloat(getComputedStyle(el).outlineWidth)})")


def test_no_stray_ring_on_load_or_after_a_mouse_navigation(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url, width=1440)
    state = ring(page)
    assert state['focused'] and (state['style'] == 'none' or state['width'] == 0)       # D15: nothing drawn on page load
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#chapter-nav [data-chapter=overview]').click()
    state = ring(page)
    assert state['focused'] and (state['style'] == 'none' or state['width'] == 0)       # a mouse user gets no box either
    context.close()


def test_the_ring_shows_when_the_keyboard_took_us_there(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url, width=1440)
    page.locator('#chapter-nav [data-chapter=improve]').focus()
    page.keyboard.press('Enter')
    page.locator('#chapter-nav [data-chapter=overview]').focus()
    page.keyboard.press('Enter')
    state = ring(page)
    assert state['focused'] and state['style'] != 'none' and state['width'] >= 2        # keyboard-initiated focus stays visible (WCAG 2.4.7)
    context.close()
