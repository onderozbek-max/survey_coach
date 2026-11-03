"""One decision revision sequence across checklist and contextual coach."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_open_is_not_applied_and_action_only_keeps_reason(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('.phone-screen').wait_for()
    page.get_by_role('button', name='With fixes', exact=True).click()
    assert page.get_by_text('Fixed in preview', exact=True).count() == 0
    page.get_by_role('tab', name='All issues', exact=True).click()
    action_only = page.locator('.fix-card').filter(has_text='Action required · No ready-to-use rewrite.').first
    action_only.locator('select').select_option('original')
    reason = action_only.locator('textarea').first
    reason.fill('Intentional research stimulus; keep full image.')
    reason.blur()
    action_only.get_by_text('Saved on this computer.', exact=True).wait_for()
    page.reload()
    action_only = page.locator('.fix-card').filter(has_text='Action required · No ready-to-use rewrite.').first
    assert action_only.locator('select').input_value() == 'original'
    assert 'Intentional research stimulus' in action_only.locator('textarea').first.input_value()
    page.close()


def test_delayed_checklist_save_cannot_overwrite_newer_coach_choice(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('.phone-screen').wait_for()
    page.get_by_role('tab', name='All issues', exact=True).click()
    card = page.locator('.fix-card').filter(has=page.get_by_role('button', name='Copy chosen fix', exact=True)).first
    headline = card.locator('h3').inner_text()
    pending = []
    def hold_first(route):
        if not pending:
            pending.append(route)
        else:
            route.continue_()
    page.route('**/decisions/*', hold_first)
    card.locator('select').select_option('0')
    page.wait_for_timeout(100)
    assert pending
    page.get_by_role('tab', name='Survey & recommendations', exact=True).click()
    # Navigate to the issue's screen via the rail button whose text cites it.
    rail = page.locator('.rail-item').filter(has_text=headline)
    if rail.count():
        rail.first.click()
    coach = page.locator('.card').filter(has=page.get_by_role('button', name=headline, exact=True))
    coach.get_by_text('Your original', exact=True).click()
    page.wait_for_timeout(200)
    response = pending[0].fetch()
    pending[0].fulfill(response=response)
    page.wait_for_timeout(200)
    page.reload()
    page.get_by_role('tab', name='All issues', exact=True).click()
    card = page.locator('.fix-card').filter(has=page.get_by_role('heading', name=headline, exact=True))
    assert card.locator('select').input_value() == 'original'
    page.close()
