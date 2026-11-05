"""Participant traversal has a finite budget beyond passive startup assets."""
from unittest.mock import Mock

import pytest

from surveycoach.reader.models import Coverage
from surveycoach.reader.transport import GuardedTransport


@pytest.mark.parametrize('participate,limit', [(False, 150), (True, 500)])
def test_request_budget_remains_bounded_by_mode(monkeypatch, participate, limit):
    monkeypatch.setenv('SURVEYCOACH_CORPORATE_PROXY','http://proxy-intlho.wal-mart.com:8080')
    guard=GuardedTransport('https://app.redjade.net/surveys/example/test/', local=False,
                           approval=True, coverage=Coverage(), participate=participate)
    exchange=Mock(return_value=(200, [], b'ok'))
    monkeypatch.setattr(guard,'_exchange',exchange)
    route=Mock()
    route.request.url=guard.start_url
    route.request.method='GET'
    route.request.headers={}
    guard.requests=limit-1
    guard(route)
    route.fulfill.assert_called_once()
    guard(route)
    route.abort.assert_called_once()
    assert exchange.call_count==1
