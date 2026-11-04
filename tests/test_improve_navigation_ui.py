"""Phone and decision stay in context; keyboard controls survive rendering."""
from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser


def test_pager_selects_first_open_plan_item_on_destination_screen(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('[data-fk=next]').click()
    location = page.locator('#coach .location').first
    if location.count():
        assert location.inner_text().split(' · ')[0] == page.locator('#stage .phone-bar').inner_text().split(' · ')[0]
    assert not writes and not errors
    context.close()


def test_queue_mode_and_energy_keyboard_activation_retains_focus(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    mode = page.get_by_role('button', name='With changes', exact=True)
    mode.focus()
    page.keyboard.press('Enter')
    assert mode.evaluate('e => e === document.activeElement')
    bar = page.locator('#improve-bar .energy-bar').nth(3)
    bar.focus()
    page.keyboard.press('Space')
    assert bar.evaluate('e => e === document.activeElement')
    assert detail['screens'][3]['name'] in page.locator('#stage .phone-bar').inner_text()
    assert not writes and not errors
    context.close()


def test_drawer_screen_without_findings_has_valid_labelled_panel(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('#all-screens').click()
    page.locator('#screen-drawer .screen-row').last.click()
    assert page.locator('#coach-h').count() == 1
    assert not writes and not errors
    context.close()
