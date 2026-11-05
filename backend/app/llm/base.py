"""Base Protocol and Data Models for LLM Providers."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


@dataclass
class LLMResult:
    content: str
    parsed: dict[str, Any] | None = None
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    generation_mode: str = "live"


def retry_after_seconds(headers: Mapping[str, str], default: int = 30) -> int:
    """Read Retry-After as seconds or an HTTP date, returning a non-negative delay."""
    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return default
    try:
        return max(0, int(float(value)))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0, int((retry_at - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return default


@runtime_checkable
class LLMProvider(Protocol):
    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
        timeout: float | None = None,
    ) -> LLMResult:
        """Generate structured JSON response adhering to schema."""
        ...
