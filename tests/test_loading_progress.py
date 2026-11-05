"""Truthful loading and recovery contracts. All job endpoints are synthetic."""
import json

from playwright.sync_api import expect

from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio

LINK = 'https://app.redjade.net/surveys/synthetic'
JOB = dict(status='running', stage='reading', pages_captured=2)


def start(page, studio):
    page.goto(studio + '/local.html')
    page.get_by_label('RedJade preview link').fill(LINK)
    page.get_by_role('button', name='Check survey', exact=True).click()


def test_immediate_panel_before_post_and_first_get_mobile_keyboard(browser, studio):
    page = browser.new_page(viewport={'width': 320, 'height': 780}, reduced_motion='reduce')
    held = []
    page.route('**/api/reader/jobs', lambda route: held.append(route))
    page.route('**/api/jobs/synthetic', lambda route: None)
    page.goto(studio + '/local.html')
    page.get_by_label('RedJade preview link').fill(LINK)
    page.get_by_role('button', name='Check survey', exact=True).focus()
    page.keyboard.press('Enter')
    expect(page.get_by_role('heading', name='Preparing your review')).to_be_visible()
    expect(page.locator('#import-status')).to_contain_text('Sending your request')
    for selector in ('#survey-link', '#snapshot', '#sample-start'):
        expect(page.locator(selector)).to_be_disabled()
    expect(page.get_by_role('button', name='Checking…')).to_be_disabled()
    assert page.locator('#reading-preview img, [aria-current=step], [role=progressbar]').count() == 0
    assert page.locator('#reading-preview').get_attribute('aria-busy') == 'true'
    assert page.locator('#import-status').get_attribute('aria-busy') is None
    assert page.locator('.reading-pulse').evaluate('el => getComputedStyle(el).animationName') == 'none'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert len(held) == 1
    held[0].fulfill(json={'job_id': 'synthetic'})
    expect(page.locator('#reading-response')).to_contain_text('Waiting for the first status response')
    assert page.locator('#reading-preview img').count() == 0
    assert page.locator('#reading-response').evaluate('el => getComputedStyle(el).color') == 'rgb(70, 95, 90)'
    page.close()


def test_post_timeout_is_ambiguous_locked_and_never_retried(browser, studio):
    page = browser.new_page()
    posts = []
    page.route('**/api/reader/jobs', lambda route: posts.append(route))
    page.clock.install()
    start(page, studio)
    page.clock.run_for(21000)
    expect(page.locator('#import-status')).to_contain_text('Status is unknown')
    expect(page.locator('#sample-start')).to_be_disabled()
    expect(page.locator('#survey-link')).to_be_disabled()
    assert page.locator('#resume-checking').count() == 0
    assert len(posts) == 1
    assert page.evaluate('sessionStorage.length') == 0
    assert page.locator('#reading-preview').get_attribute('aria-busy') == 'false'
    page.close()


def test_get_errors_pause_resume_same_job_and_restore_only_opaque_metadata(browser, studio):
    page = browser.new_page()
    posts = []
    def post(route):
        posts.append(route.request.method)
        route.fulfill(json={'job_id': 'synthetic'})
    page.route('**/api/reader/jobs', post)
    page.route('**/api/jobs/synthetic', lambda route: route.fulfill(status=503, json={'detail':'offline'}))
    page.clock.install()
    start(page, studio)
    expect(page.locator('#import-status')).to_contain_text('Connection interrupted')
    for _ in range(3):
        page.clock.run_for(2100)
    expect(page.get_by_role('button', name='Resume checking')).to_be_visible()
    saved = page.evaluate('JSON.parse(sessionStorage.getItem("surveycoach-pending-job"))')
    assert set(saved) == {'jobId', 'started'}
    assert saved['jobId'] == 'synthetic'
    assert LINK not in json.dumps(saved)
    page.unroute('**/api/jobs/synthetic')
    page.route('**/api/jobs/synthetic', lambda route: route.fulfill(json=JOB))
    page.route('**/api/reader/jobs/*/preview/*', lambda route: route.abort())
    page.get_by_role('button', name='Resume checking').focus()
    page.keyboard.press('Enter')
    expect(page.locator('#reading-progress')).to_have_text('Reading screen 2…')
    assert posts == ['POST']
    page.reload()
    expect(page.locator('#reading-progress')).to_have_text('Reading screen 2…')
    assert posts == ['POST']
    expect(page.locator('#survey-link')).to_be_disabled()
    page.close()


