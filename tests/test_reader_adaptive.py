"""Synthetic browser verification of constrained planning and learned replay."""
import json
from test_reader_browser import zoo

from surveycoach.reader import read_survey
from surveycoach.reader.strategies import Action, Strategy


class Planner:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system, data, schema, images=()):
        self.calls += 1
        evidence = json.loads(data)
        assert 'untrusted' in system.lower()
        targets = evidence['controls']
        text = next(i for i, entry in enumerate(targets) if entry.get('type') == 'textarea')
        forward = next(i for i, entry in enumerate(targets) if entry.get('label') == 'Next')
        return Strategy(actions=[Action(op='fill', target=text, length=50), Action(op='click', target=forward)])


def test_ai_repairs_then_verified_strategy_is_reused_without_model(zoo, tmp_path):
    planner = Planner()
    first = read_survey(zoo[0] + '/ai-length-rule', allow_test_local=True, participate=True,
                        planner=planner, rules_path=tmp_path / 'rules.sqlite3')
    assert first.coverage.stop_reason == 'path_end'
    assert planner.calls == 1
    assert first.coverage.ai_strategies == 1
    second = read_survey(zoo[0] + '/ai-length-rule', allow_test_local=True, participate=True,
                         planner=planner, rules_path=tmp_path / 'rules.sqlite3')
    assert second.coverage.stop_reason == 'path_end'
    assert planner.calls == 1
    assert second.coverage.learned_rule_hits == 1


def test_validation_only_change_does_not_teach_a_rule(zoo, tmp_path):
    planner = Planner()
    result = read_survey(zoo[0] + '/validation-only', allow_test_local=True, participate=True,
                         planner=planner, rules_path=tmp_path / 'rules.sqlite3')
    assert result.coverage.stop_reason == 'blocked'
    from surveycoach.reader.strategies import RuleStore
    with RuleStore(tmp_path / 'rules.sqlite3').connection() as db:
        assert db.execute('SELECT COUNT(*) FROM rules WHERE successes>0').fetchone()[0] == 0


def test_failed_learned_rule_is_quarantined_and_model_recovers(zoo, tmp_path):
    from surveycoach.reader.strategies import RuleStore
    planner = Planner()
    path = tmp_path / 'rules.sqlite3'
    read_survey(zoo[0] + '/ai-length-rule', allow_test_local=True, participate=True,
                planner=planner, rules_path=path)
    store = RuleStore(path)
    with store.connection() as db:
        scope = db.execute('SELECT scope FROM rules').fetchone()[0]
        db.execute('DELETE FROM rules')
    bad = Strategy(actions=[Action(op='wait', milliseconds=100)])
    store.success(scope, bad)
    result = read_survey(zoo[0] + '/ai-length-rule', allow_test_local=True, participate=True,
                         planner=planner, rules_path=path)
    assert result.coverage.stop_reason == 'path_end'
    assert bad not in store.candidates(scope)


def test_passive_mode_never_calls_planner(zoo, tmp_path):
    planner = Planner()
    read_survey(zoo[0] + '/validation-only', allow_test_local=True, planner=planner,
                rules_path=tmp_path / 'rules.sqlite3')
    assert planner.calls == 0
