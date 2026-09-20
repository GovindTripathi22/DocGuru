"""Client for Gemma 4 and compatible LLMs, delegating to backend.app.llm providers."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
import httpx

from ..config import settings
from ..errors import (
    LLMInvalidResponse,
    LLMNotConfigured,
)
from ..llm.factory import get_llm_provider
from ..llm.google_ai import GoogleAIProvider
from ..llm.ollama import OllamaProvider
from ..llm.openai_compat import OpenAICompatProvider

logger = logging.getLogger(__name__)


class GemmaClient:
    """
    Client for Gemma 4 and compatible LLMs.
    Delegates to modular backend.app.llm providers (Google AI, Ollama, OpenAI-compat, Demo).
    Never silently falls back to invented/canned content on live paths.
    """

    def __init__(self, provider: Optional[str] = None):
        self._provider = provider
        self.model_name = settings.MODEL_NAME
        self.api_key = settings.api_key
        self.endpoint = settings.MODEL_ENDPOINT
        self.temperature = settings.TEMPERATURE
        self.max_tokens = settings.MAX_TOKENS

    @property
    def provider(self) -> str:
        return self._provider or settings.MODEL_PROVIDER

    @provider.setter
    def provider(self, val: str) -> None:
        self._provider = val

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Requests structured JSON from the configured provider.
        Raises typed exceptions on failure; never returns silent fake content.
        """
        tokens = max_tokens or self.max_tokens

        if self.provider == "google_ai" and not self.api_key:
            raise LLMNotConfigured("Google AI provider is not configured. GEMINI_API_KEY is missing.")

        provider = get_llm_provider(self.provider)
        try:
            result = await provider.generate_json(
                system=system_prompt,
                user=user_prompt,
                schema=response_schema,
                max_output_tokens=tokens,
            )
            if result.parsed is not None:
                return result.parsed
            return self._extract_json_from_text(result.content)
        except (httpx.TimeoutException, asyncio.TimeoutError) as e:
            raise LLMTimeout("LLM request timed out.") from e
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"LLM service communication error: {e}") from e

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if not text:
            raise LLMInvalidResponse("The model returned an empty response.")

        if "```" in text:
            lines = text.splitlines()
            json_lines = []
            in_fence = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    json_lines.append(line)
            if json_lines:
                text = "\n".join(json_lines).strip()

        try:
            return json.loads(text)
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass

        raise LLMInvalidResponse(f"Could not parse valid JSON from LLM response: {text[:200]}")

    async def _call_google_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Optional[Dict[str, Any]],
        max_tokens: int,
    ) -> Dict[str, Any]:
        provider = GoogleAIProvider(
            api_key=self.api_key,
            model_name=self.model_name,
            temperature=self.temperature,
            timeout_sec=settings.LLM_TIMEOUT_SEC,
        )
        res = await provider.generate_json(
            system=system_prompt,
            user=user_prompt,
            schema=response_schema,
            max_output_tokens=max_tokens,
        )
        return res.parsed if res.parsed is not None else self._extract_json_from_text(res.content)

    async def _call_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Optional[Dict[str, Any]],
        max_tokens: int,
    ) -> Dict[str, Any]:
        import asyncio
        endpoint = (self.endpoint or "http://127.0.0.1:11434").rstrip("/")
        url = f"{endpoint}/api/chat"
        payload = {
            "model": self.model_name,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens,
                "stop": ["<end_of_turn>", "<eos>"],
            },
        }
        timeout = httpx.Timeout(80.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                raw_content = data.get("message", {}).get("content", "{}")
                return self._extract_json_from_text(raw_content)
            except (asyncio.TimeoutError, httpx.TimeoutException) as e:
                logger.warning(f"Ollama async call timed out: {e}")
                raise
            except httpx.HTTPError as e:
                logger.warning(f"Ollama async call failed: {e}")
                raise

    async def _call_openai_compat(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Optional[Dict[str, Any]],
        max_tokens: int,
    ) -> Dict[str, Any]:
        provider = OpenAICompatProvider(
            endpoint=self.endpoint,
            model_name=self.model_name,
            api_key=self.api_key,
            temperature=self.temperature,
            timeout_sec=settings.LLM_TIMEOUT_SEC,
        )
        res = await provider.generate_json(
            system=system_prompt,
            user=user_prompt,
            schema=response_schema,
            max_output_tokens=max_tokens,
        )
        return res.parsed if res.parsed is not None else self._extract_json_from_text(res.content)
