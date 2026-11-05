"""Offline participant paths may revisit generic follow-ups, but not loop forever."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from surveycoach.reader import read_survey
from surveycoach.reader.extract import extract_page


@pytest.fixture
def survey():
    servers = []

    def start(sequence, *, cycle=False, source_ids=False):
        html = '''<main></main><script>
        const sequence=SEQUENCE, cycle=CYCLE, sourceIds=SOURCE_IDS;
        let index=0;
        function render() {
          const value=sequence[index % sequence.length];
          const root=document.querySelector('main');
          if(sourceIds) root.dataset.pageId=value;
          if(value==='end') { root.innerHTML='<h1>Thank you.</h1>'; return; }
          root.innerHTML=`<h2>${value==='followup' ? '' : value}</h2>
            <fieldset ${sourceIds ? 'data-question-id="q-'+value+'"' : ''}>
            <legend>${value==='followup' ? 'What would make this tray more appealing?' : 'Would you add this tray to your cart?'}</legend>
            <label><input type="radio" name="choice" value="yes">Yes</label>
            <label><input type="radio" name="choice" value="no">No</label></fieldset>
            <button onclick="if(cycle || index+1<sequence.length) {index++; render()}">Next</button>`;
        }
        render();</script>'''
        html = html.replace('SEQUENCE', json.dumps(sequence)).replace('CYCLE', json.dumps(cycle))
        html = html.replace('SOURCE_IDS', json.dumps(source_ids)).encode()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(html)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        servers.append((server, worker))
        return f'http://127.0.0.1:{server.server_port}/'

    yield start
    for server, worker in servers:
        server.shutdown()
        server.server_close()
        worker.join()


def assert_unique(result):
    pages = result.snapshot.pages
    questions = result.snapshot.all_questions()
    assert len({p.id for p in pages}) == len(pages)
    assert len({q.id for q in questions}) == len(questions)
    options = [o for q in questions for o in q.options]
    assert len({o.id for o in options}) == len(options)
    assert [c.page_id for c in result.captures] == [p.id for p in pages]
    assert [p.position for p in pages] == list(range(len(pages)))


@pytest.mark.parametrize('source_ids', [False, True])
def test_generic_followup_revisited_after_distinct_concepts_is_captured(survey, source_ids):
    sequence = ['Concept A', 'followup', 'Concept B', 'followup', 'Concept C', 'end']
    url = survey(sequence, source_ids=source_ids)
    first = read_survey(url, allow_test_local=True, participate=True)
    assert first.coverage.stop_reason == 'path_end'
    assert first.coverage.pages_captured == 6
    assert len(first.snapshot.all_questions()) == 5
    assert_unique(first)
    followups = [first.snapshot.pages[i] for i in (1, 3)]
    assert followups[0].text == followups[1].text
    assert followups[0].questions[0].text == followups[1].questions[0].text
    if source_ids:
        assert followups[0].id == 'followup'
        assert followups[0].questions[0].id == 'q-followup'
    again = read_survey(url, allow_test_local=True, participate=True)
    assert first.snapshot.content_hash == again.snapshot.content_hash
    assert [p.id for p in first.snapshot.pages] == [p.id for p in again.snapshot.pages]


def test_repeated_transition_cycle_stops_on_third_traversal(survey):
    result = read_survey(survey(['Concept A', 'followup'], cycle=True),
                         allow_test_local=True, participate=True)
    assert result.coverage.stop_reason == 'loop'
    assert result.coverage.pages_captured == 5
    assert any('transition' in warning.lower() for warning in result.coverage.warnings)
    assert_unique(result)


def test_stuck_page_does_not_consume_revisit_budget(survey):
    result = read_survey(survey(['Concept A']), allow_test_local=True, participate=True)
    assert result.coverage.stop_reason == 'blocked'
    assert result.coverage.pages_captured == 1


def test_consecutive_exact_state_stops_even_if_advancement_claims_success(survey, monkeypatch):
    async def unchanged(*args, **kwargs):
        return 'advanced'

    monkeypatch.setattr('surveycoach.reader.session.advance', unchanged)
    result = read_survey(survey(['A']), allow_test_local=True, participate=True)
    assert result.coverage.stop_reason == 'loop'
    assert result.coverage.pages_captured == 1


def test_revisit_still_respects_page_budget(survey):
    result = read_survey(survey(['A', 'followup', 'B', 'followup', 'C', 'end']),
                         allow_test_local=True, participate=True, max_pages=4)
    assert result.coverage.stop_reason == 'page_limit'
    assert result.coverage.pages_captured == 4
    assert_unique(result)


def test_extract_collision_allocation_preserves_first_source_ids():
    observation = {'source_page_id': 'source-page', 'text': 'Observed wording',
                   'groups': [{'source_id': 'source-question', 'prompt': 'Buy?',
                               'kind': 'single_choice', 'required': False,
                               'items': [{'label': 'Yes', 'row': ''}]}],
                   'screenout': False, 'media': []}
    first = extract_page(observation, 0)
    second = extract_page(observation, 1, existing_pages=[first])
    third = extract_page(observation, 2, existing_pages=[first, second])
    assert first.id == 'source-page'
    assert first.questions[0].id == 'source-question'
    assert len({p.id for p in (first, second, third)}) == 3
    assert len({p.questions[0].id for p in (first, second, third)}) == 3
    assert len({p.questions[0].options[0].id for p in (first, second, third)}) == 3
    assert extract_page(observation, 1, existing_pages=[first]) == second
    # Question source IDs may also be reused on different source pages.
    other = extract_page(dict(observation, source_page_id='other-page'), 1, existing_pages=[first])
    assert other.id == 'other-page'
    assert other.questions[0].id != first.questions[0].id
    # Even an existing source ID matching a generated occurrence cannot collide.
    occupied = first.model_copy(update={'id': second.id})
    next_page = extract_page(observation, 2, existing_pages=[first, occupied])
    assert next_page.id not in {first.id, occupied.id}
