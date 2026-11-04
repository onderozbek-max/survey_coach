"""Specific, scoped member-experience evidence; navigation stays canonical."""
import pytest

from builders import page, question, survey
from tests.test_signals import finding, overview, result, signal


DIMENSIONS = [('clarity', '3.4'), ('honest', '4.2'), ('energy', '8.2'),
              ('tone', '9.1'), ('phone', '6.2')]


@pytest.mark.parametrize('sid,cid', DIMENSIONS)
def test_summary_leads_with_highest_priority_finding_and_exact_question_label(sid, cid):
    snapshot = survey(page(1, question(qid='q1', label='Q8a')), page(2))
    findings = [finding('minor', cid, 'worth_improving', headline='A smaller issue', page_id='p2'),
                finding('urgent', cid, headline='The actual urgent issue', question_id='q1',
                        page_id='p2', evidence='Exact captured words'),
                finding('later', cid, headline='Another urgent issue', page_id='p2')]
    card = signal(overview({cid: result(.5)}, findings, snapshot=snapshot), sid)
    assert card['summary'] == 'Q8a · Screen 1: The actual urgent issue'
    assert card['lead'] == {'headline': 'The actual urgent issue', 'location': 'Q8a · Screen 1'}
    assert card['findings'] == ['minor', 'urgent', 'later']
    assert card['pages'] == ['p1', 'p2']
    assert card['summary'] not in card['details']
    assert any('Exact captured words' in text for text in card['details'])
    assert any('3 recorded findings' in text for text in card['details'])


def test_page_and_whole_survey_findings_use_canonical_locations():
    snapshot = survey(page(1, question(qid='q1', label='Q8'), question(qid='q2', label='Q18')))
    card = signal(overview(findings=[finding(cid='3.4', page_id='p1')], snapshot=snapshot), 'clarity')
    assert card['summary'] == 'Q8–Q18 · Screen 1: An answer is missing'
    card = signal(overview(findings=[finding(cid='3.4')]), 'clarity')
    assert card['summary'] == 'Whole survey: An answer is missing'


@pytest.mark.parametrize('sid,cid', DIMENSIONS)
def test_unknown_names_dimension_specific_missing_evidence(sid, cid):
    card = signal(overview(), sid)
    assert card['state'] == 'unknown'
    assert card['summary'] != 'Not checked yet.'
    assert card['name'].lower().split()[0] in card['summary'].lower()
    assert card['coverage']['checked'] == 0
    assert cid in card['coverage']['missing']
    assert any('Not assessed:' in text for text in card['details'])


@pytest.mark.parametrize('sid,cid', DIMENSIONS)
def test_checked_summary_names_only_assessed_check_and_discloses_missing(sid, cid):
    card = signal(overview({cid: result()}), sid)
    assert card['state'] == 'strong'
    assert '1 of ' in card['summary']
    assert 'assessed' in card['summary']
    assert card['coverage']['checked'] == 1
    assert card['coverage']['total'] > 1
    assert any('checked evidence only' in text for text in card['details'])
    assert any('Not assessed:' in text for text in card['details'])
    assert not any(word in card['summary'] for word in ['Every member', 'Comfortable on a phone'])


def test_low_credit_without_finding_is_not_an_invented_positive():
    card = signal(overview({'3.4': result(0)}), 'clarity')
    assert 'Grammar and spelling' in card['summary']
    assert '0%' in card['summary']
    assert 'Looking good' not in card['summary']


def test_not_applicable_is_not_missing_and_legacy_ai_is_not_checked():
    card = signal(overview({'3.1': {'fraction': 1}, '3.4': result(),
                            '3.5': result(applies=False)}), 'clarity')
    assert card['coverage'] == {'checked': 1, 'total': 5,
                                'missing': ['3.1', '3.2', '3.3'],
                                'not_applicable': ['3.5']}
    assert any('Not applicable: Consistent terms' in text for text in card['details'])


def test_absorbed_and_handled_findings_do_not_become_a_verified_pass():
    card = signal(overview({'4.2': result()}, [finding(cid='4.2', absorbed_by='root')]), 'honest')
    assert 'An answer is missing' in card['summary']
    assert card['findings'] == []
    card = signal(overview({'4.2': result()}, [finding()], {'issue': {'action': 'pick'}}), 'honest')
    assert 'An answer is missing' in card['summary']
    assert any('not verified fixes' in text for text in card['details'])


def cross_dimension_detail():
    from surveycoach.rubric import load_rubric
    from surveycoach.server.present import enrich
    snapshot = survey(page(1, question()))
    return enrich({'snapshot': snapshot.model_dump(mode='json'), 'review': {
        'results': {}, 'findings': [
            finding('primary', 'B2', page_id='p1', headline='Add a valid answer'),
            finding('child', '8.4', 'worth_improving', page_id='p1',
                    headline='Some members cannot answer this relevantly')]}}, load_rubric())


def test_cross_dimension_absorbed_evidence_resolves_primary_navigation():
    card = signal(cross_dimension_detail()['overview'], 'energy')
    assert card['findings'] == [] and card['pages'] == []  # marker contract unchanged
    assert card['navigation'] == {'fingerprints': ['primary'], 'pages': ['p1']}


@pytest.mark.parametrize('parent', ['missing', 'issue'])
def test_unresolvable_or_cyclic_absorption_does_not_promise_navigation(parent):
    card = signal(overview(findings=[finding(absorbed_by=parent)]), 'honest')
    assert card['navigation'] is None
    assert not any('navigation opens' in text for text in card['details'])


def test_real_null_fraction_blockers_are_complete_but_missing_unassessed_are_not():
    from surveycoach.review import run_review
    review = run_review(survey(page(1, question()))).model_dump(mode='json')
    assert review['results']['B4'] == dict(criterion_id='B4', fraction=None,
        applies=True, assessed=True, findings=review['results']['B4']['findings'])
    out = overview(review['results'])
    assert not any('No complete blocker assessment:' in text
                   for text in signal(out, 'tone')['details'])
    assert any('Broken time promise' in text for text in signal(out, 'time')['details'])
    assert any('Leading question on the main research topic' in text
               for text in signal(out, 'honest')['details'])
    review['results']['B4']['applies'] = False
    card = signal(overview(review['results']), 'tone')
    assert any('Blocker not applicable: No intro page' in text for text in card['details'])
    assert not any('No complete blocker assessment:' in text for text in card['details'])
