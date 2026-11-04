"""The member experience, not report chrome, is the first-screen centrepiece."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_phone_is_visible_above_fold_on_saved_review(browser, studio):
    page = browser.new_page(viewport={'width':1440,'height':900})
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#stage .phone-screen').wait_for()
    phone = page.locator('#stage .phone').bounding_box()
    assert phone['y'] < 450  # Chapter navigation now shares the top half of the viewport.
    assert page.locator('#stage .phone-screen').bounding_box()['height'] >= 450
    assert page.locator('#coach .report').count() == 0
    assert page.locator('#stage').evaluate('e => getComputedStyle(e).backgroundColor') == 'rgba(0, 0, 0, 0)'
    page.close()


def test_return_to_review_always_opens_member_experience(browser, studio):
    page = browser.new_page(viewport={'width':390,'height':844})
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#all-screens').click()
    page.locator('.screen-row').last.click()
    page.reload()
    page.locator('#stage .phone-screen').wait_for(state='visible')
    assert page.locator('#stage .phone').bounding_box()['y'] < 430
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.close()
