"""Per-event-loop LLM call limits shared across concurrent generation jobs."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import Lock
from weakref import WeakKeyDictionary

from ..config import settings

_semaphores: WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[int, asyncio.Semaphore]] = (
    WeakKeyDictionary()
)
_semaphore_lock = Lock()


def _semaphore_for_current_loop() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    limit = settings.LLM_MAX_CONCURRENCY
    with _semaphore_lock:
        configured = _semaphores.get(loop)
        if configured is None or configured[0] != limit:
            semaphore = asyncio.Semaphore(limit)
            _semaphores[loop] = (limit, semaphore)
            return semaphore
        return configured[1]


@asynccontextmanager
async def llm_call_slot() -> AsyncIterator[None]:
    """Acquire one process-wide slot for this event loop's configured limit."""
    async with _semaphore_for_current_loop():
        yield
