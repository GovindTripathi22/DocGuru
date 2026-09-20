"""Async Ollama Provider via HTTP API (Decision D3)."""

import asyncio
import json
import logging
from typing import Any, Optional
import httpx
from pydantic import BaseModel

from .base import LLMResult
from ..config import settings
from ..errors import (
    LLMInvalidResponse,
    LLMNotConfigured,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Async Ollama provider using native HTTP calls without ollama SDK."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_sec: Optional[int] = None,
    ):
        self.endpoint = (endpoint or settings.MODEL_ENDPOINT or "http://127.0.0.1:11434").rstrip("/")
        self.model_name = model_name or settings.MODEL_NAME
        self.temperature = temperature if temperature is not None else settings.TEMPERATURE
        self.timeout_sec = timeout_sec or settings.LLM_TIMEOUT_SEC

    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        schema: Optional[dict[str, Any] | type[BaseModel]] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
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
                "stop": ["<end_of_turn>", "<eos>"],
            },
        }

        http_timeout = httpx.Timeout(effective_timeout, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 429:
                    raise LLMRateLimited("Ollama rate limit exceeded.")
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
        except Exception as e:
            raise LLMUnavailable(f"Ollama communication error: {e}") from e

        raw_content = data.get("message", {}).get("content", "").strip()
        if not raw_content or raw_content == "{}":
            raise LLMInvalidResponse("Ollama returned an empty response.")

        # Clean markdown fences if any
        if raw_content.startswith("```"):
            lines = raw_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw_content = "\n".join(lines).strip()

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as e:
            raise LLMInvalidResponse(f"Ollama returned non-JSON response: {raw_content[:200]}") from e

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
