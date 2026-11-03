"""Browser callbacks stay on their event loop; HTTP work may run concurrently."""
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from surveycoach.reader.models import Coverage
from surveycoach.reader.transport import GuardedTransport


def test_async_routes_do_not_serialize_blocking_http_work(monkeypatch):
    guard = GuardedTransport("http://127.0.0.1:9000/test", local=True, approval=False, coverage=Coverage())
    def slow(self, route):
        time.sleep(0.15)
        route.fulfill(status=200, headers={}, body=b"synthetic")
    monkeypatch.setattr(GuardedTransport, "__call__", slow)
    routes = [SimpleNamespace(request=SimpleNamespace(url="http://127.0.0.1:9000/test", method="GET", headers={}),
                              fulfill=AsyncMock(), abort=AsyncMock()) for _ in range(4)]
    async def run():
        await asyncio.gather(*(guard.handle_async(route) for route in routes))
    started = time.monotonic()
    asyncio.run(run())
    assert time.monotonic() - started < 0.5
    for route in routes:
        route.fulfill.assert_awaited_once_with(status=200, headers={}, body=b"synthetic")
