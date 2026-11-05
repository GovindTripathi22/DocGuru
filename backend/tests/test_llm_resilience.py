from __future__ import annotations

import asyncio

import pytest

from backend.app.errors import LLMRateLimited, LLMTimeout, LLMUnavailable
from backend.app.llm.resilience import LLMCallResilience


@pytest.mark.asyncio
async def test_rate_limit_retries_respect_retry_after(monkeypatch):
    resilience = LLMCallResilience()
    calls = 0
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def invoke() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LLMRateLimited(retry_after=4)
        return "ready"

    monkeypatch.setattr("backend.app.llm.resilience.asyncio.sleep", sleep)
    monkeypatch.setattr("backend.app.llm.resilience.random.uniform", lambda _low, _high: 1.0)
    result = await resilience.call(
        "test-provider",
        invoke,
        max_retries=2,
        deadline_seconds=10,
        breaker_threshold=5,
        breaker_reset_seconds=30,
    )

    assert result == "ready"
    assert calls == 2
    assert delays == [4]


@pytest.mark.asyncio
async def test_transient_failure_uses_exponential_backoff_then_succeeds(monkeypatch):
    resilience = LLMCallResilience()
    calls = 0
    delays: list[float] = []

    async def invoke() -> int:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise LLMUnavailable("temporary outage")
        return 9

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("backend.app.llm.resilience.asyncio.sleep", sleep)
    monkeypatch.setattr("backend.app.llm.resilience.random.uniform", lambda _low, _high: 1.0)

    result = await resilience.call(
        "test-provider",
        invoke,
        max_retries=2,
        deadline_seconds=10,
        breaker_threshold=5,
        breaker_reset_seconds=30,
    )

    assert result == 9
    assert calls == 3
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_circuit_breaker_opens_then_allows_one_half_open_probe(monkeypatch):
    resilience = LLMCallResilience()
    clock = [100.0]
    monkeypatch.setattr("backend.app.llm.resilience.time.monotonic", lambda: clock[0])
    should_fail = True
    calls = 0

    async def invoke() -> str:
        nonlocal calls
        calls += 1
        if should_fail:
            raise LLMUnavailable("provider is down")
        return "recovered"

    with pytest.raises(LLMUnavailable, match="provider is down"):
        await resilience.call(
            "test-provider",
            invoke,
            max_retries=0,
            deadline_seconds=5,
            breaker_threshold=1,
            breaker_reset_seconds=30,
        )

    clock[0] = 101.0
    with pytest.raises(LLMUnavailable, match="circuit breaker is open") as open_error:
        await resilience.call(
            "test-provider",
            invoke,
            max_retries=0,
            deadline_seconds=5,
            breaker_threshold=1,
            breaker_reset_seconds=30,
        )
    assert open_error.value.details["retry_after"] == 29
    assert calls == 1

    clock[0] = 131.0
    should_fail = False
    assert (
        await resilience.call(
            "test-provider",
            invoke,
            max_retries=0,
            deadline_seconds=5,
            breaker_threshold=1,
            breaker_reset_seconds=30,
        )
        == "recovered"
    )
    assert calls == 2


@pytest.mark.asyncio
async def test_overall_deadline_maps_to_typed_llm_timeout():
    resilience = LLMCallResilience()

    async def hang() -> str:
        await asyncio.sleep(1)
        return "late"

    with pytest.raises(LLMTimeout, match="overall deadline"):
        await resilience.call(
            "test-provider",
            hang,
            max_retries=0,
            deadline_seconds=0.01,
            breaker_threshold=5,
            breaker_reset_seconds=30,
        )
