"""Sign off against the real server and a real stored review (3C): the page and the 3A endpoints agree.
Synthetic concept survey in a temporary database; no browser network beyond localhost."""
import socket
import threading
import time

import pytest
import uvicorn

from concept_fixture import concept_survey
from review_helpers import save_review
from surveycoach.server import create_app
from surveycoach.server.repository import Repository
from tests.test_site_e2e import browser


@pytest.fixture
def seeded(tmp_path):
    db = tmp_path / 'signoff-e2e.sqlite3'
    repo = Repository(db)
    survey_id = save_review(repo, concept_survey())
    repo.sign_off(survey_id, 1, 'Priya N', acknowledge_open=True)       # version 1 was signed with items open
    second = concept_survey()
    second.title += ' revised'                                          # identical content would not be a new version
    assert save_review(repo, second, survey_id) == survey_id
    assert sorted(v['version'] for v in repo.detail(survey_id)['versions']) == [1, 2]   # version 2 starts unsigned
    repo.close()
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(create_app(db), log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.03)
    yield f'http://127.0.0.1:{sock.getsockname()[1]}', survey_id
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()


def test_version_two_is_unsigned_then_signs_with_the_open_items_acknowledged(browser, seeded):
    base, survey_id = seeded
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'{base}/review.html?id={survey_id}#share')
    page.wait_for_function('SC.reviewReady === true')
    assert 'Version 2 has not been signed off yet.' in page.locator('.signoff-card').inner_text()
    assert page.locator('.signoff-timeline li').all_inner_texts()[0].startswith('v1 signed off by Priya N')
    served = page.evaluate(f"fetch('/api/surveys/{survey_id}/versions/2').then(r => r.json())")
    page.get_by_role('button', name='Copy Slack post').click()
    assert page.evaluate('navigator.clipboard.readText()') == served['share']['slack_post']      # copied exactly as the server wrote it
    assert page.locator('#slack-post').inner_text() == served['share']['slack_post']
    open_now = served['overview']['verdict']['tiles']
    count = sum(open_now.values())
    assert page.locator('#signoff-submit').inner_text() == f'Sign off with {count} open items'
    page.locator('#signoff-name').fill('Lee Q')
    page.locator('#signoff-ack').check()
    page.locator('#signoff-submit').click()
    page.locator('.signed-line').wait_for()
    assert page.locator('.signed-line').inner_text().startswith('Signed off by Lee Q · ')
    after = page.evaluate(f"fetch('/api/surveys/{survey_id}/versions/2').then(r => r.json())")
    assert after['signoff']['signed_off_by'] == 'Lee Q' and after['signoff']['record']['acknowledged_open'] is True
    assert page.locator('#signoff-open').inner_text().startswith('Open now:')
    page.reload()
    page.wait_for_function('SC.reviewReady === true')
    assert page.locator('.signed-line').inner_text().startswith('Signed off by Lee Q · ')       # the record survives a reload
    assert not errors
    context.close()
