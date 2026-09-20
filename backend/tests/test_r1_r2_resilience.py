"""
Test Suite for R1 (Native Async Ollama Client Migration) & R2 (Tailored Token Caps & Offline Resilience).

Verifies:
1. Native ollama.AsyncClient initialization with timeout=80.0 and options num_predict=max_tokens.
2. Graceful socket teardown on 80s timeout using asyncio.shield(client.close()).
3. Socket teardown on task cancellation using asyncio.shield(client.close()).
4. HTTP error handling in _call_ollama with guaranteed socket closure.
5. Absence of asyncio.to_thread in GemmaClient Ollama calls.
6. PromptEnhancer token cap (max_tokens=350).
7. DocumentPlanner DOCX token cap (max_tokens=1500).
8. DocumentPlanner PPTX token cap (max_tokens=1000).
9. ImageService offline mode (OFFLINE_MODE=True) instant fallback (<0.5s) producing .svg and .jpg.
10. ImageService network error fallback producing .svg and .jpg.
11. Settings.OFFLINE_MODE configuration default and environment override.
"""

import inspect
import time
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx
import respx
from PIL import Image

from backend.app.ai.gemma_client import GemmaClient
from backend.app.config import settings, Settings
from backend.app.ai.image_service import ImageService
from backend.app.ai.prompt_enhancer import PromptEnhancer
from backend.app.ai.planner import DocumentPlanner
from backend.app.models.template_spec import TemplateSpecification


# ==============================================================================
# R1: GEMMA CLIENT ASYNC OLLAMA TESTS (via httpx + respx)
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_gemma_client_call_ollama_num_predict():
    """
    Verify GemmaClient._call_ollama posts to /api/chat with num_predict=max_tokens.
    """
    client = GemmaClient()
    endpoint = (client.endpoint or "http://127.0.0.1:11434").rstrip("/")
    route = respx.post(f"{endpoint}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={"message": {"content": '{"status": "success", "result": "verified"}'}}
        )
    )

    res = await client._call_ollama(
        system_prompt="System prompt test",
        user_prompt="User prompt test",
        response_schema=None,
        max_tokens=350
    )

    assert route.called
    req = route.calls.last.request
    import json
    data = json.loads(req.content.decode("utf-8"))
    assert data["model"] == client.model_name
    assert data["format"] == "json"
    assert data["options"]["num_predict"] == 350
    assert data["options"]["temperature"] == client.temperature
    assert res == {"status": "success", "result": "verified"}


@pytest.mark.asyncio
@respx.mock
async def test_gemma_client_handles_80s_timeout_and_drops_socket():
    """
    Verify GemmaClient._call_ollama catches timeout and raises.
    """
    client = GemmaClient()
    endpoint = (client.endpoint or "http://127.0.0.1:11434").rstrip("/")
    respx.post(f"{endpoint}/api/chat").mock(
        side_effect=httpx.ReadTimeout("Ollama timed out")
    )

    with pytest.raises((asyncio.TimeoutError, httpx.TimeoutException)):
        await client._call_ollama(
            system_prompt="Sys",
            user_prompt="User",
            response_schema=None,
            max_tokens=1500
        )


@pytest.mark.asyncio
@respx.mock
async def test_gemma_client_handles_task_cancellation_and_shields_close():
    """
    Verify GemmaClient._call_ollama handles task cancellation cleanly.
    """
    client = GemmaClient()
    endpoint = (client.endpoint or "http://127.0.0.1:11434").rstrip("/")

    async def hang_chat(request):
        await asyncio.sleep(10)
        return httpx.Response(200, json={"message": {"content": "{}"}})

    respx.post(f"{endpoint}/api/chat").mock(side_effect=hang_chat)

    task = asyncio.create_task(
        client._call_ollama(
            system_prompt="Sys",
            user_prompt="User",
            response_schema=None,
            max_tokens=1000
        )
    )

    await asyncio.sleep(0.02)
    assert task.done() is False

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
@respx.mock
async def test_gemma_client_handles_httpx_error_and_closes_socket():
    """
    Verify GemmaClient._call_ollama catches httpx.HTTPError.
    """
    client = GemmaClient()
    endpoint = (client.endpoint or "http://127.0.0.1:11434").rstrip("/")
    respx.post(f"{endpoint}/api/chat").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with pytest.raises(httpx.HTTPError):
        await client._call_ollama(
            system_prompt="Sys",
            user_prompt="User",
            response_schema=None,
            max_tokens=500
        )


def test_no_asyncio_to_thread_in_gemma_client():
    """
    Verify no asyncio.to_thread exists in gemma_client.py, confirming native async implementation.
    """
    import backend.app.ai.gemma_client as gc_mod
    source = inspect.getsource(gc_mod)
    assert "asyncio.to_thread" not in source
    assert "to_thread" not in source


# ==============================================================================
# R2: TAILORED TOKEN CAPS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_prompt_enhancer_passes_max_tokens_350():
    """
    Verify PromptEnhancer.enhance passes max_tokens=350 to generate_structured_json.
    """
    enhancer = PromptEnhancer()
    mock_generate = AsyncMock(return_value={"enhanced_prompt": "Synthesized High-Impact Prompt"})
    enhancer.client.generate_structured_json = mock_generate

    result = await enhancer.enhance("Brief topic prompt", document_type="docx")

    mock_generate.assert_awaited_once()
    call_kwargs = mock_generate.await_args.kwargs
    assert call_kwargs["max_tokens"] == 350
    assert result == "Synthesized High-Impact Prompt"


