"""Hypothetical preview changes wording without accepting or saving decisions."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_preview_changes_immediately_without_writes_and_can_restore_original(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('.phone-screen').wait_for()
    page.get_by_role('tab', name='All issues', exact=True).click()
    card = page.locator('.fix-card').filter(has_text='desktop word').first
    card.get_by_role('button', name='See on the phone', exact=False).click()
    before = page.locator('.phone-screen').inner_text()
    writes = []
    page.on('request', lambda request: writes.append(request.url) if request.method == 'PUT' else None)
    page.get_by_role('button', name='With fixes', exact=True).click()
    assert page.locator('.phone-screen').inner_text() != before
    assert 'Tap the one you like best.' in page.locator('.phone-screen').inner_text()
    assert 'not accepted or saved' in page.locator('.preview-effect').inner_text()
    assert not writes
    page.get_by_role('button', name='Current', exact=True).click()
    assert page.locator('.phone-screen').inner_text() == before
    coach = page.locator('.card').filter(has_text='desktop word').first
    coach.get_by_text('Your original', exact=True).click()
    page.wait_for_timeout(100)
    assert page.get_by_role('button', name='With fixes', exact=True).is_disabled()
    assert page.locator('.phone-screen').inner_text() == before
    page.reload()
    page.locator('.phone-screen').wait_for()
    page.get_by_role('tab', name='All issues', exact=True).click()
    card = page.locator('.fix-card').filter(has_text='desktop word').first
    assert card.locator('select').input_value() == 'original'
    page.close()
