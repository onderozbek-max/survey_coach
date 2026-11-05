"""Phone and decision stay in context; keyboard controls survive rendering."""
from tests.test_issue_loop_ui import focus, open_review, single_paste
from tests.test_site_e2e import base_url, browser


def test_pager_selects_first_open_plan_item_on_destination_screen(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('[data-fk=next]').click()
    location = page.locator('#coach .location').first
    if location.count():
        assert location.inner_text().split(' · ')[0] == page.locator('#stage .phone-bar').inner_text().split(' · ')[0]
    assert not writes and not errors
    context.close()


def test_queue_mode_and_pager_keyboard_activation_retains_focus(browser, base_url):
    """2B: the toolbar energy chart is gone; the screen pager and the mode toggle stay keyboard-operable across re-renders."""
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding, entry = single_paste(detail)
    focus(page, finding)
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    mode = page.get_by_role('button', name='With my changes (1)', exact=True)
    mode.focus()
    page.keyboard.press('Enter')
    assert mode.get_attribute('aria-pressed') == 'true'
    assert mode.evaluate('e => e === document.activeElement')
    before = page.locator('#stage .phone-bar').inner_text()
    pager = page.locator('[data-fk=next]')
    pager.focus()
    page.keyboard.press('Space')
    assert pager.evaluate('e => e === document.activeElement')
    assert page.locator('#stage .phone-bar').inner_text() != before
    assert len(writes) == 1 and not errors                      # only the add wrote
    context.close()


def test_drawer_screen_without_findings_has_valid_labelled_panel(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('#all-screens').click()
    page.locator('#screen-drawer .screen-row').last.click()
    assert page.locator('#coach-h').count() == 1
    assert not writes and not errors
    context.close()
