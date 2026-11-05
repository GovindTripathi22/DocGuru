from __future__ import annotations

import httpx
import pytest
import respx

from backend.app.images.provider import PexelsProvider, UnsplashProvider, WikimediaProvider


@pytest.mark.asyncio
@respx.mock
async def test_wikimedia_provider_filters_non_images_and_maps_metadata():
    route = respx.get(WikimediaProvider.API_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "1": {
                            "imageinfo": [
                                {
                                    "mime": "image/jpeg",
                                    "thumburl": "https://upload.wikimedia.org/thumb.jpg",
                                    "thumbwidth": 640,
                                    "thumbheight": 360,
                                    "extmetadata": {
                                        "Artist": {"value": "Ada Author"},
                                        "LicenseShortName": {"value": "CC BY-SA"},
                                    },
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Grid.jpg",
                                }
                            ]
                        },
                        "2": {
                            "imageinfo": [
                                {"mime": "application/pdf", "url": "https://example.test/file.pdf"}
                            ]
                        },
                        "3": {"imageinfo": [{"mime": "image/png"}]},
                        "4": {"imageinfo": []},
                    }
                }
            },
        )
    )

    candidates = await WikimediaProvider().search("  grid resilience  ")

    assert route.called
    assert route.calls.last.request.headers["User-Agent"].startswith("DocGuru-")
    assert len(candidates) == 1
    assert candidates[0].width == 640
    assert candidates[0].height == 360
    assert candidates[0].author == "Ada Author"
    assert candidates[0].license == "CC BY-SA"
    assert candidates[0].source_url.endswith("File:Grid.jpg")


@pytest.mark.asyncio
@respx.mock
async def test_wikimedia_provider_handles_empty_error_and_unexpected_payloads():
    route = respx.get(WikimediaProvider.API_URL).mock(return_value=httpx.Response(503))
    provider = WikimediaProvider()

    assert await provider.search("   ") == []
    assert route.call_count == 0
    assert await provider.search("outage") == []

    route.mock(return_value=httpx.Response(200, json={"query": {"pages": None}}))
    assert await provider.search("malformed") == []


@pytest.mark.asyncio
@respx.mock
async def test_unsplash_provider_requires_key_and_returns_attributed_candidates():
    route = respx.get(UnsplashProvider.API_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "urls": {"regular": "https://images.unsplash.com/photo.jpg"},
                        "user": {"name": "Lin Designer"},
                        "links": {
                            "html": "https://unsplash.com/photos/grid",
                            "download_location": "https://api.unsplash.com/photos/grid/download",
                        },
                        "width": 1200,
                        "height": 800,
                    }
                ]
            },
        )
    )
    assert await UnsplashProvider("").search("grid") == []
    assert route.call_count == 0

    candidates = await UnsplashProvider("test-key").search("grid")
    assert len(candidates) == 1
    assert candidates[0].author == "Lin Designer"
    assert candidates[0].download_location.endswith("/download")
    assert "Unsplash" in candidates[0].attribution
    assert route.calls.last.request.headers["Authorization"] == "Client-ID test-key"


@pytest.mark.asyncio
@respx.mock
async def test_pexels_provider_returns_attributed_candidates_and_handles_failures():
    route = respx.get(PexelsProvider.API_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "photos": [
                    {
                        "src": {"large": "https://images.pexels.com/photo.jpg"},
                        "photographer": "Morgan Photographer",
                        "url": "https://www.pexels.com/photo/grid/",
                        "width": 900,
                        "height": 600,
                    }
                ]
            },
        )
    )
    assert await PexelsProvider("").search("grid") == []
    candidates = await PexelsProvider("secret").search("grid")
    assert candidates[0].author == "Morgan Photographer"
    assert candidates[0].source_url.endswith("/grid/")
    assert route.calls.last.request.headers["Authorization"] == "secret"

    route.mock(return_value=httpx.Response(429))
    assert await PexelsProvider("secret").search("rate limited") == []
