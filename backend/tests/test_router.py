"""ModelRouter failover + circuit-breaker tests (no DB, no network)."""

import pytest

from greenflow.llm import router as router_mod
from greenflow.llm.provider import LLMResponse
from greenflow.llm.router import ModelRouter


class FakeProvider:
    def __init__(self, name, model="m", fail=False):
        self.name, self.model, self._fail = name, model, fail
        self.calls = 0

    def chat(self, messages, tools=None, **kw):
        self.calls += 1
        if self._fail:
            raise RuntimeError(f"{self.name} boom")
        return LLMResponse(content=f"ok from {self.name}")


@pytest.fixture(autouse=True)
def _clear_breaker():
    router_mod._breaker.clear()
    yield
    router_mod._breaker.clear()


def test_fails_over_to_next_provider():
    r = ModelRouter([FakeProvider("a", fail=True), FakeProvider("b")])
    resp = r.chat([{"role": "user", "content": "hi"}])
    assert resp.content == "ok from b"
    assert resp.raw["_router"]["provider"] == "b"  # audit: who answered


def test_all_providers_fail_raises():
    r = ModelRouter([FakeProvider("a", fail=True), FakeProvider("b", fail=True)])
    with pytest.raises(Exception):
        r.chat([{"role": "user", "content": "hi"}])


def test_no_providers_raises():
    with pytest.raises(RuntimeError):
        ModelRouter([]).chat([{"role": "user", "content": "hi"}])


def test_circuit_breaker_skips_recently_failed_provider():
    a = FakeProvider("a", fail=True)
    b = FakeProvider("b")
    r = ModelRouter([a, b])
    r.chat([{"role": "user", "content": "1"}])  # a fails -> tripped, b answers
    a_calls_after_first = a.calls
    r.chat([{"role": "user", "content": "2"}])  # a is cooling -> skipped
    assert a.calls == a_calls_after_first       # a not retried while in cooldown
    assert b.calls == 2


def test_success_clears_breaker():
    a = FakeProvider("a")
    r = ModelRouter([a])
    router_mod._breaker[ModelRouter._key(a)] = router_mod.time.time() + 999
    # all providers cooling -> router tries them anyway; success clears the breaker
    resp = r.chat([{"role": "user", "content": "x"}])
    assert resp.content == "ok from a"
    assert ModelRouter._key(a) not in router_mod._breaker
