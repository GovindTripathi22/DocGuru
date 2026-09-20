import asyncio

import pytest

from backend.app.ai.gemma_client import GemmaClient


@pytest.mark.xfail(strict=True, reason="LLM-01: live mode silently substitutes fabricated offline content")
def test_live_provider_without_credentials_never_returns_demo_content():
    client = GemmaClient()
    client.provider = "google_ai"
    client.api_key = ""

    async def generate():
        return await client.generate_structured_json("Return a document plan", "Quarterly retail sales report")

    with pytest.raises(RuntimeError, match="LLM_NOT_CONFIGURED"):
        asyncio.run(generate())
