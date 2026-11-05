"""Truthful loading and recovery contracts. All job endpoints are synthetic."""
import json
import re

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
    assert page.locator('#reading-response').evaluate('el => getComputedStyle(el).color') == 'rgb(91, 107, 128)'  # shared muted token
    page.close()


def test_post_timeout_is_ambiguous_locked_and_never_retried(browser, studio):
    page = browser.new_page()
    posts = []
    page.route('**/api/reader/jobs', lambda route: posts.append(route))
    page.clock.install()
    start(page, studio)
    page.wait_for_function('sessionStorage.getItem("surveycoach-pending-job") !== null')
    page.clock.run_for(21000)
    expect(page.locator('#import-status')).to_contain_text('Request status unknown')
    expect(page.locator('#sample-start')).to_be_disabled()
    expect(page.locator('#survey-link')).to_be_disabled()
    assert page.locator('#resume-checking').count() == 0
    assert page.get_by_text(page.locator('#import-status').inner_text(), exact=True).count() == 1
    assert len(posts) == 1
    saved = page.evaluate('JSON.parse(sessionStorage.getItem("surveycoach-pending-job"))')
    assert set(saved) == {'submissionPending', 'started'}
    assert page.locator('#reading-preview').get_attribute('aria-busy') == 'false'
    page.reload()
    expect(page.locator('#import-status')).to_contain_text('Request status unknown')
    expect(page.locator('#sample-start')).to_be_disabled()
    assert len(posts) == 1
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
    assert page.locator('#reading-progress').inner_text() == 'Review needs attention.'
    assert page.get_by_text('<b>Synthetic failure</b>', exact=True).count() == 1
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


def test_pending_submission_reload_stays_locked_without_fake_job(browser, studio):
    page = browser.new_page()
    posts, gets = [], []
    page.route('**/api/reader/jobs', lambda route: posts.append(route))
    page.route('**/api/jobs/*', lambda route: gets.append(route))
    page.clock.install()
    start(page, studio)
    page.wait_for_function('sessionStorage.getItem("surveycoach-pending-job") !== null')
    saved = page.evaluate('JSON.parse(sessionStorage.getItem("surveycoach-pending-job"))')
    assert set(saved) == {'submissionPending', 'started'}
    assert saved['submissionPending'] is True
    page.reload()
    expect(page.locator('#import-status')).to_contain_text('Request status unknown')
    expect(page.locator('#sample-start')).to_be_disabled()
    expect(page.locator('#survey-link')).to_be_disabled()
    assert page.locator('#resume-checking').count() == 0
    assert page.get_by_text(page.locator('#import-status').inner_text(), exact=True).count() == 1
    assert len(posts) == 1
    assert gets == []
    # The same marker survives repeated reloads, including beyond the accepted-job TTL.
    page.evaluate('''() => {
      const key = 'surveycoach-pending-job', saved = JSON.parse(sessionStorage.getItem(key));
      saved.started -= 3 * 60 * 60 * 1000;
      sessionStorage.setItem(key, JSON.stringify(saved));
    }''')
    page.reload()
    expect(page.locator('#import-status')).to_contain_text('Do not submit again while it may be running')
    expect(page.locator('#sample-start')).to_be_disabled()
    page.close()


def test_explicit_rejection_clears_submission_marker(browser, studio):
    page = browser.new_page()
    page.route('**/api/reader/jobs', lambda route: route.fulfill(status=422, json={'detail':'Synthetic rejected input'}))
    start(page, studio)
    expect(page.locator('#import-status')).to_have_text('Synthetic rejected input')
    assert page.get_by_text('Synthetic rejected input', exact=True).count() == 1
    assert page.locator('#reading-preview [aria-live], #reading-preview [role=status]').count() == 0
    expect(page.locator('#sample-start')).to_be_enabled()
    assert page.evaluate('sessionStorage.getItem("surveycoach-pending-job")') is None
    page.reload()
    expect(page.get_by_role('button', name='Check survey', exact=True)).to_be_enabled()
    page.close()


