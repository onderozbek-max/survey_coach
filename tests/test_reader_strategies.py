"""Constrained planning and local verified-learning contracts."""
import pytest
from pydantic import ValidationError

from surveycoach.reader.strategies import Action, Strategy, RuleStore, signature


def observation(prompt='Question'):
    return {'groups': [{'kind': 'text_short', 'prompt': prompt, 'items': [{'type': 'text', 'maxlength': 5}]}],
            'nav': [{'label': 'Next'}], 'uploads': []}


def test_strategy_rejects_code_and_unbounded_values():
    with pytest.raises(ValidationError):
        Action(op='eval', target=0, value='document.cookie')
    with pytest.raises(ValidationError):
        Action(op='fill', target=0, value='personal content')


def test_structural_signature_ignores_question_wording():
    assert signature(observation('Private wording')) == signature(observation('Other wording'))


def test_rules_are_private_provisional_and_quarantined_on_failure(tmp_path):
    store = RuleStore(tmp_path / 'rules.sqlite3')
    plan = Strategy(actions=[Action(op='fill', target=0, length=5), Action(op='click', target=1)])
    key = signature(observation())
    store.success(key, plan)
    assert store.candidates(key)[0] == plan
    store.failure(key, plan)
    assert store.candidates(key) == []
    assert (tmp_path / 'rules.sqlite3').stat().st_mode & 0o077 == 0
