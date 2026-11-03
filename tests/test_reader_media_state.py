"""RedJade's inline uploader auto-saves; Add Media creates another answer."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from surveycoach.reader.actions import answer_groups
from surveycoach.reader.models import Coverage
from surveycoach.reader.observe import OBSERVE
from surveycoach.reader.requirements import UnmetRequirement
from surveycoach.reader.transport import GuardedTransport


HTML = b'''<!doctype html><html><body>
<div class="taker-question-slot-container"><div data-testid="media-uploader">
<label>Photo<input type="file" accept="image/png"></label>
<label>Comments<textarea required></textarea></label>
<button class="media-upload-add-button" onclick="window.extraAnswers++">Add Media</button>
</div></div><button id="next">Next</button>
<script>
window.extraAnswers = 0; window.attached = false; window.comment = '';
const file = document.querySelector('input');
file.onchange = async () => {
  const data = new FormData(); data.append('file', file.files[0]);
  const response = await fetch('/file-proxy/attach-multipart', {method:'POST', body:data});
  if (response.ok) window.attached = true;
  file.value = '';
};
document.querySelector('textarea').oninput = event => { window.comment = event.target.value; };
document.querySelector('#next').onclick = () => {
  window.accepted = window.attached && !!window.comment && window.extraAnswers === 0;
};
</script></body></html>'''


@pytest.fixture
def media_server():
    state = {'bodies': [], 'status': 200}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML)

        def do_POST(self):
            state['bodies'].append(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(state['status'])
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f'http://127.0.0.1:{server.server_port}/', state
    server.shutdown()
    server.server_close()
    worker.join()


async def exercise(base, state, tmp_path, *, rejected=False):
    from playwright.async_api import async_playwright

    guard = GuardedTransport(base, local=True, approval=False, coverage=Coverage())
    # Isolated loopback fixture permits its synthetic write, with all routing and
    # serialization still going through the production transport unchanged.
    guard.participate = True
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context = await browser.new_context(service_workers='block')
            await context.route('**/*', guard.handle_async)
            page = await context.new_page()
            await page.goto(base)
            observation = await page.evaluate(OBSERVE)
            if rejected:
                with pytest.raises(UnmetRequirement, match='rejected'):
                    await answer_groups(page, observation, upload_dir=tmp_path)
                assert await page.evaluate('window.extraAnswers') == 0
                assert len(state['bodies']) == 1
                return
            committed = await answer_groups(page, observation, upload_dir=tmp_path)
            assert committed is False  # auto-save does not remove/reveal controls
            await page.locator('#next').click()
            assert await page.evaluate('window.accepted') is True
            assert await page.evaluate('window.extraAnswers') == 0
            assert await page.locator('input').evaluate('e => e.files.length') == 0
            # The widget resets the native input after saving. A bounded repair
            # must not re-upload or create a new missing answer.
            await answer_groups(page, await page.evaluate(OBSERVE), upload_dir=tmp_path, skip_upload=True)
            assert len(state['bodies']) == 1
            assert await page.evaluate('window.extraAnswers') == 0
        finally:
            await browser.close()


def test_inline_media_saves_real_png_bytes_without_adding_empty_answer(media_server, tmp_path):
    base, state = media_server
    asyncio.run(exercise(base, state, tmp_path))
    body = state['bodies'][0]
    assert b'\x89PNG\r\n\x1a\n' in body
    assert b'Content-Type: image/png' in body
    assert b'filename="surveycoach-test-placeholder.png"' in body


def test_rejected_inline_upload_stops_before_next_or_add_media(media_server, tmp_path):
    base, state = media_server
    state['status'] = 400
    asyncio.run(exercise(base, state, tmp_path, rejected=True))
