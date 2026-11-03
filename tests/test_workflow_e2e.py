"""Synthetic localhost workflow acceptance. No model calls or external survey access."""
import socket
import threading
from pathlib import Path

import pytest
import uvicorn

from surveycoach.server import create_app
from surveycoach.snapshot import SurveySnapshot
from tests.test_site_e2e import browser

ROOT = Path(__file__).parent.parent


@pytest.fixture
def studio(tmp_path):
    from surveycoach.llm import FakeProvider
    from tests.test_judge_run import all_clear
    app = create_app(tmp_path / "studio.sqlite3", provider=FakeProvider({"BatchOutput": all_clear}))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    import time
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.03)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()


def test_import_saved_choices_phone_and_updated_review(browser, studio):
    context = browser.new_context(viewport={"width": 390, "height": 844}, permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(studio + "/local.html")
    page.get_by_label("Survey snapshot file (.json)").set_input_files(str(ROOT / "fixtures/boxer-briefs.json"))
    page.get_by_role("button", name="Check survey").click()
    page.wait_for_url("**/review.html?**", timeout=30000)
    page.locator('#issues-view > summary').click()
    jump = page.locator('.issue-jump').first
    headline = jump.locator('strong').inner_text()
    jump.click()
    assert page.locator('#coach .card').count() == 1
    page.get_by_role('button', name='Keep mine', exact=True).click()
    page.get_by_label('Reason for keeping', exact=False).fill('Required for comparability')
    page.get_by_role('button', name='Save reason & keep mine').click()
    page.locator('.accepted-risk').wait_for()
    page.reload()
    page.locator('#issues-view > summary').click()
    page.locator('.issue-jump').filter(has_text=headline).first.click()
    assert page.get_by_label('Reason for keeping', exact=False).input_value() == 'Required for comparability'
    assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
    assert page.locator('#copy-all').is_disabled()
    assert page.locator('.phone-screen').is_visible()
    assert 'Local review' in page.locator('#strip').inner_text()
    page.locator('#check-again').click()
    page.locator('.advanced-recheck > summary').click()
    before = page.url
    updated = SurveySnapshot.model_validate_json((ROOT / "fixtures/boxer-briefs.json").read_text())
    updated.title += " revised"
    page.get_by_label("Updated snapshot file (.json)").set_input_files({"name": "revised.json", "mimeType": "application/json", "buffer": updated.model_dump_json().encode()})
    page.get_by_role("button", name="Start next round").click()
    page.wait_for_url(lambda url: str(url) != before, timeout=30000)
    page.locator('.round-timeline').wait_for()
    assert page.locator('.round-timeline a').count() == 2
    assert '/versions/2/summary' in page.locator('#sign-off').get_attribute('href')
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    context.close()
