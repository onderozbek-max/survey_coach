"""Normalized quality uses saved CheckResult evidence, never choices or the raw score."""
from copy import deepcopy

import pytest

from surveycoach.rubric import load_rubric
from surveycoach import quality


def result(cid, fraction=None, **extra):
    return dict(criterion_id=cid, fraction=fraction, applies=True, assessed=True, findings=[], **extra)


def test_half_credit_is_normalized_and_unknown_weight_is_separate():
    rubric = load_rubric()
    criterion = next(c for c in rubric.criteria if c.active)
    q = quality.build_quality({'results': {criterion.id: result(criterion.id, .5)}}, rubric)
    assert q['score'] == 50
    assert q['earned_points'] == criterion.points / 2
    assert q['assessed_points'] == criterion.points
    assert q['applicable_points'] == rubric.active_points
    assert q['coverage_percent'] == criterion.points
    assert q['unchecked_points'] == 100 - criterion.points
    assert q['provisional']


def complete(rubric):
    return {'results': {c.id: result(c.id, 1) for c in rubric.criteria if c.active}
            | {b.id: result(b.id) for b in rubric.blockers}}


def test_na_excluded_zero_assessed_is_null_and_no_evidence_is_not_a_pass():
    rubric = load_rubric()
    review = {'results': {c.id: dict(result(c.id), applies=False) for c in rubric.criteria}}
    q = quality.build_quality(review, rubric)
    assert q['score'] is None
    assert q['coverage_percent'] == 0
    assert q['applicable_points'] == q['assessed_points'] == 0
    assert q['provisional']
    assert quality.build_quality({}, rubric)['score'] is None


def test_full_coverage_na_and_pending_blockers_are_independent():
    rubric = load_rubric()
    review = complete(rubric)
    criterion = next(c for c in rubric.criteria if c.active)
    review['results'][criterion.id]['applies'] = False
    q = quality.build_quality(review, rubric)
    assert q['score'] == q['coverage_percent'] == 100
    assert q['applicable_points'] == 100 - criterion.points
    assert not q['provisional']
    del review['results'][rubric.blockers[0].id]
    q = quality.build_quality(review, rubric)
    assert q['score'] == q['coverage_percent'] == 100
    assert q['provisional'] and q['blockers']['unchecked'] == 1
    review['results'][rubric.blockers[1].id]['assessed'] = False
    assert quality.build_quality(review, rubric)['blockers']['unchecked'] == 2


def test_unassessed_and_unknown_fractions_cannot_earn_points():
    rubric = load_rubric()
    review = complete(rubric)
    criteria = [c for c in rubric.criteria if c.active][:2]
    review['results'][criteria[0].id]['assessed'] = False
    review['results'][criteria[1].id]['fraction'] = None
    q = quality.build_quality(review, rubric)
    assert q['score'] == 100
    assert q['unchecked_points'] == sum(c.points for c in criteria)
    assert sum(d['assessed_points'] for d in q['dimensions']) == q['assessed_points']


def test_blockers_and_score_stable_under_choices_and_raw_score_changes():
    rubric = load_rubric()
    review = complete(rubric)
    review['results'][rubric.blockers[0].id]['findings'] = [{'severity': 'must_fix'}]
    before = deepcopy(review)
    q = quality.build_quality(review, rubric)
    assert q['blockers']['flagged'] == 1
    review.update(decisions={'x': {'action': 'pick'}, 'y': {'action': 'keep'}}, scorecard={'score': 0}, findings=[])
    assert quality.build_quality(review, rubric) == q
    assert before['results'] == review['results']


def test_exact_weighted_fraction_not_average_or_rounded_intermediates():
    rubric = load_rubric()
    criteria = [c for c in rubric.criteria if c.active][:3]
    fractions = [.3333333333, .25, .9]
    review = {'results': {c.id: result(c.id, f) for c, f in zip(criteria, fractions)}}
    q = quality.build_quality(review, rubric)
    assert q['score'] == pytest.approx(sum(c.points * f for c, f in zip(criteria, fractions)) / sum(c.points for c in criteria) * 100)


def test_enrichment_list_and_download_share_projection_without_mutating_evidence(tmp_path):
    from fastapi.testclient import TestClient
    from surveycoach.server import create_app
    with TestClient(create_app(tmp_path / 'synthetic.db'), base_url='http://localhost') as client:
        created = client.post('/api/samples/boxer-briefs', json={}).json()
        detail = client.get(f"/api/surveys/{created['id']}").json()
        expected = quality.build_quality(detail['review'], load_rubric())
        assert detail['methodology']['quality'] == expected and 'quality' not in detail
        assert client.get('/api/surveys').json()['surveys'][0]['methodology']['quality'] == expected
        for suffix in ['/summary', '/summary?download=1']:
            packet = client.get(f"/api/surveys/{created['id']}/versions/1{suffix}").text
            assert 'Survey Quality' in packet and 'Quality methodology' in packet
            assert f"{round(expected['score'])}/100" in packet
            assert 'coverage' in packet
        assert detail['effort_method']['seconds_per_word'] == .3


def test_pick_and_keep_reprojection_never_boosts_quality(tmp_path):
    from fastapi.testclient import TestClient
    from surveycoach.server import create_app
    with TestClient(create_app(tmp_path / 'choices.db'), base_url='http://localhost') as client:
        created = client.post('/api/samples/boxer-briefs', json={}).json()
        path = f"/api/surveys/{created['id']}"
        detail = client.get(path).json()
        before = detail['methodology']['quality']
        f = next(f for f in detail['review']['findings'] if f.get('options') or f.get('suggested_text'))
        picked = f['options'][0]['text'] if f.get('options') else f['suggested_text']
        endpoint = path + f"/versions/1/decisions/{f['fingerprint']}"
        for payload in [dict(action='pick', picked_text=picked), dict(action='keep', reason='Synthetic accepted risk')]:
            assert client.put(endpoint, json=payload).status_code == 200
            assert client.get(path).json()['methodology']['quality'] == before


def test_download_rounding_matches_compact_browser_score_at_half_point():
    from surveycoach.server.report import quality_section
    q = quality.build_quality({}, load_rubric())
    q['score'] = 82.5
    assert '83/100' in quality_section({'methodology': {'quality': q}})
