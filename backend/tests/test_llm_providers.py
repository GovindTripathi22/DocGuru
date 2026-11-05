from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
import respx
from google.genai.errors import APIError

from backend.app.config import settings
from backend.app.errors import (
    LLMBlocked,
    LLMInvalidResponse,
    LLMNotConfigured,
    LLMRateLimited,
    LLMTimeout,
    LLMTruncated,
    LLMUnavailable,
)
from backend.app.llm.base import retry_after_seconds
from backend.app.llm.google_ai import GoogleAIProvider
from backend.app.llm.ollama import OllamaProvider
from backend.app.llm.openai_compat import OpenAICompatProvider


class _FakeGoogleModels:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.kwargs = None

    async def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def _google_provider(
    response=None, error: Exception | None = None
) -> tuple[GoogleAIProvider, _FakeGoogleModels]:
    provider = GoogleAIProvider(api_key="test-key", model_name="test-model")
    models = _FakeGoogleModels(response=response, error=error)
    provider._client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return provider, models


def test_retry_after_parses_seconds_dates_and_defaults():
    assert retry_after_seconds({"Retry-After": "2.5"}) == 2
    assert retry_after_seconds({"retry-after": "not a date"}, default=9) == 9
    assert retry_after_seconds({}) == 30


@pytest.mark.asyncio
async def test_google_provider_builds_structured_request_and_parses_usage(monkeypatch):
    response = SimpleNamespace(
        text='{"answer": 42}',
        candidates=[SimpleNamespace(finish_reason="STOP")],
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=8),
        prompt_feedback=None,
    )
    provider, models = _google_provider(response)

    result = await provider.generate_json(
        "system instructions",
        "user request",
        schema={"type": "object"},
        max_output_tokens=777,
        timeout=9,
    )

    assert result.parsed == {"answer": 42}
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8
    assert result.finish_reason == "STOP"
    assert models.kwargs["contents"] == "user request"
    assert models.kwargs["config"].max_output_tokens == 777
    assert models.kwargs["config"].response_schema == {"type": "object"}


@pytest.mark.asyncio
async def test_google_provider_removes_json_fences_and_honors_thinking_setting(monkeypatch):
    monkeypatch.setattr(settings, "LLM_THINKING", "off")
    response = SimpleNamespace(
        text='```json\n{"ok": true}\n```', candidates=[], usage_metadata=None
    )
    provider, models = _google_provider(response)

    result = await provider.generate_json("system", "user")

    assert result.parsed == {"ok": True}
    assert models.kwargs["config"].thinking_config.thinking_budget == 0


@pytest.mark.asyncio
async def test_google_provider_maps_blocked_truncated_empty_and_invalid_responses():
    provider, _ = _google_provider(
        SimpleNamespace(
            text="{}",
            candidates=[],
            prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
            usage_metadata=None,
        )
    )
    with pytest.raises(LLMBlocked):
        await provider.generate_json("system", "user")

    for reason, error_type in (("MAX_TOKENS", LLMTruncated), ("SAFETY", LLMBlocked)):
        provider, _ = _google_provider(
            SimpleNamespace(
                text='{"ok":true}',
                candidates=[SimpleNamespace(finish_reason=reason)],
                prompt_feedback=None,
                usage_metadata=None,
            )
        )
        with pytest.raises(error_type):
            await provider.generate_json("system", "user")

    provider, _ = _google_provider(SimpleNamespace(text="  ", candidates=[], prompt_feedback=None))
    with pytest.raises(LLMInvalidResponse):
        await provider.generate_json("system", "user")
    provider, _ = _google_provider(
        SimpleNamespace(text="no json", candidates=[], prompt_feedback=None)
    )
    with pytest.raises(LLMInvalidResponse):
        await provider.generate_json("system", "user")


@pytest.mark.asyncio
async def test_google_provider_maps_sdk_errors_and_requires_credentials():
    with pytest.raises(LLMNotConfigured):
        await GoogleAIProvider(api_key="").generate_json("system", "user")

    rate_limit_error = APIError(
        429,
        {"message": "quota exceeded"},
        response=httpx.Response(429, headers={"Retry-After": "3"}),
    )
    cases = [
        (rate_limit_error, LLMRateLimited),
        (APIError(503, {"message": "maintenance"}), LLMUnavailable),
        (APIError(400, {"message": "API_KEY invalid"}), LLMNotConfigured),
        (APIError(401, {"message": "request rejected"}), LLMUnavailable),
        (RuntimeError("RESOURCE_EXHAUSTED"), LLMRateLimited),
        (RuntimeError("socket timeout"), LLMTimeout),
        (RuntimeError("connection reset"), LLMUnavailable),
        (asyncio.TimeoutError(), LLMTimeout),
    ]
    for error, expected in cases:
        provider, _ = _google_provider(error=error)
        with pytest.raises(expected) as mapped:
            await provider.generate_json("system", "user")
        if isinstance(error, APIError) and error.code == 429:
            assert mapped.value.details["retry_after"] == 3


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("provider_name", ["ollama", "openai"])
async def test_http_llm_providers_send_json_and_return_usage(provider_name):
    if provider_name == "ollama":
        provider = OllamaProvider(endpoint="http://llm.test", model_name="qwen", timeout_sec=10)
        route = respx.post("http://llm.test/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {"content": '```json\n{"ok":true}\n```'},
                    "prompt_eval_count": 7,
                    "eval_count": 3,
                },
            )
        )
    else:
        provider = OpenAICompatProvider(
            endpoint="http://llm.test", model_name="qwen", api_key="k", timeout_sec=10
        )
        route = respx.post("http://llm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 3},
                },
            )
        )

    result = await provider.generate_json("system", "user", max_output_tokens=400)

    assert route.called
    assert result.parsed == {"ok": True}
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 3
    payload = route.calls.last.request.content.decode()
    assert '"user"' in payload
    if provider_name == "ollama":
        assert '"num_predict":400' in payload
    else:
        assert route.calls.last.request.headers["Authorization"] == "Bearer k"
        assert '"max_tokens":400' in payload


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("provider_name", ["ollama", "openai"])
async def test_http_llm_providers_report_http_timeout_and_invalid_json(provider_name):
    if provider_name == "ollama":
        provider = OllamaProvider(endpoint="http://llm.test")
        endpoint = "http://llm.test/api/chat"
    else:
        provider = OpenAICompatProvider(endpoint="http://llm.test")
        endpoint = "http://llm.test/v1/chat/completions"

    route = respx.post(endpoint).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "2"})
    )
    with pytest.raises(LLMRateLimited) as rate_limit:
        await provider.generate_json("system", "user")
    assert rate_limit.value.details["retry_after"] == 2
    route.mock(return_value=httpx.Response(503))
    with pytest.raises(LLMUnavailable):
        await provider.generate_json("system", "user")
    route.mock(side_effect=httpx.ReadTimeout("timeout"))
    with pytest.raises(LLMTimeout):
        await provider.generate_json("system", "user")

    route.mock(
        return_value=httpx.Response(
            200,
            json={"message": {"content": "not json"}}
            if provider_name == "ollama"
            else {"choices": [{"message": {"content": "not json"}}]},
        )
    )
    with pytest.raises(LLMInvalidResponse):
        await provider.generate_json("system", "user")

    route.mock(
        return_value=httpx.Response(200, json={} if provider_name == "ollama" else {"choices": []})
    )
    with pytest.raises(LLMInvalidResponse):
        await provider.generate_json("system", "user")
