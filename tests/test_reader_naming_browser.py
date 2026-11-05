"""D6 end to end: RedJade's generic "Surveys" document title never names a survey (loopback only)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from surveycoach.reader import read_survey

PAGE = (b"<!doctype html><title>%s</title><main><fieldset><legend>Pick one</legend>"
        b"<label><input type=radio name=a>Yes</label><label><input type=radio name=a>No</label>"
        b"</fieldset><button>Submit</button></main>")


@pytest.fixture
def serve():
    servers = []

    def start(document_title):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(PAGE % document_title.encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_port}"
    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_generic_document_title_is_replaced_by_the_humanized_slug(serve):
    result = read_survey(serve("Surveys") + "/InsightsHMSQuesadillaTray", allow_test_local=True)
    assert result.snapshot.title == "Quesadilla Tray"


def test_specific_document_title_is_kept_when_nothing_better_is_known(serve):
    result = read_survey(serve("Synthetic study") + "/preview", allow_test_local=True)
    assert result.snapshot.title == "Synthetic study"


def test_generic_title_is_kept_only_as_a_last_resort_so_the_read_still_works(serve):
    result = read_survey(serve("Surveys") + "/preview", allow_test_local=True)
    assert result.snapshot.title == "Surveys"
