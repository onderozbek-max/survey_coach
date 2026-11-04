"""Hypothetical preview changes wording without accepting or saving decisions."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_preview_changes_immediately_without_writes_and_can_restore_original(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#stage .phone-screen').wait_for()
    page.evaluate("() => { const f=SC.workspaceDetail.review.findings.find(f=>f.headline.includes('desktop word')); dispatchEvent(new CustomEvent('surveycoach-focus-finding',{detail:f.fingerprint})); }")
    before = page.locator('#stage .phone-screen').inner_text()
    writes = []
    page.on('request', lambda request: writes.append(request.url) if request.method == 'PUT' else None)
    page.get_by_role('button', name='With changes', exact=True).click()
    assert page.locator('#stage .phone-screen').inner_text() != before
    assert 'Tap the one you like best.' in page.locator('#stage .phone-screen').inner_text()
    assert 'not accepted or saved' in page.locator('.preview-effect').inner_text()
    assert not writes
    page.get_by_role('button', name='Original', exact=True).click()
    assert page.locator('#stage .phone-screen').inner_text() == before
    page.get_by_role('button', name='Keep as is', exact=True).click()
    page.get_by_role('button', name='Stakeholder requirement', exact=True).click()
    page.locator('#toast').wait_for()
    page.evaluate("() => { const f=SC.workspaceDetail.review.findings.find(f=>f.headline.includes('desktop word')); dispatchEvent(new CustomEvent('surveycoach-focus-finding',{detail:f.fingerprint})); }")

    assert writes
    page.get_by_role('button', name='With changes', exact=True).click()
    assert page.locator('#stage .phone-screen').inner_text() == before
    page.reload()
    page.locator('#stage .phone-screen').wait_for()
    page.evaluate("() => { const f=SC.workspaceDetail.review.findings.find(f=>f.headline.includes('desktop word')); dispatchEvent(new CustomEvent('surveycoach-focus-finding',{detail:f.fingerprint})); }")
    assert page.get_by_label('Reason for keeping', exact=False).input_value() == 'Stakeholder requirement'
    assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
    page.close()
