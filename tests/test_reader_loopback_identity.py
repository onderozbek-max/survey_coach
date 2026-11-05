"""Browser reads against a loopback page: naming (D6) and type detection reach the snapshot."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from surveycoach.reader import read_survey

PAGE = ("<!doctype html><title>{title}</title><main>{stimulus}<fieldset><legend>{question}</legend>"
        "<label><input type=radio name=a>Yes</label><label><input type=radio name=a>No</label>"
        "</fieldset><button>Submit</button></main>")


@pytest.fixture
def serve():
    servers = []

    def start(document_title, stimulus="", question="Pick one"):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(PAGE.format(title=document_title, stimulus=stimulus,
                                             question=question).encode())

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


def test_concept_then_purchase_intent_is_detected_but_the_type_is_only_a_default(serve):
    stimulus = ("<p>Alright, here is our idea.</p><h2>Acme Widget Tray</h2><p>Imagine a tray of widgets that "
                "snap together in seconds, ready for any weeknight dinner without any mess at all.</p>")
    url = serve("Surveys", stimulus, "How likely are you to buy the Acme Widget Tray?") + "/preview"
    result = read_survey(url, allow_test_local=True)
    assert result.snapshot.survey_type == "services_concept"
    assert result.snapshot.title == "Acme Widget Tray"   # first stimulus heading names it


def test_plain_page_stays_a_product_test(serve):
    result = read_survey(serve("Synthetic study", "", "Which did you like?") + "/preview", allow_test_local=True)
    assert result.snapshot.survey_type == "non_ihut_product"