def test_storage_unavailable_warns_without_preventing_current_job(browser, studio):
    page = browser.new_page()
    page.add_init_script("Storage.prototype.setItem = function() { throw new DOMException('Blocked', 'SecurityError'); };")
    page.route('**/api/reader/jobs', lambda route: None)
    page.clock.install()
    start(page, studio)
    expect(page.locator('#reading-storage-warning')).to_contain_text('cannot recover this request after a reload')
    page.clock.run_for(21000)
    expect(page.locator('#import-status')).to_contain_text('Request status unknown')
    expect(page.locator('#sample-start')).to_be_disabled()
    expect(page.locator('#reading-storage-warning')).to_be_visible()
    page.close()


def test_acceptance_atomically_replaces_marker_and_storage_failure_can_finish(browser, studio):
    for storage_blocked in (False, True):
        page = browser.new_page()
        if storage_blocked:
            page.add_init_script("Storage.prototype.setItem = function() { throw new Error('Blocked'); };")
        else:
            page.add_init_script('''
              window.pendingWrites = [];
              const original = Storage.prototype.setItem;
              Storage.prototype.setItem = function(key, value) {
                if (key === 'surveycoach-pending-job') window.pendingWrites.push(JSON.parse(value));
                return original.call(this, key, value);
              };
            ''')
        page.route('**/api/reader/jobs', lambda route: route.fulfill(json={'job_id':'accepted'}))
        page.route('**/api/jobs/accepted', lambda route: route.fulfill(json={
            'status':'failed', 'stage':'reading', 'pages_captured':0, 'error':'Synthetic terminal failure'}))
        start(page, studio)
        expect(page.locator('#import-status')).to_have_text('Synthetic terminal failure')
        expect(page.locator('#sample-start')).to_be_enabled()
        if not storage_blocked:
            writes = page.evaluate('window.pendingWrites')
            assert len(writes) == 2
            assert writes[0] == {'submissionPending':True, 'started':writes[1]['started']}
            assert set(writes[1]) == {'jobId', 'started'}
            assert writes[1]['jobId'] == 'accepted'
        assert page.evaluate('sessionStorage.getItem("surveycoach-pending-job")') is None
        page.close()


def test_old_accepted_job_requires_terminal_verification_even_after_404(browser, studio):
    page = browser.new_page()
    page.add_init_script('''
      if (!sessionStorage.getItem('surveycoach-pending-job'))
        sessionStorage.setItem('surveycoach-pending-job', JSON.stringify({jobId:'old-job', started:Date.now()-10800000}));
    ''')
    posts, gets = [], []
    page.route('**/api/reader/jobs', lambda route: posts.append(route))
    def missing(route):
        gets.append(route.request.url)
        route.fulfill(status=404, json={'detail':'Unknown job'})
    page.route('**/api/jobs/old-job', lambda route: route.fulfill(json={'status':'running', 'stage':'reading', 'pages_captured':0}))
    page.goto(studio + '/local.html')
    expect(page.locator('#reading-progress')).to_have_text('Opening the test survey…')
    expect(page.locator('#sample-start')).to_be_disabled()
    assert posts == []
    page.unroute('**/api/jobs/old-job')
    page.route('**/api/jobs/old-job', missing)
    page.reload()
    expect(page.locator('#import-status')).to_contain_text('cannot verify')
    expect(page.locator('#sample-start')).to_be_disabled()
    assert len(gets) == 1
    assert posts == []
    assert page.evaluate('JSON.parse(sessionStorage.getItem("surveycoach-pending-job")).jobId') == 'old-job'
    page.unroute('**/api/jobs/old-job')
    page.route('**/api/jobs/old-job', lambda route: route.fulfill(json={
        'status':'failed', 'error':'Verified terminal failure'}))
    page.reload()
    expect(page.locator('#import-status')).to_have_text('Verified terminal failure')
    expect(page.locator('#sample-start')).to_be_enabled()
    assert page.evaluate('sessionStorage.getItem("surveycoach-pending-job")') is None
    assert posts == []
    page.close()


