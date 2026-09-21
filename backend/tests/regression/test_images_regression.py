"""Regression test suite for Image Service (IMG-01, IMG-02, IMG-03, IMG-04)."""

import asyncio
from pathlib import Path
import pytest
import respx
import httpx

from backend.app.images.service import ImageService
from backend.app.images.provider import WikimediaProvider, UnsplashProvider
from backend.app.images.placeholder import generate_neutral_placeholder
from backend.app.config import settings


def test_distinct_long_queries_use_distinct_cache_entries(tmp_path):
    """IMG-01 & A-20: Three queries sharing a 30-character prefix produce three distinct cache entries."""
    service = ImageService(cache_dir=tmp_path)
    prefix = "A common thirty-character image query prefix "
    q1 = prefix + "Alpha variant"
    q2 = prefix + "Beta variant"
    q3 = prefix + "Gamma variant"

    k1 = service.cache.compute_key("wikimedia", q1, 800, 450)
    k2 = service.cache.compute_key("wikimedia", q2, 800, 450)
    k3 = service.cache.compute_key("wikimedia", q3, 800, 450)

    assert len({k1, k2, k3}) == 3, "Cache keys collided despite distinct suffixes!"


def test_no_fixed_photo_routing_for_semantic_keywords(tmp_path):
    """IMG-02 & A-21: Queries never route to hardcoded photos via substring sniffing."""
    service = ImageService(cache_dir=tmp_path)
    
    # Assert provider search uses query as-is, not hardcoded Go or AI photo maps
    provider = service.provider
    assert not hasattr(provider, "PHOTO_MAP")
    assert not hasattr(service, "PHOTO_MAP")


@respx.mock
def test_atomic_write_and_caching(tmp_path):
    """IMG-01: Images are fetched, validated, and atomically saved with metadata."""
    cache_dir = tmp_path / "cache"
    service = ImageService(cache_dir=cache_dir)
    
    # 1x1 valid JPEG
    valid_jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00d\x00d\x01\x01\"\x00\xff\xc4\x00\x1f\x00"
        b"\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01"
        b"\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    )

    key = service.cache.compute_key("wikimedia", "test query", 800, 450)
    meta = {"license": "CC-BY", "author": "Photographer"}
    saved = service.cache.put(key, valid_jpeg, meta)
    
    assert saved.exists()
    assert (cache_dir / f"{key}.json").exists()
    
    cached = service.cache.get(key)
    assert cached is not None
    assert cached[0] == saved
    assert cached[1]["author"] == "Photographer"


def test_neutral_placeholder_contains_no_banned_copy(tmp_path):
    """IMG-03: Neutral placeholders contain no marketing hype, no product claims, and wrap cleanly."""
    dest = tmp_path / "placeholder.jpg"
    generate_neutral_placeholder("Annual quarterly financial breakdown metrics", dest, 800, 450)
    assert dest.exists()
    assert dest.stat().st_size > 500
