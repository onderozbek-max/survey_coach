"""Completion is not correction; read projections never rewrite captured evidence."""
from copy import deepcopy
import pytest
from surveycoach.demo_export import build_demo_data
from surveycoach.server.present import enrich
from surveycoach.rubric import load_rubric
from surveycoach.server.report import summary_packet
from scripts import capture_screens as capture


@pytest.mark.parametrize('mode', ['pick', 'keep', 'mixed', 'carried', 'stale', 'reopened'])
def test_handled_headline_preserves_assessment_and_download(mode):
    detail = build_demo_data()['surveys'][0]
    detail['decisions'] = {}
    must = [f for f in detail['review']['findings'] if f['severity'] == 'must_fix' and not f.get('absorbed_by')]
    for i, f in enumerate(must):
        choices = f.get('options') or []
        text = f.get('suggested_text') or (choices[0]['text'] if choices else None)
        action = 'keep' if mode in ['keep', 'carried'] or not text or mode == 'mixed' and i % 2 else 'pick'
        detail['decisions'][f['fingerprint']] = {'action':action, 'reason':'Tracker', 'picked_text':text if action == 'pick' else None}
    if mode == 'carried':
        for d in detail['decisions'].values():
            d['carried_from_round'] = 1
    if mode in ['stale', 'reopened']:
        detail['decisions'][must[0]['fingerprint']] = {'action':'open'} if mode == 'reopened' else {'action':'open','stale_pick':True, 'prior_picked_text':'obsolete suggestion'}
    before = deepcopy(detail)
    result = enrich(detail, load_rubric())
    headline = result['overview']['headline']
    if mode in ['stale', 'reopened']:
        assert result['plan']['counts']['open_must_fix'] > 0
        assert 'must-fix' in headline
    else:
        assert 'decisions handled' in headline
        assert 'not verified fixes' in headline
    assert 'No must-fixes found' not in headline
    result.setdefault('version', 1)
    packet = summary_packet(result, download=True)
    assert headline in packet
    assert result['review']['scorecard']['open_blockers'] == before['review']['scorecard']['open_blockers']
    assert detail == before


@pytest.mark.parametrize('value', ['nan','inf','-inf','0','-1'])
def test_capture_rejects_nonfinite_or_nonpositive_timeout_before_output(monkeypatch, value):
    entered = []
    monkeypatch.setattr(capture.Path, 'mkdir', lambda *a, **k: entered.append('mkdir'))
    monkeypatch.setattr(capture, 'server', lambda *a: entered.append('server'))
    with pytest.raises(SystemExit) as error:
        capture.main(['--timeout=' + value])
    assert error.value.code == 2
    assert entered == []
