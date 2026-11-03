"""Canonical review navigation and honest image reminders, synthetic localhost only."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_saved_review_opens_phone_and_shared_system(browser, studio):
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('.phone-screen').wait_for()
    assert page.locator('link[href="design-system.css"]').count() == 1
    page.get_by_role('tab', name='All issues', exact=True).click()
    page.locator('.fix-card').first.wait_for()
    page.get_by_role('tab', name='Survey & recommendations', exact=True).click()
    page.locator('.phone-screen').wait_for(state='visible')
    assert page.get_by_role('link', name='Export review report', exact=True).count() == 1
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.close()


def test_phone_renders_page_landscape_placeholder(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/index.html')
    page.locator('.phone-screen').wait_for()
    page.evaluate('''() => {
      const host = document.createElement('div'); host.id='image-test'; document.body.append(host);
      const item={name:'Test',index:0,page:{id:'p',kind:'info',text:'Review image',media:[
        {element_id:'hero',natural_w:1200,natural_h:400,rendered_w:300,rendered_h:100,loaded:true}
      ]},entries:[]};
      host.append(SC.renderPhone(item,{total:1,device:390,applied:()=>false}));
    }''')
    assert 'Landscape' in page.locator('#image-test').inner_text()
    assert 'Check on mobile' in page.locator('#image-test').inner_text()
    box = page.locator('#image-test .media').bounding_box()
    assert abs(box['width'] / box['height'] - 3) < .15
    page.close()
