"""Play it as a member: a full-screen, pin-free walk through the phone screens (brief 4.4, workstream 3B)."""
from tests.journey_helpers import add_journey, open_verdict
from tests.test_site_e2e import base_url, browser  # noqa: F401  (fixtures)


def open_dialog(browser, base_url, **kwargs):
    context, page, detail, writes, errors = open_verdict(browser, base_url, **kwargs)
    page.locator('#preview-member').click()
    dialog = page.get_by_role('dialog', name='Play it as a member')
    dialog.wait_for()
    return context, page, detail, writes, errors, dialog


def test_steps_through_every_screen_in_order_with_back_and_next_and_no_pins(browser, base_url):
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url)
    assert dialog.locator('.phone').evaluate('el => el.getBoundingClientRect().width') == 390
    back, nxt = dialog.get_by_role('button', name='Back', exact=True), dialog.get_by_role('button', name='Next', exact=True)
    assert back.is_disabled()
    names = [s['name'] for s in detail['screens']]
    for index, name in enumerate(names):
        assert name in dialog.locator('.phone-bar').inner_text()
        assert dialog.locator('.member-where').inner_text() == f'Screen {index + 1} of {len(names)}'
        assert dialog.locator('.phone-marker, [data-pin], .pin-number').count() == 0                # a member sees no pins
        assert dialog.locator('.phone-gutter > *').count() == 0
        if index < len(names) - 1:
            nxt.click()
    assert nxt.is_disabled()
    back.click()
    assert names[-2] in dialog.locator('.phone-bar').inner_text()
    assert not writes and not errors
    context.close()


def test_the_running_time_is_shown_and_follows_the_screen(browser, base_url):
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url)
    time = dialog.locator('.member-time')
    assert time.inner_text().startswith('Elapsed estimate: about 0:00')
    dialog.get_by_role('button', name='Next', exact=True).click()
    start = detail['presentation']['journey'][1]['running']
    assert f'about {int(round(start)) // 60}:{int(round(start)) % 60:02d}' in time.inner_text()
    context.close()


def test_the_strip_inside_the_dialog_jumps_and_marks_the_current_screen(browser, base_url):
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url)
    dialog.locator('.journey button[data-page]').nth(4).click()
    assert detail['screens'][4]['name'] in dialog.locator('.phone-bar').inner_text()
    assert dialog.locator('.journey button[aria-current=step]').get_attribute('data-page') == detail['presentation']['journey'][4]['page_id']
    assert dialog.locator('.journey button[aria-current=step]').evaluate('el => el === document.activeElement')    # focus stays on the strip
    context.close()


def test_escape_closes_returns_focus_and_reopening_makes_one_dialog(browser, base_url):
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url)
    page.keyboard.press('Escape')
    assert page.locator('#member-preview').count() == 0
    assert page.locator('#preview-member').evaluate('el => el === document.activeElement')
    page.locator('#preview-member').click()
    assert page.locator('#member-preview').count() == 1
    page.get_by_role('button', name='Close preview').click()
    assert page.locator('#member-preview').count() == 0
    assert not writes and not errors
    context.close()


def test_focus_is_trapped_in_the_dialog(browser, base_url):
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url)
    inside = 'document.querySelector("#member-preview").contains(document.activeElement)'
    page.keyboard.press('Shift+Tab')
    assert page.evaluate(inside)
    for _ in range(25):
        page.keyboard.press('Tab')
        assert page.evaluate(inside)
    context.close()


def test_the_time_estimate_explanation_lives_in_an_info_popover(browser, base_url):
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url)
    info = dialog.get_by_role('button', name='About the time estimate')
    info.hover()
    tip = page.get_by_role('tooltip')
    assert 'Segment width' in tip.inner_text() and 'Uncalibrated' in tip.inner_text()
    info.click()
    explain = page.get_by_role('dialog', name='How the time estimate works')
    for text in ['0.3', 'Uncalibrated', 'captured', 'answer option with media']:
        assert text in explain.inner_text()
    assert 'colour' not in explain.inner_text().lower() and 'fatigue' not in explain.inner_text().lower().replace('not measured respondent behaviour', '')
    page.keyboard.press('Escape')
    assert dialog.is_visible() and info.evaluate('el => el === document.activeElement')
    context.close()


def test_an_uncertain_route_is_qualified_and_shows_no_elapsed_route(browser, base_url):
    def uncertain(detail):
        detail['overview']['energy']['path_uncertain'] = True
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url, prepare=uncertain, derived=False)
    text = dialog.locator('.member-time').inner_text()
    assert 'route uncertain' in text and 'Screen estimate:' in text and 'Elapsed' not in text
    context.close()


def test_the_dialog_fits_a_390_screen_without_page_scroll(browser, base_url):
    context, page, detail, writes, errors, dialog = open_dialog(browser, base_url, width=390)
    assert dialog.locator('.phone').evaluate('el => el.getBoundingClientRect().width') <= 390
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert dialog.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
    assert dialog.get_by_role('button', name='Next', exact=True).bounding_box()['height'] >= 44
    context.close()
