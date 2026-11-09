"""Async Ollama Provider via HTTP API (Decision D3)."""

import asyncio
import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from ..config import settings
from ..errors import (
    AppError,
    LLMInvalidResponse,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)
from .base import LLMResult, retry_after_seconds
from .json_repair import repair_and_parse_json

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Async Ollama provider using native HTTP calls without ollama SDK."""

    def __init__(
        self,
        endpoint: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        timeout_sec: int | None = None,
    ):
        self.endpoint = (endpoint or settings.MODEL_ENDPOINT or "http://127.0.0.1:11434").rstrip(
            "/"
        )
        self.model_name = model_name or settings.MODEL_NAME
        self.temperature = temperature if temperature is not None else settings.TEMPERATURE
        self.timeout_sec = timeout_sec or settings.LLM_TIMEOUT_SEC

    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
        timeout: float | None = None,
    ) -> LLMResult:
        effective_timeout = timeout or float(self.timeout_sec)
        tokens = max_output_tokens or settings.OUTLINE_MAX_TOKENS
        url = f"{self.endpoint}/api/chat"

        payload = {
            "model": self.model_name,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": self.temperature,
                "num_predict": tokens,
                "num_ctx": 8192,
                "stop": ["<end_of_turn>", "<eos>"],
            },
        }

        http_timeout = httpx.Timeout(effective_timeout, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 429:
                    raise LLMRateLimited(
                        "Ollama rate limit exceeded.",
                        retry_after=retry_after_seconds(response.headers),
                    )
                if response.status_code in (500, 502, 503, 504):
                    raise LLMUnavailable(f"Ollama server returned HTTP {response.status_code}.")
                response.raise_for_status()
                data = response.json()
        except (asyncio.TimeoutError, httpx.TimeoutException) as e:
            raise LLMTimeout("Ollama request timed out.") from e
        except httpx.ConnectError as e:
            raise LLMUnavailable(f"Could not connect to Ollama at {self.endpoint}: {e}") from e
        except httpx.HTTPStatusError as e:
            raise LLMUnavailable(f"Ollama HTTP error {e.response.status_code}: {e}") from e
        except AppError:
            raise
        except Exception as e:  # noqa: BLE001 - normalize client failures to a typed provider error
            raise LLMUnavailable(f"Ollama communication error: {e}") from e

        raw_content = data.get("message", {}).get("content", "").strip()
        parsed = repair_and_parse_json(raw_content, source_name="Ollama")

        prompt_tokens = data.get("prompt_eval_count", 0) or 0
        completion_tokens = data.get("eval_count", 0) or 0

        return LLMResult(
            content=raw_content,
            parsed=parsed,
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model_name,
            generation_mode="live",
        )
