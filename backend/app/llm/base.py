"""Base Protocol and Data Models for LLM Providers."""

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable
from pydantic import BaseModel


@dataclass
class LLMResult:
    content: str
    parsed: Optional[dict[str, Any]] = None
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    generation_mode: str = "live"


@runtime_checkable
class LLMProvider(Protocol):
    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        schema: Optional[dict[str, Any] | type[BaseModel]] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResult:
        """Generate structured JSON response adhering to schema."""
        ...
