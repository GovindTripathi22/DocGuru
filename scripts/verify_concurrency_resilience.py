"""Behavioral verification for the process-wide async LLM concurrency limit."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.app.ai.gemma_client as gemma_module
from backend.app.ai.gemma_client import GemmaClient
from backend.app.config import settings
from backend.app.llm.base import LLMResult


class ScriptedProvider:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def generate_json(self, **_kwargs) -> LLMResult:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.03)
            return LLMResult(content='{"ok": true}', parsed={"ok": True}, model="scripted")
        finally:
            self.active -= 1


async def verify_global_concurrency_limit() -> tuple[float, float, int]:
    provider = ScriptedProvider()
    previous_limit = settings.LLM_MAX_CONCURRENCY
    previous_factory = gemma_module.get_llm_provider
    settings.LLM_MAX_CONCURRENCY = 3
    gemma_module.get_llm_provider = lambda _name: provider
    try:
        client = GemmaClient(provider="demo")
        heartbeat_gaps: list[float] = []
        finished = asyncio.Event()
        loop = asyncio.get_running_loop()

        async def heartbeat() -> None:
            previous = loop.time()
            while not finished.is_set():
                await asyncio.sleep(0.01)
                current = loop.time()
                heartbeat_gaps.append(current - previous)
                previous = current

        pulse = asyncio.create_task(heartbeat())
        started = time.perf_counter()
        results = await asyncio.gather(
            *[client.generate_structured_json("system", f"request {index}") for index in range(20)]
        )
        elapsed = time.perf_counter() - started
        finished.set()
        await pulse

        assert len(results) == 20
        assert all(result == {"ok": True} for result in results)
        assert provider.max_active == 3, (
            f"Expected at most 3 active calls; observed {provider.max_active}."
        )
        assert elapsed < 4.0, f"20 async calls took too long: {elapsed:.3f}s."
        max_gap = max(heartbeat_gaps, default=0.0)
        assert max_gap <= 0.2, f"Event loop heartbeat gap exceeded 200 ms: {max_gap:.3f}s."
        return elapsed, max_gap, provider.max_active
    finally:
        settings.LLM_MAX_CONCURRENCY = previous_limit
        gemma_module.get_llm_provider = previous_factory


async def main() -> None:
    elapsed, max_gap, max_active = await verify_global_concurrency_limit()
    print(
        "PASS: 20 scripted provider calls completed in "
        f"{elapsed:.3f}s; max active={max_active}; event-loop gap={max_gap:.3f}s."
    )


if __name__ == "__main__":
    asyncio.run(main())
