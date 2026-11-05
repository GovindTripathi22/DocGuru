"""Retry, circuit-breaker, and overall deadline handling for live model calls."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from math import ceil
from typing import TypeVar

import httpx

from ..errors import LLMRateLimited, LLMTimeout, LLMUnavailable

T = TypeVar("T")
_TRANSIENT_ERRORS = (
    LLMRateLimited,
    LLMUnavailable,
    LLMTimeout,
    httpx.TimeoutException,
    httpx.TransportError,
)


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    opened_until: float | None = None
    half_open_in_flight: bool = False


class LLMCallResilience:
    """Bounds a provider call with retries and a per-provider circuit breaker."""

    def __init__(self) -> None:
        self._circuits: dict[str, _CircuitState] = {}

    def reset(self) -> None:
        """Clear breaker state; intended for tests and controlled operator resets."""
        self._circuits.clear()

    async def call(
        self,
        provider_name: str,
        invoke: Callable[[], Awaitable[T]],
        *,
        max_retries: int,
        deadline_seconds: float,
        breaker_threshold: int,
        breaker_reset_seconds: float,
    ) -> T:
        state = self._circuits.setdefault(provider_name, _CircuitState())
        now = time.monotonic()
        is_probe = False

        if state.opened_until is not None:
            if now < state.opened_until:
                raise self._open_error(state.opened_until - now)
            if state.half_open_in_flight:
                raise self._open_error(breaker_reset_seconds)
            state.half_open_in_flight = True
            is_probe = True

        try:
            async with asyncio.timeout(deadline_seconds):
                for attempt in range(max_retries + 1):
                    try:
                        result = await invoke()
                    except _TRANSIENT_ERRORS as exc:
                        state.consecutive_failures += 1
                        if state.consecutive_failures >= breaker_threshold or is_probe:
                            self._open(state, breaker_reset_seconds)
                            is_probe = False
                        if attempt >= max_retries:
                            raise
                        await asyncio.sleep(self._retry_delay(exc, attempt))
                    else:
                        state.consecutive_failures = 0
                        state.opened_until = None
                        state.half_open_in_flight = False
                        return result
        except TimeoutError as exc:
            state.consecutive_failures += 1
            if state.consecutive_failures >= breaker_threshold or is_probe:
                self._open(state, breaker_reset_seconds)
            raise LLMTimeout("The generation request exceeded its overall deadline.") from exc
        except _TRANSIENT_ERRORS:
            if is_probe:
                self._open(state, breaker_reset_seconds)
            raise
        finally:
            if is_probe:
                state.half_open_in_flight = False

        raise LLMUnavailable("The model provider failed without returning a result.")

    @staticmethod
    def _retry_delay(error: Exception, attempt: int) -> float:
        backoff = min(10.0, 0.5 * (2**attempt)) * random.uniform(0.75, 1.25)  # nosec B311
        if isinstance(error, LLMRateLimited):
            return max(backoff, float(error.details.get("retry_after", 0)))
        return backoff

    @staticmethod
    def _open(state: _CircuitState, reset_seconds: float) -> None:
        state.opened_until = time.monotonic() + reset_seconds
        state.half_open_in_flight = False

    @staticmethod
    def _open_error(retry_after: float) -> LLMUnavailable:
        return LLMUnavailable(
            "The model provider circuit breaker is open; retry after its recovery window.",
            details={"retry_after": max(1, ceil(retry_after))},
        )


llm_resilience = LLMCallResilience()
