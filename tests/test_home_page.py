"""Home page ("launch pad") contracts: list summary data and rendered states. Synthetic only."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from surveycoach.server import create_app
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio

ROOT = Path(__file__).resolve().parents[1]


def test_survey_list_summarises_latest_review(tmp_path):
    snapshot = json.loads((ROOT / "fixtures" / "boxer-briefs.json").read_text())
    with TestClient(create_app(tmp_path / "home.sqlite3"), base_url="http://localhost") as client:
        assert client.get("/api/surveys").json()["surveys"] == []
        created = client.post("/api/surveys", json={"snapshot": snapshot}).json()
        detail = client.get(f"/api/surveys/{created['id']}").json()
        card = detail["review"]["scorecard"]
        listed = client.get("/api/surveys").json()["surveys"][0]
        assert listed["readiness"] == card["readiness"]
        assert listed["must_fix"] == sum(f["severity"] == "must_fix" for f in detail["review"]["findings"])
        assert listed["score_checked"] == [round(card["score"]), card["checked_points"]]
        assert listed['signals'] == detail['overview']['signals']
        assert listed['job']['status'] == 'completed'
        assert listed['ready_to_share'] is False


def test_home_renders_cards_example_and_toned_errors(browser, studio):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.set_default_timeout(10000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(studio + "/local.html")
    # Empty state points at the hero instead of duplicating the sample button.
    page.get_by_text("Nothing reviewed yet", exact=False).wait_for()
    assert page.locator("#sample-start").count() == 1
    assert page.get_by_role("img", name="Example review result", exact=False).count() == 1
    page.get_by_label("RedJade preview link").fill("not-a-url")
    page.get_by_role("button", name="Check survey", exact=True).click()
    status = page.locator("#import-status")
    page.wait_for_function("document.querySelector('#import-status').dataset.tone === 'error'")
    assert "valid HTTPS RedJade test link" in status.inner_text()
    # Snapshot import is developer-only; use the visible, network-free sample path.
    assert page.locator("details.import").is_hidden()
    page.get_by_role("button", name="Try a sample survey", exact=True).click()
    page.wait_for_url("**/review.html?**", timeout=30000)
    page.goto(studio + "/local.html")
    survey_card = page.locator("#survey-list a.survey-card").first
    survey_card.wait_for()
    assert survey_card.locator(".chip").inner_text().strip()
    assert "must-fixes" in survey_card.inner_text().lower()
    assert survey_card.get_attribute('href').endswith('#overview')
    assert survey_card.locator('.signal-dot').count() == 6
    assert 'checked points' not in survey_card.inner_text()
    assert survey_card.locator('.meta').inner_text().startswith('Version 1 · ')
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    context.close()


NOTICE = 'Test links only · Wording is reviewed by Walmart-approved AI · Creates a test response to exclude from results.'


def test_home_promise_notice_and_keyboard_dialog(browser, studio):
    page = browser.new_page(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    page.goto(studio + '/local.html')
    assert page.locator('h1').inner_text() == 'See your survey through your members’ eyes.'
    assert page.locator('#import-form > p.help').all_text_contents() == [NOTICE]
    assert page.locator('section.steps, section.trust').count() == 0
    assert page.locator('ol.narrative li').all_text_contents() == ['See', 'Improve', 'Share']
    assert page.locator('ol.narrative svg').count() == 3
    assert page.locator('.go:visible, .btn-primary:visible').count() == 1
    trigger = page.get_by_role('button', name='How we handle data', exact=True)
    trigger.focus()
    page.keyboard.press('Enter')
    dialog = page.get_by_role('dialog', name='How we handle data', exact=True)
    assert dialog.is_visible()
    assert dialog.locator('h3').all_text_contents() == [
        'Stays on this computer', 'AI sees survey wording only', 'Test responses only']
    assert 'Local pilot, not an automatic launch approval' in dialog.inner_text()
    assert page.evaluate('document.activeElement.closest("dialog") !== null')
    page.keyboard.press('Shift+Tab')
    assert page.evaluate('document.activeElement.closest("dialog") !== null')
    page.keyboard.press('Escape')
    assert not dialog.is_visible()
    assert trigger.evaluate('(el) => el === document.activeElement')
    trigger.click()
    dialog.get_by_role('button', name='Close', exact=True).click()
    assert trigger.evaluate('(el) => el === document.activeElement')
    for selector in ('.before', '.after'):
        assert page.locator(selector).evaluate('(el) => getComputedStyle(el).animationName') == 'none'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.close()


def test_cards_use_supplied_signals_and_never_infer_readiness(browser, studio):
    page = browser.new_page()
    signals = [{'name': name, 'state': state, 'label': label} for name, state, label in [
        ('Time', 'needs_work', 'Needs attention'), ('Clarity', 'strong', 'Looking good'),
        ('Honest answers', 'mixed', 'Room to improve'), ('Energy & flow', 'unknown', 'Not checked yet'),
        ('Tone & fun', 'strong', 'Looking good'), ('Phone comfort', 'unknown', 'Not checked yet')]]
    base = dict(id='unsafe<>', title='', version=3, created_at='2026-01-01 00:00:00',
                must_fix=0, readiness='ready', signals=signals, ready_to_share=False)
    page.route('**/api/surveys', lambda route: route.fulfill(json={'surveys': [
        base, dict(base, id='ready', title='<b>Literal title</b>', ready_to_share=True),
        dict(base, id='missing', signals=None, readiness=None, must_fix=None),
        dict(base, id='fix', must_fix=2, ready_to_share=True)]}))
    page.goto(studio + '/local.html')
    cards = page.locator('a.survey-card')
    cards.first.wait_for()
    assert cards.locator('.chip').all_text_contents() == ['Checking…', 'Ready to share', 'Checking…', '2 must-fixes']
    assert cards.first.locator('h3').inner_text() == 'Untitled survey'
    assert cards.nth(1).locator('h3').inner_text() == '<b>Literal title</b>'
    assert cards.nth(1).locator('b').count() == 0
    assert cards.first.locator('.signals').get_attribute('aria-label') == ', '.join(
        f"{signal['name']}: {signal['label']}" for signal in signals)
    assert cards.first.locator('.signal-dot').count() == 6
    assert cards.first.locator('.signal-dot').evaluate_all('(els) => els.map(el => el.dataset.state)') == [s['state'] for s in signals]
    assert cards.nth(2).locator('.signal-dot[data-state=unknown]').count() == 6
    assert cards.first.locator('button, input, a, [tabindex]').count() == 0
    assert cards.first.get_attribute('href') == 'review.html?id=unsafe%3C%3E#overview'
    assert cards.first.locator('.meta').inner_text().startswith('Version 3 · ')
    assert 'checked points' not in cards.first.inner_text()
    page.close()


def test_reading_state_tracks_actual_job_and_capture(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.route('**/api/reader/jobs/*/preview/*', lambda route: route.abort())
    def render(job):
        page.evaluate('job => SC.renderReadProgress(job, "synthetic")', job)
    render(dict(status='queued', stage=None, pages_captured=0))
    assert page.locator('#reading-progress').inner_text() == 'Review queued…'
    assert page.locator('#reading-preview img').count() == 0
    assert page.locator('#reading-steps [data-complete=true]').count() == 0
    render(dict(status='running', stage='reading', pages_captured=4))
    assert page.locator('#reading-progress').inner_text() == 'Reading screen 4…'
    assert page.locator('#reading-preview img').get_attribute('src').endswith('/preview/3')
    assert page.locator('#reading-steps [data-complete=true]').count() == 1
    render(dict(status='running', stage='checking', pages_captured=4))
    assert page.locator('#reading-steps [data-complete=true]').count() == 2
    assert page.locator('#reading-steps [data-complete=true] svg').count() == 2
    render(dict(status='failed', stage='checking', pages_captured=4, error='Synthetic read failure'))
    assert page.locator('#reading-progress').inner_text() == 'Review needs attention.'
    assert page.get_by_text('Synthetic read failure', exact=True).count() == 1
    assert page.locator('#reading-steps [data-complete=true]').count() == 2
    render(dict(status='completed', stage='checking', pages_captured=4))
    assert page.locator('#reading-steps [data-complete=true]').count() == 4
    assert page.locator('#reading-steps [data-complete=true] svg').count() == 4
    assert page.locator('[role=progressbar]').count() == 0
    page.close()


def test_new_zero_capture_job_clears_previous_survey_preview(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.route('**/api/reader/jobs/*/preview/*', lambda route: route.abort())

    def render(job_id, **job):
        page.evaluate('args => SC.renderReadProgress(args.job, args.id)',
                      {'id': job_id, 'job': job})

    render('previous-survey', status='failed', stage='checking', pages_captured=4,
           error='Previous captured read failed')
    assert page.locator('#reading-preview img').get_attribute('src') == (
        '/api/reader/jobs/previous-survey/preview/3')
    assert page.locator('#reading-steps [data-complete=true]').count() == 2

    for status, stage, error, expected in [
        ('queued', None, None, 'Review queued…'),
        ('running', 'reading', None, 'Opening the test survey…'),
        ('failed', 'reading', 'New read failed before capture', 'New read failed before capture'),
    ]:
        render('new-survey', status=status, stage=stage, pages_captured=0, error=error)
        assert page.locator('#reading-preview img').count() == 0
        assert page.locator('#reading-preview [src]').count() == 0
        assert page.locator('#reading-preview .reading-phone > svg').count() == 1
        assert page.locator('#reading-progress').inner_text() == ('Review needs attention.' if status == 'failed' else expected)
        if status == 'failed':
            assert page.get_by_text(error, exact=True).count() == 1
        assert page.locator('#reading-steps [data-complete=true]').count() == 0
        assert page.locator('#reading-steps [data-complete=false]').count() == 4
        assert 'previous-survey' not in page.locator('#reading-preview').inner_html()
        assert 'Reading screen 1' not in page.locator('#reading-preview').inner_text()

    render('new-survey', status='running', stage='reading', pages_captured=1)
    assert page.locator('#reading-preview img').get_attribute('src') == (
        '/api/reader/jobs/new-survey/preview/0')
    assert page.locator('#reading-progress').inner_text() == 'Reading screen 1…'
    assert page.locator('#reading-preview').count() == 1
    page.close()


def test_list_does_not_promote_incomplete_evidence(tmp_path, monkeypatch):
    from surveycoach.server.repository import Repository
    from tests.builders import one_question_survey, question
    repository = Repository(tmp_path / 'cards.sqlite3')
    created = repository.submit(one_question_survey(question()), False)
    # A queued snapshot has neither assessed signals nor a readiness claim.
    listed = repository.list_surveys()[0]
    assert listed['signals'] == []
    assert listed['job']['status'] == 'queued'
    assert listed['ready_to_share'] is False
    detail = repository.detail(created['id'])
    detail.update(review={'scorecard': {'readiness': 'ready', 'score': 100, 'checked_points': 100},
                          'findings': [], 'unchecked': []},
                  overview={'signals': [{'state': 'strong'}] * 6}, job={'status': 'completed'})
    monkeypatch.setattr(repository, 'detail', lambda *_: detail)
    assert repository.list_surveys()[0]['ready_to_share'] is True
    detail['coverage'] = {'full_branching_coverage': False}
    assert repository.list_surveys()[0]['ready_to_share'] is False
    detail['coverage'] = None
    detail['overview']['signals'] = [{'state': 'strong'}] * 5 + [{'state': 'unknown'}]
    assert repository.list_surveys()[0]['ready_to_share'] is False
    detail['overview']['signals'] = [{'state': 'strong'}] * 6
    detail['review']['unchecked'] = ['Unassessed evidence']
    assert repository.list_surveys()[0]['ready_to_share'] is False


def test_example_motion_is_single_short_css_animation(browser, studio):
    page = browser.new_page(reduced_motion='no-preference')
    page.goto(studio + '/local.html')
    for selector, expected in (('.before', 'strike'), ('.after', 'insert')):
        style = page.locator(selector).evaluate('el => { const s = getComputedStyle(el); return [s.animationName, s.animationDuration, s.animationIterationCount]; }')
        assert style == [expected, '0.36s', '1']
    page.close()
