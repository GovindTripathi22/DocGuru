"""Async Google AI (Gemini / Gemma) provider using google-genai SDK."""

import asyncio
import json
import logging
from typing import Any, Optional
from pydantic import BaseModel

from google import genai
from google.genai import types
from google.genai.errors import APIError

from .base import LLMResult
from ..config import settings
from ..errors import (
    LLMBlocked,
    LLMInvalidResponse,
    LLMNotConfigured,
    LLMRateLimited,
    LLMTimeout,
    LLMTruncated,
    LLMUnavailable,
)

logger = logging.getLogger(__name__)


class GoogleAIProvider:
    """Async Google AI provider using the official google-genai SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_sec: Optional[int] = None,
    ):
        self.api_key = api_key or settings.api_key
        self.model_name = model_name or settings.MODEL_NAME
        self.temperature = temperature if temperature is not None else settings.TEMPERATURE
        self.timeout_sec = timeout_sec or settings.LLM_TIMEOUT_SEC
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise LLMNotConfigured("Google AI provider requires GEMINI_API_KEY to be set.")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        schema: Optional[dict[str, Any] | type[BaseModel]] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResult:
        if not self.api_key:
            raise LLMNotConfigured("Google AI provider requires GEMINI_API_KEY to be set.")

        effective_timeout = timeout or float(self.timeout_sec)
        tokens = max_output_tokens or settings.OUTLINE_MAX_TOKENS

        client = self._get_client()

        # Build GenerateContentConfig
        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": tokens,
            "response_mime_type": "application/json",
            "system_instruction": system,
            "http_options": types.HttpOptions(timeout=int(effective_timeout * 1000)),
        }

        if schema is not None:
            config_kwargs["response_schema"] = schema

        if settings.LLM_THINKING == "off":
            try:
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            async with asyncio.timeout(effective_timeout + 5.0):
                response = await client.aio.models.generate_content(
                    model=self.model_name,
                    contents=user,
                    config=config,
                )
        except asyncio.TimeoutError as e:
            raise LLMTimeout("Google AI model call timed out.") from e
        except APIError as e:
            status_code = getattr(e, "code", 500)
            if status_code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                raise LLMRateLimited("Google AI rate limit exceeded.") from e
            elif status_code in (500, 502, 503, 504):
                raise LLMUnavailable(f"Google AI service unavailable: {e.message or e}") from e
            elif status_code == 400 and "API_KEY" in str(e).upper():
                raise LLMNotConfigured(f"Invalid Google AI credentials: {e.message or e}") from e
            raise LLMUnavailable(f"Google AI API error: {e.message or e}") from e
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                raise LLMRateLimited("Google AI rate limit exceeded.") from e
            if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                raise LLMTimeout("Google AI request timed out.") from e
            raise LLMUnavailable(f"Google AI connection error: {err_msg}") from e

        # Check prompt feedback
        if hasattr(response, "prompt_feedback") and response.prompt_feedback:
            block_reason = getattr(response.prompt_feedback, "block_reason", None)
            if block_reason:
                raise LLMBlocked(f"Google AI blocked request: {block_reason}")

        # Check candidate response
        finish_reason = "stop"
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            cand_finish = getattr(candidate, "finish_reason", None)
            if cand_finish:
                cand_str = str(cand_finish).upper()
                if "MAX_TOKENS" in cand_str:
                    raise LLMTruncated("Google AI response was truncated due to max output tokens.")
                if "SAFETY" in cand_str or "BLOCKED" in cand_str:
                    raise LLMBlocked(f"Google AI candidate blocked by safety filter: {cand_str}")
                finish_reason = cand_str

        raw_text = response.text or ""
        raw_text = raw_text.strip()
        if not raw_text or raw_text == "{}":
            raise LLMInvalidResponse("Google AI returned an empty response.")

        # Clean markdown fences if any
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise LLMInvalidResponse(f"Google AI returned non-JSON response: {raw_text[:200]}") from e

        prompt_tokens = 0
        completion_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return LLMResult(
            content=raw_text,
            parsed=parsed,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model_name,
            generation_mode="live",
        )
