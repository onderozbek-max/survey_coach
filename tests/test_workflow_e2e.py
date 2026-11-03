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
    page.get_by_role("button", name="Start review").click()
    page.wait_for_url("**/review.html?**", timeout=30000)
    page.get_by_role("heading", name="Your fix checklist").wait_for()
    first = page.locator(".fix-card").filter(has=page.get_by_role("button", name="Copy chosen fix", exact=True)).first
    select = first.locator("select")
    select.select_option("original")
    first.get_by_label("Reason for keeping", exact=False).fill("Required for comparability")
    first.get_by_label("Reason for keeping", exact=False).blur()
    first.get_by_text("Saved on this computer.", exact=True).wait_for()
    page.reload()
    first = page.locator(".fix-card").first
    assert first.locator("select").input_value() == "original"
    assert first.get_by_label("Reason for keeping", exact=False).input_value() == "Required for comparability"
    assert first.get_by_role("button", name="Copy chosen fix").is_disabled()
    page.get_by_role("link", name="Open phone preview").click()
    page.locator(".phone-screen").wait_for()
    assert "Local review" in page.locator("#strip").inner_text()
    page.get_by_role("link", name="Saved fix checklist").click()
    before = page.url
    updated = SurveySnapshot.model_validate_json((ROOT / "fixtures/boxer-briefs.json").read_text())
    updated.title += " revised"
    page.get_by_label("Or updated snapshot file (.json)").set_input_files({"name": "revised.json", "mimeType": "application/json", "buffer": updated.model_dump_json().encode()})
    page.get_by_role("button", name="Check again").click()
    page.wait_for_url(lambda url: str(url) != before, timeout=30000)
    page.get_by_text("Since the previous version", exact=True).wait_for()
    assert page.get_by_label("Review version").input_value() == "2"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    context.close()
