"""All browser traffic goes to a synthetic loopback server, never RedJade."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from surveycoach.reader import read_survey

FIXTURES = Path(__file__).parent / "fixtures" / "reader"


@pytest.fixture
def zoo():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append(("GET", self.path))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest/meta-data")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml" if self.path == "/asset.svg" else "text/html")
            self.end_headers()
            if self.path == "/asset.svg":
                self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><rect width="80" height="40" fill="blue"/></svg>')
            else:
                self.wfile.write((FIXTURES / "zoo.html").read_bytes())

        def do_POST(self):
            requests.append(("POST", self.path))
            self.send_response(500)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{server.server_port}", requests
    server.shutdown()
    server.server_close()
    worker.join()


def test_reader_walks_native_zoo_with_original_text_and_stable_ids(zoo):
    base, requests = zoo
    result = read_survey(base + "/choices", allow_test_local=True)
    assert result.coverage.stop_reason == "final_control"
    assert result.coverage.full_branching_coverage is False
    assert result.coverage.pages_captured == 4
    assert any("branch" in warning.lower() for warning in result.coverage.warnings)
    questions = result.snapshot.all_questions()
    assert [q.kind for q in questions] == ["single_choice", "multi_choice", "text_long", "numeric", "dropdown", "grid_single"]
    assert questions[0].text == "Which fruit — exactly?"
    assert [o.label for o in questions[0].options] == ["Apple & pear", "None of these"]
    assert questions[-1].rows == ["Texture", "Flavor"]
    assert [o.label for o in questions[-1].options] == ["Bad", "Good"]
    assert result.snapshot.pages[0].media[0].natural_w == 80
    assert result.snapshot.pages[0].media[0].alt == "A synthetic rectangle"
    assert not any(path == "/submitted" for _, path in requests)
    for capture in result.captures:
        assert capture.viewport_png.is_file()
        assert capture.observation_json.is_file()
        assert not capture.viewport_png.is_relative_to(Path.cwd())
    again = read_survey(base + "/choices", allow_test_local=True)
    assert [q.id for q in questions] == [q.id for q in again.snapshot.all_questions()]
    assert result.snapshot.content_hash == again.snapshot.content_hash


@pytest.mark.parametrize("stage,reason,pages", [
    ("screenout", "screen_out", 1), ("unsupported", "unsupported", 1),
    ("stuck", "blocked", 1), ("reveal", "same_page_change", 2),
])
def test_reader_stops_honestly(zoo, stage, reason, pages):
    result = read_survey(zoo[0] + "/" + stage, allow_test_local=True)
    assert result.coverage.stop_reason == reason
    assert result.coverage.pages_captured == pages
    assert result.coverage.warnings
    if stage == "screenout":
        assert result.snapshot.pages[0].kind == "screen_out"
    if stage == "reveal":
        assert any(q.text == "Explain your choice." for q in result.snapshot.all_questions())


def test_page_budget_is_enforced(zoo):
    result = read_survey(zoo[0] + "/choices", allow_test_local=True, max_pages=1)
    assert result.coverage.stop_reason == "page_limit"
    assert len(result.snapshot.pages) == 1
    assert not any(path == "/text" for _, path in zoo[1])


def test_subresource_redirect_write_and_final_endpoint_are_blocked(zoo, caplog):
    result = read_survey(zoo[0] + "/threats", allow_test_local=True)
    assert result.coverage.blocked_requests >= 4
    assert ("POST", "/save") not in zoo[1]
    assert ("GET", "/complete_response") not in zoo[1]
    assert "secret" not in caplog.text
    assert result.coverage.stop_reason == "final_control"


def test_aria_choice_controls_are_read_without_guessed_wording(zoo):
    result = read_survey(zoo[0] + "/aria", allow_test_local=True)
    assert result.coverage.stop_reason == "final_control"
    question = result.snapshot.all_questions()[0]
    assert question.text == "Pick a color."
    assert [o.label for o in question.options] == ["Blue", "Green"]


@pytest.mark.parametrize("stage", ["empty", "unlabeled"])
def test_unknown_or_unlabeled_pages_are_not_claimed_as_read(zoo, stage):
    result = read_survey(zoo[0] + "/" + stage, allow_test_local=True)
    assert result.coverage.stop_reason == "unsupported"
    assert len(result.captures) == 1
    assert result.coverage.full_branching_coverage is False


def test_no_usable_dropdown_returns_partial_error_not_fabricated_answer(zoo):
    result = read_survey(zoo[0] + "/disabled", allow_test_local=True)
    assert result.coverage.stop_reason == "reader_error"
    assert len(result.captures) == 1


@pytest.mark.parametrize("limit", [0, -1, 31, True])
def test_invalid_page_budget_is_rejected_before_launch(limit):
    with pytest.raises(ValueError, match="max_pages"):
        read_survey("http://127.0.0.1:1/test", allow_test_local=True, max_pages=limit)
