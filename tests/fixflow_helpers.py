"""A real localhost server holding the synthetic concept survey (no model calls, no outside access).

The fix flow runs here against the real queue, My changes and decisions the server builds, so these tests
never fake what the server owns. The survey is invented; nothing in it is real concept copy."""
import socket
import threading
import time

import pytest
import uvicorn

from surveycoach.server import create_app
from surveycoach.server.repository import Repository
from tests.test_queue import encoded


@pytest.fixture
def flow(tmp_path):
    """Yield (base_url, survey_id) for a server whose only survey is the synthetic concept test."""
    from concept_fixture import concept_survey
    from surveycoach.llm import FakeProvider
    from tests.test_judge_run import all_clear
    path = tmp_path / "flow.sqlite3"
    repo = Repository(path)
    snapshot = concept_survey()
    created = repo.submit(snapshot, ai=False)
    repo.finish(created["job_id"], encoded(snapshot))
    repo.close()
    app = create_app(path, provider=FakeProvider({"BatchOutput": all_clear}))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.03)
    yield f"http://127.0.0.1:{sock.getsockname()[1]}", created["id"]
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()


def open_flow(browser, flow, width=1440, height=900, hash="improve"):
    """Open the Fix step of the concept survey. Returns (context, page, errors)."""
    base, survey_id = flow
    context = browser.new_context(viewport={"width": width, "height": height}, permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{base}/review.html?id={survey_id}#{hash}")
    page.wait_for_function("SC.reviewReady === true", timeout=30000)
    page.locator("#coach h3").first.wait_for()
    return context, page, errors


def detail_of(page):
    return page.evaluate("structuredClone(SC.workspaceDetail)")