def test_stale_captures_live_responses_and_terminal_states(browser, studio):
    page = browser.new_page()
    page.route('**/api/reader/jobs/*/preview/*', lambda route: route.abort())
    page.goto(studio + '/local.html')
    page.clock.install()
    page.evaluate('SC.beginReadProgress()')
    def render(job, job_id='synthetic'):
        return page.evaluate('(args) => SC.renderReadProgress(args[0], args[1])', [job, job_id])
    page.locator('#data-handling').focus()
    render(JOB)
    assert page.locator('#data-handling').evaluate('el => el === document.activeElement')
    page.clock.run_for(45000)
    render(JOB)
    expect(page.locator('#reading-context')).to_contain_text('Waiting for the next screen update.')
    expect(page.locator('#reading-context')).to_contain_text('45s ago')
    expect(page.locator('#reading-response')).to_contain_text('Last status response 0s ago')
    assert 'proof the reader is still working' in page.locator('#reading-response').inner_text()
    assert page.locator('[aria-current=step]').inner_text() == 'Read screens'
    render(dict(status='running', stage='checking', pages_captured=2))
    assert page.locator('[aria-current=step]').inner_text() == 'Check wording & flow'
    render(dict(status='failed', stage='checking', pages_captured=2, error='<b>Synthetic failure</b>'))
    assert page.locator('#reading-progress').inner_text() == '<b>Synthetic failure</b>'
    assert page.locator('#reading-progress b, [aria-current=step]').count() == 0
    render(dict(status='queued', stage=None, pages_captured=0), 'new-job')
    assert page.locator('#reading-preview img, [aria-current=step], [data-complete=true]').count() == 0
    render(dict(status='completed', stage='checking', pages_captured=2))
    assert page.locator('[data-complete=true]').count() == 4
    assert page.locator('#reading-preview').get_attribute('aria-busy') == 'false'
    page.close()


def test_get_timeout_recovers_without_new_post_and_completion_redirects(browser, studio):
    page = browser.new_page()
    posts, held = [], []
    def post(route):
        posts.append(route.request.method)
        route.fulfill(json={'job_id':'synthetic'})
    page.route('**/api/reader/jobs', post)
    page.route('**/api/jobs/synthetic', lambda route: held.append(route))
    page.clock.install()
    start(page, studio)
    expect(page.locator('#reading-heading')).to_be_visible()
    page.wait_for_function('sessionStorage.getItem("surveycoach-pending-job") !== null')
    page.clock.run_for(21000)
    expect(page.locator('#import-status')).to_contain_text('Connection interrupted')
    page.unroute('**/api/jobs/synthetic')
    page.route('**/api/jobs/synthetic', lambda route: route.fulfill(json=dict(
        status='completed', stage='checking', pages_captured=3, survey_id='done', version=2)))
    page.route('**/review.html?**', lambda route: route.fulfill(content_type='text/html', body='<h1>Saved review</h1>'))
    page.clock.run_for(2100)
    page.wait_for_url('**/review.html?id=done&version=2#overview')
    assert posts == ['POST']
    assert page.evaluate('sessionStorage.getItem("surveycoach-pending-job")') is None
    page.close()


def test_recheck_progress_is_visible_and_failed_job_keeps_old_workspace(browser, studio):
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    # Build a valid old review using the existing local FakeProvider fixture, never a vendor.
    page.goto(studio + '/local.html')
    page.get_by_role('button', name='Try a sample survey').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#check-again').click()
    page.get_by_label('Updated RedJade preview link').fill(LINK)
    page.route('**/api/reader/jobs', lambda route: route.fulfill(json={'job_id':'recheck'}))
    page.route('**/api/jobs/recheck', lambda route: route.fulfill(json=dict(
        status='failed', stage='reading', pages_captured=0, error='Synthetic recheck failure. Previous review unchanged.')))
    page.get_by_role('button', name='Start next version').click()
    expect(page.locator('#reading-heading')).to_be_visible()
    expect(page.locator('#import-status')).to_contain_text('Previous review unchanged')
    expect(page.get_by_role('button', name='Start next version')).to_be_enabled()
    assert page.locator('#reading-preview img').count() == 0
    assert page.locator('#reading-steps [aria-current]').count() == 0
    page.locator('#chapter-nav [data-chapter=improve]').click()
    expect(page.locator('#stage .phone-screen')).to_be_visible()
    page.close()
