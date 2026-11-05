"""Hypothetical preview changes wording only for added changes, never saves a decision by itself (real local server).

2D: the preview needs a change in My changes (2B), so the flow is: nothing to preview and no write -> add one change
(the only write) -> With my changes shows it, Original restores -> a kept item is not a change, and its reason
survives a reload."""
from tests.test_site_e2e import browser
from tests.site_helpers import go_to
from tests.test_workflow_e2e import studio

FOCUS = "() => { const f=SC.workspaceDetail.review.findings.find(f=>f.headline.includes('desktop word')); dispatchEvent(new CustomEvent('surveycoach-focus-finding',{detail:f.fingerprint})); }"


def open_improve(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    go_to(page, 'improve')
    page.locator('#stage .phone-screen').wait_for()
    page.evaluate(FOCUS)
    return page


def test_preview_changes_only_after_adding_a_change_and_can_restore_original(browser, studio):
    page = open_improve(browser, studio)
    before = page.locator('#stage .phone-screen').inner_text()
    writes = []
    page.on('request', lambda request: writes.append(request.url) if request.method == 'PUT' else None)
    preview = page.get_by_role('button', name='With my changes (0)', exact=True)
    assert preview.is_disabled() and 'Add a change' in preview.get_attribute('title')      # says why, and never writes
    assert not writes
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert len(writes) == 1                                  # adding is the one explicit write
    page.evaluate(FOCUS)
    page.get_by_role('button', name='With my changes (1)', exact=True).click()
    assert page.locator('#stage .phone-screen').inner_text() != before
    assert 'RedJade is only changed when you edit it there' in page.locator('.preview-effect').inner_text()
    assert len(writes) == 1                                  # previewing wrote nothing more
    page.get_by_role('button', name='Original', exact=True).click()
    assert page.locator('#stage .phone-screen').inner_text() == before
    assert len(writes) == 1
    page.close()


def test_kept_item_is_not_previewed_and_its_reason_survives_a_reload(browser, studio):
    page = open_improve(browser, studio)
    before = page.locator('#stage .phone-screen').inner_text()
    page.locator('#keep-as-is').click()
    page.get_by_role('button', name='Owner decided', exact=True).click()
    page.locator('#keep-save').click()
    page.locator('#undo').wait_for()
    page.evaluate(FOCUS)
    assert page.get_by_role('button', name='With my changes (0)', exact=True).is_disabled()   # a keep is not a change
    assert page.locator('#stage .phone-screen').inner_text() == before
    page.reload()
    page.locator('#stage .phone-screen').wait_for()
    page.evaluate(FOCUS)
    assert 'Kept as is · Owner decided' in page.locator('#coach .handled-line').inner_text()   # the reason came back from the server
    page.close()
