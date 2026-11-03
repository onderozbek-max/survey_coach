"""Synthetic passive capture only: no sockets, writes or advancement."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from surveycoach.reader.definition import adapt_definition, apply_definition, find_definition
from surveycoach.reader.models import Coverage, ReadResult
from surveycoach.reader.session import external_progression_stop, read_survey
from surveycoach.reader.transport import GuardedTransport
from surveycoach.snapshot import Media, Page, Question, SurveySnapshot

FIXTURE = Path(__file__).parent / "fixtures/reader/captured-definition.json"


def definition():
    return adapt_definition(find_definition(json.loads(FIXTURE.read_text())))


def test_complete_definition_retains_answers_and_conditions():
    parsed = definition()
    assert len(parsed.snapshot.pages) == 3
    questions = parsed.snapshot.all_questions()
    assert [q.id for q in questions] == ["q-fruit", "q-reasons", "q-widget", "q-french"]
    assert questions[0].text == "Which fruit & flavor?"
    assert [o.id for q in questions for o in q.options] == ["a-apple", "a-none", "a-taste", "a-price", "a-first"]
    assert [o.label for o in questions[1].options] == ["Taste", "Price"]
    assert questions[1].conditional and questions[2].conditional
    assert parsed.conditions["p-conditional"]["page"]["triggers"][0]["answers"] == ["a-apple"]
    assert parsed.conditions["p-conditional"]["questions"]["q-reasons"]["conditions"]


def test_unknown_types_and_missing_locale_remain_honest():
    parsed = definition()
    assert parsed.snapshot.all_questions()[2].kind == "unknown"
    assert parsed.snapshot.all_questions()[2].options[0].label == "First item"
    assert parsed.snapshot.all_questions()[3].text == "Dites-nous pourquoi."
    assert not parsed.wording_complete
    assert any("Unsupported question type" in w for w in parsed.warnings)
    assert any("Missing en_US" in w and "fr_CA" in w for w in parsed.warnings)
    french = adapt_definition(parsed.raw, locale="fr_CA")
    assert french.snapshot.all_questions()[0].text == "Quel fruit?"
    assert any("Missing fr_CA" in w for w in french.warnings)


def test_definition_wording_is_not_visual_or_path_coverage(tmp_path):
    raw = definition().raw
    raw["data"]["pages"][2]["questions"][0]["text"]["en_US"] = "Tell us why."
    parsed = adapt_definition(raw)
    result = ReadResult(snapshot=SurveySnapshot(title="", pages=[]), coverage=Coverage(), capture_dir=tmp_path)
    apply_definition(result, parsed)
    assert result.coverage.definition_wording_complete
    assert result.coverage.pages_defined == 3
    assert result.coverage.questions_defined == 4
    assert result.coverage.pages_captured == 0
    assert not result.coverage.paths_verified
    assert not result.coverage.visual_media_verified
    assert not result.coverage.full_branching_coverage
    assert result.definition == parsed.raw
    assert external_progression_stop(allow_test_local=False)


@pytest.mark.parametrize("page_id,question_id,merged", [
    ("p-intro", "q-fruit", True), ("hash", "q-fruit", False), ("p-intro", "hash", False),
])
def test_merge_requires_known_page_and_question_ids(tmp_path, page_id, question_id, merged):
    page = Page(id=page_id, position=0, kind="question", media=[Media(alt="Observed")],
                questions=[Question(id=question_id, text="Not authoritative", kind="text_short", fits_one_screen=True)])
    result = ReadResult(snapshot=SurveySnapshot(title="", pages=[page]), coverage=Coverage(), capture_dir=tmp_path)
    apply_definition(result, definition())
    target = result.snapshot.pages[0]
    assert target.questions[0].text == "Which fruit & flavor?"
    assert bool(target.media) is merged
    assert (target.questions[0].fits_one_screen is True) is merged
    assert result.coverage.rendered_definition_pages == (["p-intro"] if merged else [])
    assert len(result.snapshot.all_questions()) == 4


def test_transport_captures_only_existing_permitted_get(monkeypatch):
    calls = []

    class Response:
        status = 200

        def read(self, limit):
            calls.append(("read", limit))
            return FIXTURE.read_bytes()

        def getheaders(self):
            return [("Content-Type", "application/json")]

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method, path, headers, body=None):
            calls.append((method, path))

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("http.client.HTTPConnection", Connection)
    guard = GuardedTransport("http://127.0.0.1:9000/start", local=True, approval=False, coverage=Coverage())
    request = SimpleNamespace(url="http://127.0.0.1:9000/definition", method="GET", headers={})
    fulfilled, blocked = [], []
    route = SimpleNamespace(request=request, fulfill=lambda **kw: fulfilled.append(kw), abort=blocked.append)
    guard(route)
    assert len(guard.definition.snapshot.pages) == 3
    assert calls[0] == ("GET", "/definition")
    assert len(fulfilled) == 1 and not blocked
    original = guard.definition
    guard.observe_response(b'{"response":{"questionnaire":{"data":{"pages":[]}}}}')
    assert guard.definition is original
    request.method = "POST"
    guard(route)
    assert len(calls) == 2  # GET + bounded read; POST never reaches connection
    assert blocked


@pytest.mark.parametrize("payload", [b"not json", b'{"response":{"questionnaire":{"data":{"pages":[{}]}}}}'])
def test_bad_definition_leaves_rendered_reader_usable(payload):
    guard = GuardedTransport("http://127.0.0.1:9000/start", local=True, approval=False, coverage=Coverage())
    guard.observe_response(payload)
    assert guard.definition is None
    assert any("unreadable" in w for w in guard.coverage.warnings)


def test_session_uses_definition_without_answering_or_advancing(monkeypatch, tmp_path):
    from contextlib import nullcontext
    import playwright.async_api as browser_api
    from unittest.mock import AsyncMock

    guards = []
    observed = {"title": "Rendered first page", "text": "First page only", "groups": [],
                "nav": [{"label": "Next", "disabled": False, "id": "next"}],
                "screenout": False, "unsupported": False, "media": []}

    class FakePage:
        def on(self, *args):
            pass

        async def goto(self, *args, **kwargs):
            guards[0].__self__.observe_response(FIXTURE.read_bytes())

        async def wait_for_timeout(self, *args):
            pass

        async def evaluate(self, *args):
            return observed

        async def screenshot(self, *, path, **kwargs):
            Path(path).write_bytes(b"synthetic screenshot")

        def locator(self, *args):
            pytest.fail("passive definition read must not answer or advance")

    class FakeContext:
        def set_default_timeout(self, *args):
            pass

        async def route(self, pattern, guard):
            guards.append(guard)

        async def route_web_socket(self, *args):
            pass

        async def new_page(self):
            return FakePage()

    browser = SimpleNamespace(new_context=AsyncMock(return_value=FakeContext()), close=AsyncMock())
    fake_playwright = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))
    monkeypatch.setattr(browser_api, "async_playwright", lambda: nullcontext(fake_playwright))
    monkeypatch.setattr("surveycoach.reader.session.tempfile.mkdtemp", lambda **kw: str(tmp_path))
    result = read_survey("http://127.0.0.1:9000/start", allow_test_local=True)
    assert result.coverage.stop_reason == "definition_captured"
    assert result.coverage.pages_captured == 1
    assert result.coverage.pages_defined == 3
    assert len(result.snapshot.all_questions()) == 4
    assert not result.coverage.rendered_definition_pages


def test_missing_wording_and_duplicate_ids():
    raw = definition().raw
    raw["data"]["pages"][0]["questions"][0]["text"] = {}
    parsed = adapt_definition(raw)
    assert not parsed.wording_complete
    assert parsed.snapshot.all_questions()[0].text == ""
    raw["data"]["pages"][1]["id"] = "p-intro"
    with pytest.raises(ValueError, match="Duplicate"):
        adapt_definition(raw)
