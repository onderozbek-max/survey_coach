"""Loading regressions use synthetic loopback content only."""
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread

from surveycoach.reader import read_survey


def test_many_delayed_assets_load_concurrently_without_shell_capture():
    active = peak = 0
    lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            nonlocal active, peak
            if self.path == "/start":
                scripts = "".join(f'<script defer src="/asset-{i}.js"></script>' for i in range(26))
                body = (scripts + '<script>addEventListener("DOMContentLoaded", () => {'
                        'document.body.innerHTML = "<h1>Loaded synthetic question</h1>'
                        '<button>Finish</button>";});</script><body>Loading shell</body>').encode()
                content_type = "text/html"
            else:
                with lock:
                    active += 1
                    peak = max(peak, active)
                try:
                    time.sleep(0.45)
                    body = b"/* synthetic delayed asset */"
                finally:
                    with lock:
                        active -= 1
                content_type = "application/javascript"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        started = time.monotonic()
        result = read_survey(f"http://127.0.0.1:{server.server_port}/start", allow_test_local=True)
        elapsed = time.monotonic() - started
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert result.coverage.stop_reason == "final_control"
    assert result.coverage.pages_captured == 1
    assert "Loaded synthetic question" in result.snapshot.pages[0].text
    assert "Loading shell" not in result.snapshot.pages[0].text
    assert peak > 1
    assert elapsed < 10