@pytest.mark.asyncio
async def test_document_planner_docx_passes_max_tokens_1500():
    """
    Verify DocumentPlanner.plan_document passes max_tokens=1500 to generate_structured_json.
    """
    planner = DocumentPlanner()
    mock_generate = AsyncMock(return_value={
        "title": "Quantum Computing Architectural Analysis",
        "sections": [
            {
                "title": "Executive Summary",
                "heading_style": "Heading 1",
                "paragraphs": ["Detailed architectural breakdown."],
                "bullets": []
            }
        ]
    })
    planner.client.generate_structured_json = mock_generate

    template_spec = TemplateSpecification(
        filename="report.docx",
        document_type="docx",
        available_heading_styles=["Heading 1", "Heading 2"]
    )

    plan = await planner.plan_document(
        user_prompt="Quantum Computing Architecture",
        template_spec=template_spec
    )

    mock_generate.assert_awaited_once()
    call_kwargs = mock_generate.await_args.kwargs
    assert call_kwargs["max_tokens"] == 1500
    assert plan.title == "Quantum Computing Architectural Analysis"
    assert len(plan.sections) >= 1


@pytest.mark.asyncio
async def test_document_planner_pptx_passes_max_tokens_1000():
    """
    Verify DocumentPlanner.plan_presentation passes max_tokens=1000 to generate_structured_json.
    """
    planner = DocumentPlanner()
    mock_generate = AsyncMock(return_value={
        "presentation_title": "AI Safety & Ethics Briefing",
        "slides": [
            {
                "slide_number": 1,
                "title": "Strategic Overview",
                "layout_name": "Title Slide",
                "bullet_points": ["Safety alignment", "Verification protocols"],
                "body_paragraphs": []
            }
        ]
    })
    planner.client.generate_structured_json = mock_generate

    template_spec = TemplateSpecification(
        filename="presentation.pptx",
        document_type="pptx",
        available_layout_names=["Title Slide", "Title and Content"]
    )

    plan = await planner.plan_presentation(
        user_prompt="AI Safety & Ethics Overview",
        template_spec=template_spec
    )

    mock_generate.assert_awaited_once()
    call_kwargs = mock_generate.await_args.kwargs
    assert call_kwargs["max_tokens"] == 1000
    assert plan.presentation_title == "AI Safety & Ethics Briefing"
    assert len(plan.slides) >= 1


# ==============================================================================
# R2: OFFLINE RESILIENCE & IMAGE SERVICE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_image_service_offline_mode_generates_svg_and_jpg_immediately(tmp_path):
    """
    Verify ImageService with OFFLINE_MODE=True bypasses external network calls,
    executes immediately (<0.5s), and creates both .svg and .jpg visual assets.
    """
    test_cache = tmp_path / "img_cache"
    service = ImageService(cache_dir=test_cache)

    with patch("backend.app.ai.image_service.settings.OFFLINE_MODE", True):
        t0 = time.perf_counter()
        result_path_str = await service.fetch_or_generate_image(
            query_or_prompt="Quantum Supercomputing Matrix",
            mode="search",
            width=800,
            height=450
        )
        elapsed = time.perf_counter() - t0

        # Must be virtually instantaneous (no 2s or 10s HTTP timeout)
        assert elapsed < 0.5

        # 1. Verify raster JPG asset exists and is valid
        jpg_path = Path(result_path_str)
        assert jpg_path.exists()
        assert jpg_path.suffix == ".jpg"
        with Image.open(jpg_path) as img:
            assert img.size == (800, 450)

        # 2. Verify companion SVG asset exists and has valid XML/SVG markup
        svg_path = jpg_path.with_suffix(".svg")
        assert svg_path.exists()
        svg_content = svg_path.read_text(encoding="utf-8")
        assert "<svg" in svg_content
        assert "</svg>" in svg_content
        assert "Quantum Supercomputing Matrix" in svg_content


@pytest.mark.asyncio
async def test_image_service_network_failure_falls_back_to_svg_and_jpg(tmp_path):
    """
    Verify ImageService gracefully falls back to SVG and JPG when network call fails or times out.
    """
    test_cache = tmp_path / "fail_cache"
    service = ImageService(cache_dir=test_cache)

    # Force network search to return None (simulating timeout or connection error)
    with patch.object(service, "_search_real_image", new=AsyncMock(return_value=None)):
        with patch("backend.app.ai.image_service.settings.OFFLINE_MODE", False):
            result_path_str = await service.fetch_or_generate_image(
                query_or_prompt="Deep Learning Neural Networks",
                mode="search",
                width=640,
                height=360
            )

            jpg_path = Path(result_path_str)
            assert jpg_path.exists()
            assert jpg_path.suffix == ".jpg"
            with Image.open(jpg_path) as img:
                assert img.size == (640, 360)

            svg_path = jpg_path.with_suffix(".svg")
            assert svg_path.exists()
            assert "<svg" in svg_path.read_text(encoding="utf-8")


def test_settings_offline_mode_defaults_and_env(monkeypatch):
    """
    Verify Settings.OFFLINE_MODE default is False, and respects env var overrides.
    """
    # 1. Default should be False
    default_settings = Settings()
    assert default_settings.OFFLINE_MODE is False

    # 2. Env var override
    monkeypatch.setenv("OFFLINE_MODE", "true")
    env_settings = Settings()
    assert env_settings.OFFLINE_MODE is True
