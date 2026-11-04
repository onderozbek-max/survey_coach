"""Shared design and canonical routes apply to saved versions, not only new reads."""
from fastapi.testclient import TestClient

from surveycoach.server import create_app
from surveycoach.server.service import summary_packet
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_root_is_launchpad_and_assets_revalidate(tmp_path):
    with TestClient(create_app(tmp_path / 'workspace.sqlite'), base_url='http://127.0.0.1') as client:
        response = client.get('/')
        assert 'Check survey' in response.text
        assert 'design-system.css' in response.text
        assert response.headers['cache-control'] == 'no-cache'
        assert client.get('/api/missing').status_code == 404


def test_export_embeds_shared_components_without_external_dependencies():
    html = summary_packet({'title': '<script>unsafe</script>', 'version': 1, 'review': None, 'snapshot': {'title': 'Synthetic', 'pages': []}, 'decisions': {}})
    assert '<style>' in html and '<main>' in html
    assert 'Share for sign-off' in html and 'not launch approval' in html
    assert 'Review not available' in html and 'No readiness judgement has been made' in html
    assert '<script>unsafe' not in html
    assert '&lt;script&gt;unsafe' in html
    assert '<link' not in html


def test_legacy_phone_link_and_keyboard_issue_navigation(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    query = page.url.split('?', 1)[1]
    page.goto(studio + '/index.html?' + query)
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#stage .phone-screen').wait_for()
    assert page.get_by_role('tab').count() == 3
    summary = page.locator('#all-screens')
    summary.focus()
    page.keyboard.press('Enter')
    jump = page.locator('.screen-row').first
    headline = jump.locator('strong').inner_text()
    jump.focus()
    page.keyboard.press('Enter')
    assert page.locator('#coach .card').count() == 1
    assert page.locator('#stage .phone-bar').inner_text().startswith(headline)
    assert page.locator('#survey-view').is_visible()
    assert page.locator('#stage .phone-screen').is_visible()
    assert page.locator('#fix-list select, #fix-list textarea').count() == 0
    assert page.locator('#screen-drawer').evaluate('e => e.tagName') == 'DIALOG'
    assert page.locator('#screen-drawer .screen-row').count() > 0
    headings = page.locator('#screen-drawer strong').all_inner_texts()
    assert not any('fingerprint' in text or 'q-' in text for text in headings)
    page.locator('[data-chapter=share]').click()
    assert page.locator('#download-summary').inner_text() == 'Download summary'
    assert page.locator('#download-summary').get_attribute('href').endswith('/summary?download=1')
    assert page.locator('details.studio-tools').count() == 0
    page.close()


def test_old_validation_capture_is_identified_not_presented_as_question(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/index.html#improve')
    page.locator('#stage .phone-screen').wait_for()
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
    page.goto(studio + '/index.html#improve')
    page.locator('#stage .phone-screen').wait_for()
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
