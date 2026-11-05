"""Repeated concept trials differ by stimulus, not question/option wording."""
import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from playwright.sync_api import sync_playwright

from surveycoach.reader import read_survey
from surveycoach.reader.extract import extract_page, fingerprint
from surveycoach.reader.observe import OBSERVE


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            # No server or external traffic: the entire survey is synthetic DOM.
            page.route("**/*", lambda route: route.abort())
            page.set_content('''<main>
              <section id="stimulus"><h2>Family tray</h2>
                <p>Four cheese quesadillas with roasted tomato salsa.</p></section>
              <fieldset><legend>Would you add this tray to your cart?</legend>
                <label><input type="radio" name="cart" value="yes">Yes</label>
                <label><input type="radio" name="cart" value="no">No</label>
              </fieldset>
              <label>Why?<textarea aria-describedby="answer-feedback"></textarea></label>
              <p role="alert" id="answer-feedback"></p>
              <p id="error"></p><div role="timer">30 seconds remaining</div>
              <div aria-live="polite" id="answer-status"></div>
              <output id="answer-echo"></output><button>Next</button>
            </main>''')
            yield page
        finally:
            browser.close()


def observe(page):
    return page.evaluate(OBSERVE)


def test_repeated_question_with_different_stimulus_has_distinct_state(page):
    first = observe(page)
    page.locator("#stimulus p").evaluate(
        "e => e.textContent = 'Smoky chicken quesadillas with avocado crema.'")
    second = observe(page)
    assert first["groups"] == second["groups"]
    assert first["state_key"] != second["state_key"]
    assert fingerprint(first) != fingerprint(second)
    assert extract_page(first, 0).questions[0].id != extract_page(second, 1).questions[0].id


def test_answer_feedback_and_timer_changes_do_not_change_state(page):
    first = observe(page)
    page.locator("input[value=yes]").check()
    page.locator("textarea").fill("SurveyCoach test answer")
    page.evaluate('''() => {
      document.querySelector('[role=timer]').textContent = '29 seconds remaining';
      document.querySelector('#answer-feedback').textContent = 'Please add more detail.';
      document.querySelector('#error').textContent = 'Please answer correctly.';
      document.querySelector('#answer-status').textContent = 'Answer saved';
      document.querySelector('#answer-echo').textContent = 'SurveyCoach test answer';
      document.querySelector('button').disabled = true;
    }''')
    second = observe(page)
    assert first["text"] != second["text"]
    assert first["groups"] != second["groups"]
    assert first["state_key"] == second["state_key"]
    assert fingerprint(first) == fingerprint(second)


def test_exact_repeat_and_restored_stimulus_keep_deterministic_ids(page):
    first = observe(page)
    assert observe(page)["state_key"] == first["state_key"]
    page.locator("#stimulus h2").evaluate("e => e.textContent = 'Party tray'")
    assert observe(page)["state_key"] != first["state_key"]
    page.locator("#stimulus h2").evaluate("e => e.textContent = 'Family tray'")
    repeated = observe(page)
    assert fingerprint(first) == fingerprint(repeated)
    assert extract_page(first, 0).id == extract_page(repeated, 1).id
    assert extract_page(first, 0).questions == extract_page(repeated, 1).questions


def test_hidden_stimulus_is_not_identity(page):
    first = observe(page)
    page.evaluate("document.body.insertAdjacentHTML('beforeend', '<p hidden>Other concept</p>')")
    assert observe(page)["state_key"] == first["state_key"]


def test_source_ids_are_preserved_when_context_changes(page):
    page.locator("main").evaluate("e => e.dataset.pageId = 'source-page'")
    page.locator("fieldset").evaluate("e => e.dataset.questionId = 'source-question'")
    first = observe(page)
    page.locator("#stimulus p").evaluate("e => e.textContent = 'A different concept.'")
    second = observe(page)
    assert fingerprint(first) != fingerprint(second)
    for observation in (first, second):
        extracted = extract_page(observation, 0)
        assert extracted.id == "source-page"
        assert extracted.questions[0].id == "source-question"


@pytest.mark.parametrize("repeat,reason,pages", [(False, "path_end", 3), (True, "loop", 2)])
def test_reader_advances_concepts_but_still_detects_exact_repeat(repeat, reason, pages):
    html = '''<main id="content"></main><script>
      let trial = 0;
      function render() {
        if (trial === 2 && !REPEAT) {
          document.querySelector('main').innerHTML = '<h1>Thank you.</h1>'; return;
        }
        const concept = trial % 2 === 0 ? 'Cheese tray with salsa.' : 'Chicken tray with crema.';
        document.querySelector('main').innerHTML = `<h2>${concept}</h2>
          <fieldset><legend>Would you add this tray to your cart?</legend>
          <label><input type="radio" name="cart" value="yes">Yes</label>
          <label><input type="radio" name="cart" value="no">No</label></fieldset>
          <button onclick="trial++; render()">Next</button>`;
      }
      render();
    </script>'''.replace("REPEAT", str(repeat).lower()).encode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        result = read_survey(f"http://127.0.0.1:{server.server_port}/", allow_test_local=True)
        assert result.coverage.stop_reason == reason
        assert result.coverage.pages_captured == pages
        assert len(result.snapshot.all_questions()) == 2
        first, second = result.snapshot.pages[:2]
        assert first.id != second.id
        assert first.questions[0].text == second.questions[0].text
        assert first.questions[0].options[0].label == second.questions[0].options[0].label
        assert "Cheese tray with salsa." in first.text
        assert "Chicken tray with crema." in second.text
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_fingerprint_uses_state_identity_not_mutable_observation_fields():
    observation = {"state_key": json.dumps([None, [[None, "Buy it?", "single_choice", ["Yes"]]],
                                            "Family tray with salsa"]),
                   "text": "Family tray with salsa Buy it? Yes", "groups": []}
    answered = copy.deepcopy(observation)
    answered["text"] += " Answer saved. 29 seconds remaining."
    answered["groups"] = [{"items": [{"checked": True, "value": "yes"}]}]
    assert fingerprint(observation) == fingerprint(answered)
    other_concept = dict(observation, state_key=observation["state_key"].replace("salsa", "crema"))
    assert fingerprint(observation) != fingerprint(other_concept)