def test_capture_observation_age_ticks_without_further_poll_response(browser, studio):
    page = browser.new_page()
    page.route('**/api/reader/jobs/*/preview/*', lambda route: route.abort())
    page.goto(studio + '/local.html')
    page.clock.install()
    page.evaluate('SC.renderReadProgress({status:"running", stage:"reading", pages_captured:2}, "synthetic")')
    page.clock.run_for(45000)
    age = int(re.search(r'(\d+)s ago', page.locator('#reading-context').inner_text())[1])
    assert 44 <= age <= 46
    expect(page.locator('#reading-context')).to_contain_text('observed')
    page.evaluate('SC.readConnection("Connection interrupted", true)')
    page.clock.run_for(15000)
    age = int(re.search(r'(\d+)s ago', page.locator('#reading-context').inner_text())[1])
    assert 59 <= age <= 61
    response_age = int(re.search(r'(\d+)s ago', page.locator('#reading-response').inner_text())[1])
    assert abs(age - response_age) <= 1
    page.close()


def test_sample_and_snapshot_without_reader_stage_never_claim_test_site(browser, studio):
    for kind in ('sample', 'snapshot'):
        page = browser.new_page()
        path = '**/api/samples/boxer-briefs' if kind == 'sample' else '**/api/surveys'
        page.route(path, lambda route: route.fulfill(json={'job_id':'supplied'}) if route.request.method == 'POST' else route.fulfill(json={'surveys':[]}))
        page.route('**/api/jobs/supplied', lambda route: route.fulfill(json={'status':'running', 'pages_captured':0}))
        page.goto(studio + '/local.html')
        if kind == 'sample':
            page.get_by_role('button', name='Try a sample survey').click()
        else:
            page.locator('#snapshot').set_input_files({'name':'synthetic.json', 'mimeType':'application/json', 'buffer':b'{}'})
            page.get_by_role('button', name='Check survey', exact=True).click()
        expect(page.locator('#reading-progress')).to_contain_text('Checking wording and flow')
        assert 'Opening test survey' not in page.locator('#reading-preview').inner_text()
        assert 'captured screen will appear' not in page.locator('#reading-preview').inner_text()
        assert page.locator('#reading-steps [aria-current]').inner_text() == 'Check wording & flow'
        # No job-kind metadata is persisted; reload remains truthful using response evidence only.
        assert set(page.evaluate('JSON.parse(sessionStorage.getItem("surveycoach-pending-job"))')) == {'jobId', 'started'}
        page.reload()
        expect(page.locator('#reading-progress')).to_contain_text('Checking wording and flow')
        assert 'Opening test survey' not in page.locator('#reading-preview').inner_text()
        page.close()


def test_clock_rollback_preserves_known_job_on_reload(browser, studio):
    page = browser.new_page()
    gets, posts = [], []
    def status(route):
        gets.append(route.request.url)
        route.fulfill(json={'status':'running', 'stage':'reading', 'pages_captured':0})
    page.route('**/api/jobs/future-job', status)
    page.route('**/api/reader/jobs', lambda route: posts.append(route))
    page.goto(studio + '/local.html')
    page.evaluate('sessionStorage.setItem("surveycoach-pending-job", JSON.stringify({jobId:"future-job", started:Date.now()+60000}))')
    page.reload()
    expect(page.locator('#reading-progress')).to_have_text('Opening the test survey…')
    expect(page.locator('#sample-start')).to_be_disabled()
    expect(page.locator('#reading-elapsed')).to_have_text('Elapsed 0:00')
    assert len(gets) >= 1
    assert posts == []
    assert page.evaluate('JSON.parse(sessionStorage.getItem("surveycoach-pending-job")).jobId') == 'future-job'
    page.close()


def test_clock_rollback_preserves_unknown_submission_on_reload(browser, studio):
    page = browser.new_page()
    gets, posts = [], []
    page.route('**/api/jobs/*', lambda route: gets.append(route))
    page.route('**/api/reader/jobs', lambda route: posts.append(route))
    page.goto(studio + '/local.html')
    page.evaluate('sessionStorage.setItem("surveycoach-pending-job", JSON.stringify({submissionPending:true, started:Date.now()+60000}))')
    page.reload()
    expect(page.locator('#import-status')).to_contain_text('Request status unknown')
    expect(page.locator('#sample-start')).to_be_disabled()
    expect(page.locator('#survey-link')).to_be_disabled()
    expect(page.locator('#reading-elapsed')).to_have_text('Elapsed 0:00')
    assert page.locator('#resume-checking').count() == 0
    assert gets == posts == []
    assert page.evaluate('JSON.parse(sessionStorage.getItem("surveycoach-pending-job")).submissionPending') is True
    page.close()
