"""Hypothetical preview changes wording without accepting or saving decisions."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_preview_changes_immediately_without_writes_and_can_restore_original(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('.phone-screen').wait_for()
    page.locator('#issues-view > summary').click()
    pattern = page.locator('.issue-pattern').filter(has_text='desktop word')
    if pattern.count() and not pattern.evaluate('(e) => e.open'):
        pattern.locator(':scope > summary').click()
    page.locator('.issue-jump').filter(has_text='desktop word').first.click()
    before = page.locator('.phone-screen').inner_text()
    writes = []
    page.on('request', lambda request: writes.append(request.url) if request.method == 'PUT' else None)
    page.get_by_role('button', name='Rewritten', exact=True).click()
    assert page.locator('.phone-screen').inner_text() != before
    assert 'Tap the one you like best.' in page.locator('.phone-screen').inner_text()
    assert 'not accepted or saved' in page.locator('.preview-effect').inner_text()
    assert not writes
    page.get_by_role('button', name='Original', exact=True).click()
    assert page.locator('.phone-screen').inner_text() == before
    page.get_by_role('button', name='Keep mine', exact=True).click()
    page.get_by_role('button', name='Required wording', exact=True).click()
    page.get_by_role('button', name='Save reason & keep mine').click()
    page.locator('.accepted-risk').wait_for()
    assert writes
    assert page.get_by_role('button', name='Rewritten', exact=True).is_disabled()
    assert page.locator('.phone-screen').inner_text() == before
    page.reload()
    page.locator('.phone-screen').wait_for()
    page.locator('#issues-view > summary').click()
    pattern = page.locator('.issue-pattern').filter(has_text='desktop word')
    if pattern.count() and not pattern.evaluate('(e) => e.open'):
        pattern.locator(':scope > summary').click()
    page.locator('.issue-jump').filter(has_text='desktop word').first.click()
    assert page.get_by_label('Reason for keeping', exact=False).input_value() == 'Required wording'
    assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
    page.close()
