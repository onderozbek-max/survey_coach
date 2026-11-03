"""Shared design and canonical routes apply to saved versions, not only new reads."""
from fastapi.testclient import TestClient

from surveycoach.server import create_app
from surveycoach.server.service import summary_packet
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_root_is_launchpad_and_assets_revalidate(tmp_path):
    with TestClient(create_app(tmp_path / 'workspace.sqlite'), base_url='http://127.0.0.1') as client:
        response = client.get('/')
        assert 'Start review' in response.text
        assert 'design-system.css' in response.text
        assert response.headers['cache-control'] == 'no-cache'
        assert client.get('/api/missing').status_code == 404


def test_export_embeds_shared_components_without_external_dependencies():
    html = summary_packet({'title': '<script>unsafe</script>', 'version': 1, 'review': None})
    assert '--radius:16px' in html and 'report-shell' in html
    assert '<script>unsafe' not in html
    assert '&lt;script&gt;unsafe' in html
    assert '<link' not in html


def test_legacy_phone_link_and_keyboard_tabs(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    query = page.url.split('?', 1)[1]
    page.goto(studio + '/index.html?' + query)
    page.wait_for_url('**/review.html?**')
    page.locator('.phone-screen').wait_for()
    first = page.get_by_role('tab', name='Survey & recommendations', exact=True)
    first.focus()
    page.keyboard.press('ArrowRight')
    second = page.get_by_role('tab', name='All issues', exact=True)
    assert second.get_attribute('aria-selected') == 'true'
    assert second.evaluate('e => e === document.activeElement')
    page.keyboard.press('Home')
    assert first.get_attribute('aria-selected') == 'true'
    assert page.locator('#survey-view').is_visible()
    page.close()


def test_old_validation_capture_is_identified_not_presented_as_question(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/index.html')
    page.locator('.phone-screen').wait_for()
    page.evaluate('''() => {
      const host=document.createElement('div');host.id='validation-test';document.body.append(host);
      host.append(SC.renderPhone({name:'Test',index:0,entries:[],page:{id:'p',kind:'info',
        text:'Please correct the following errors: Photo Media is required Next'}},
        {total:1,device:390,applied:()=>false}));
    }''')
    text = page.locator('#validation-test').inner_text()
    assert 'Captured validation screen—not a survey question' in text
    assert 'Media is required Next' not in text
    assert 'later screens remain unverified' in text
    page.close()


def test_unknown_and_portrait_media_are_not_fabricated_as_landscape(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/index.html')
    page.locator('.phone-screen').wait_for()
    page.evaluate('''() => {
      const host = document.createElement('div');host.id='image-test';document.body.append(host);
      host.append(SC.renderPhone({name:'Test',index:0,entries:[],page:{id:'p',kind:'info',text:'Images',media:[
        {element_id:'portrait',natural_w:400,natural_h:800,loaded:true},
        {element_id:'unknown',loaded:false}
      ]}},{total:1,device:390,applied:()=>false}));
    }''')
    text = page.locator('#image-test').inner_text()
    assert 'Portrait' in text and 'Orientation unknown' in text
    assert 'Image failed to load' in text
    assert 'Landscape' not in text
    assert '1 / 1' not in page.locator('#image-test .media').last.get_attribute('style')
    page.close()
