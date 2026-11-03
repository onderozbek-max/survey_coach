"""Local member journey estimates are visible, inspectable and never empirical claims."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_journey_comparison_and_question_stem_visible(browser, studio):
    page = browser.new_page(viewport={'width':1440,'height':1000})
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('.phone-screen').first.wait_for()
    assert page.locator('.phone-screen').first.evaluate('e => e.scrollTop') == 0
    assert page.get_by_role('navigation', name='Member effort by screen').count() == 1
    # Comparison is intentionally unavailable on screens without text changes.
    page.evaluate("() => { const f=SC.workspaceDetail.review.findings.find(f=>f.current_text && !f.structural && (f.suggested_text || f.options?.length)); window.dispatchEvent(new CustomEvent('surveycoach-focus-finding',{detail:f.fingerprint})); }")
    page.get_by_role('button', name='Compare wording', exact=True).click()
    assert page.locator('.comparison-phones .phone').count() == 2
    assert page.get_by_text('Original', exact=True).count() >= 1
    assert 'Estimated' in page.locator('.journey').inner_text()
    page.get_by_role('button', name='Play as a member', exact=True).click()
    assert page.get_by_role('button', name='Pause walkthrough', exact=True).count() == 1
    page.get_by_role('button', name='Pause walkthrough', exact=True).click()
    page.get_by_role('button', name='Close comparison', exact=True).click()
    assert page.locator('.phone').count() == 1
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='Compare wording',exact=True).click()
    phones=page.locator('.comparison-phones .phone')
    assert phones.count()==2
    first,second=phones.nth(0).bounding_box(),phones.nth(1).bounding_box()
    assert second['y'] > first['y']
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.close()
