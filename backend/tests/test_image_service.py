from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image

from backend.app.config import settings
from backend.app.images.models import ImageCandidate
from backend.app.images.provider import PexelsProvider, UnsplashProvider, WikimediaProvider
from backend.app.images.service import ImageService


def _jpeg(width: int = 240, height: int = 160) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(20, 120, 180)).save(buffer, format="JPEG")
    return buffer.getvalue()


class _StubProvider:
    def __init__(self, candidate: ImageCandidate):
        self.candidate = candidate
        self.calls = 0

    async def search(self, *_args, **_kwargs):
        self.calls += 1
        return [self.candidate]


def _service(tmp_path: Path, monkeypatch) -> ImageService:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(settings, "IMAGE_CACHE_MAX_MB", 1)
    monkeypatch.setattr(settings, "IMAGE_TIMEOUT_SEC", 2)
    return ImageService(cache_dir=tmp_path / "cache")


@pytest.mark.asyncio
@respx.mock
async def test_image_service_downloads_sanitizes_caches_and_reuses_image(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    provider = _StubProvider(
        ImageCandidate(
            url="https://images.unsplash.com/grid.jpg",
            width=240,
            height=160,
            license="Test license",
            author="A. Author",
            source_url="https://unsplash.com/grid",
        )
    )
    service._provider = provider
    download = respx.get("https://images.unsplash.com/grid.jpg").mock(
        return_value=httpx.Response(200, content=_jpeg(), headers={"content-type": "image/jpeg"})
    )

    path = await service.fetch_or_generate_image("Grid reliability", caption="Grid report")
    cached_path = await service.fetch_or_generate_image("Grid reliability", caption="Grid report")

    assert path == cached_path
    assert Path(path).exists()
    assert download.call_count == 1
    assert provider.calls == 1
    with Image.open(path) as result:
        assert result.format == "JPEG"
        assert result.size == (240, 160)
    metadata = json.loads(Path(path).with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["author"] == "A. Author"
    assert metadata["license"] == "Test license"


@pytest.mark.asyncio
async def test_image_service_skips_off_and_uses_neutral_placeholder_for_untrusted_host(
    tmp_path, monkeypatch
):
    service = _service(tmp_path, monkeypatch)
    provider = _StubProvider(
        ImageCandidate(url="http://127.0.0.1/private.png", width=100, height=100)
    )
    service._provider = provider
    monkeypatch.setattr(settings, "IMAGE_PLACEHOLDERS", False)
    warnings: list[str] = []

    assert await service.fetch_or_generate_image("Sensitive query", mode="off") is None
    image_path = await service.fetch_or_generate_image(
        "Neutral placeholder", mode="search", width=320, height=180, warnings=warnings
    )

    assert image_path is None
    assert warnings == ["images_skipped_no_provider:Neutral placeholder"]
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_offline_search_never_calls_provider_when_placeholders_are_disabled(
    tmp_path, monkeypatch
):
    from unittest.mock import AsyncMock

    service = _service(tmp_path, monkeypatch)
    search = AsyncMock(return_value=None)
    service._search_real_image = search
    monkeypatch.setattr(settings, "OFFLINE_MODE", True)
    monkeypatch.setattr(settings, "IMAGE_PLACEHOLDERS", False)
    warnings: list[str] = []

    result = await service.fetch_or_generate_image("Offline image", warnings=warnings)

    assert result is None
    assert search.await_count == 0
    assert warnings == ["images_skipped_offline_placeholders_disabled"]


@pytest.mark.asyncio
async def test_image_service_explicit_placeholder_and_provider_selection(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "IMAGE_PLACEHOLDERS", True)
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "unsplash-key")
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "pexels-key")
    assert isinstance(service.provider, UnsplashProvider)
    assert service.has_configured_provider is True

    service._provider = None
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "")
    assert isinstance(service.provider, PexelsProvider)
    service._provider = None
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "")
    assert isinstance(service.provider, WikimediaProvider)
    assert service.has_configured_provider is False

    image_path = await service.fetch_or_generate_image(
        "Manual placeholder", mode="placeholder", width=200, height=120
    )
    with Image.open(image_path) as image:
        assert image.size == (200, 120)


@pytest.mark.asyncio
@respx.mock
async def test_image_download_rejects_redirect_to_untrusted_host(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service._provider = _StubProvider(
        ImageCandidate(
            url="https://images.unsplash.com/redirect.jpg",
            width=640,
            height=360,
        )
    )
    redirect = respx.get("https://images.unsplash.com/redirect.jpg").mock(
        return_value=httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/internal"},
        )
    )
    internal = respx.get("http://127.0.0.1/internal").mock(return_value=httpx.Response(200))

    result = await service.fetch_or_generate_image(
        "Internal host redirect", mode="search", warnings=[]
    )

    assert result is None
    assert redirect.call_count == 1
    assert internal.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_image_download_rejects_declared_oversize_before_reading(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service._provider = _StubProvider(
        ImageCandidate(
            url="https://images.unsplash.com/oversized.jpg",
            width=640,
            height=360,
        )
    )
    download = respx.get("https://images.unsplash.com/oversized.jpg").mock(
        return_value=httpx.Response(
            200,
            content=b"image header only",
            headers={"content-type": "image/jpeg", "content-length": str(16 * 1024 * 1024)},
        )
    )

    result = await service.fetch_or_generate_image("Oversized image", mode="search", warnings=[])

    assert result is None
    assert download.call_count == 1


def test_image_service_rejects_invalid_tiny_and_corrupt_images(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    assert service._process_image(b"not an image", 200, 100) is None
    assert service._process_image(_jpeg(80, 90), 200, 100) is None


def test_image_service_downscales_oversized_images(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    resized = service._process_image(_jpeg(2100, 100), 800, 450)
    assert resized is not None
    with Image.open(io.BytesIO(resized)) as image:
        assert image.size == (2000, 95)
