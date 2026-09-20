import asyncio

import pytest

from backend.app.ai.image_service import ImageService


def test_distinct_long_queries_use_distinct_cache_entries(tmp_path):
    service = ImageService(cache_dir=tmp_path)
    prefix = "A common thirty-character image query prefix "
    first = asyncio.run(service.fetch_or_generate_image(prefix + "first", mode="generate"))
    second = asyncio.run(service.fetch_or_generate_image(prefix + "second", mode="generate"))
    assert first != second
