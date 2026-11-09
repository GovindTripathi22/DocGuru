"""Async OpenAI-compatible Provider (vLLM, LiteRT-LM, etc.)."""

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


class OpenAICompatProvider:
    """Async provider for OpenAI-compatible inference servers."""

    def __init__(
        self,
        endpoint: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        timeout_sec: int | None = None,
    ):
        self.endpoint = (endpoint or settings.MODEL_ENDPOINT or "http://127.0.0.1:8001").rstrip("/")
        self.model_name = model_name or settings.MODEL_NAME
        self.api_key = api_key or settings.api_key
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
        url = f"{self.endpoint}/v1/chat/completions"

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
            "max_tokens": tokens,
        }

        http_timeout = httpx.Timeout(effective_timeout, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 429:
                    raise LLMRateLimited(
                        "OpenAI-compatible endpoint rate limit exceeded.",
                        retry_after=retry_after_seconds(response.headers),
                    )
                if response.status_code in (500, 502, 503, 504):
                    raise LLMUnavailable(
                        f"OpenAI-compatible server returned HTTP {response.status_code}."
                    )
                response.raise_for_status()
                data = response.json()
        except (asyncio.TimeoutError, httpx.TimeoutException) as e:
            raise LLMTimeout("OpenAI-compatible request timed out.") from e
        except httpx.ConnectError as e:
            raise LLMUnavailable(f"Could not connect to server at {self.endpoint}: {e}") from e
        except httpx.HTTPStatusError as e:
            raise LLMUnavailable(f"Server HTTP error {e.response.status_code}: {e}") from e
        except AppError:
            raise
        except Exception as e:  # noqa: BLE001 - normalize client failures to a typed provider error
            raise LLMUnavailable(f"Server communication error: {e}") from e

        choices = data.get("choices", [])
        if not choices:
            raise LLMInvalidResponse("Server returned no choices in response.")

        raw_content = choices[0].get("message", {}).get("content", "").strip()
        parsed = repair_and_parse_json(raw_content, source_name="Server")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        finish_reason = choices[0].get("finish_reason", "stop")

        return LLMResult(
            content=raw_content,
            parsed=parsed,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model_name,
            generation_mode="live",
        )
