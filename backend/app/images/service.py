"""Production-grade image fetching, validation, caching, and placeholder service (Phase 6)."""

import asyncio
import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import httpx
from PIL import Image

from ..config import settings
from .cache import ImageCache
from .models import ImageCandidate
from .placeholder import generate_neutral_placeholder
from .provider import ImageProvider, PexelsProvider, UnsplashProvider, WikimediaProvider

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_HOSTS = {
    "commons.wikimedia.org",
    "upload.wikimedia.org",
    "images.unsplash.com",
    "api.unsplash.com",
    "images.pexels.com",
    "api.pexels.com",
}


class ImageService:
    def __init__(self, cache_dir: Optional[Path] = None):
        cache_path = cache_dir or (settings.DATA_DIR / "cache" / "images")
        self.cache = ImageCache(
            cache_dir=cache_path,
            max_mb=settings.IMAGE_CACHE_MAX_MB,
        )
        self.placeholder_dir = settings.DATA_DIR / "cache" / "placeholders"
        self.placeholder_dir.mkdir(parents=True, exist_ok=True)
        self._provider: Optional[ImageProvider] = None
        self._semaphore = asyncio.Semaphore(4)

    @property
    def provider(self) -> ImageProvider:
        if self._provider is None:
            if settings.UNSPLASH_ACCESS_KEY:
                self._provider = UnsplashProvider(settings.UNSPLASH_ACCESS_KEY)
            elif settings.PEXELS_API_KEY:
                self._provider = PexelsProvider(settings.PEXELS_API_KEY)
            else:
                self._provider = WikimediaProvider()
        return self._provider

    @property
    def has_configured_provider(self) -> bool:
        return bool(settings.UNSPLASH_ACCESS_KEY or settings.PEXELS_API_KEY)

    async def fetch_or_generate_image(
        self,
        query_or_prompt: str,
        mode: str = "search",  # "off", "search", "placeholder"
        width: int = 800,
        height: int = 450,
        caption: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Coordinates real image search, caching, downloading, and placeholder fallback.
        Returns the absolute local path to a JPEG image file, or None if skipped.
        """
        clean_query = query_or_prompt.strip()
        effective_caption = caption or clean_query

        if mode == "off":
            return None

        offline_mode = getattr(settings, "OFFLINE_MODE", False)
        if offline_mode or mode == "placeholder":
            # Generate unbranded neutral placeholder
            key = self.cache.compute_key("placeholder", clean_query, width, height)
            placeholder_path = self.placeholder_dir / f"ph_{key}_{width}x{height}.jpg"
            if not placeholder_path.exists():
                generate_neutral_placeholder(effective_caption, placeholder_path, width, height)
            return str(placeholder_path)

        # Real provider search
        provider_name = self.provider.__class__.__name__.lower().replace("provider", "")
        key = self.cache.compute_key(provider_name, clean_query, width, height)

        # Check cache
        cached = self.cache.get(key)
        if cached:
            return str(cached[0])

        # Acquire lock for this key to prevent duplicate concurrent downloads
        key_lock = await self.cache.get_lock(key)
        async with key_lock:
            # Double-check after acquiring lock
            cached = self.cache.get(key)
            if cached:
                return str(cached[0])

            async with self._semaphore:
                image_path = await self._search_real_image(
                    clean_query,
                    dest_path=None,
                    width=width,
                    height=height,
                )

            if image_path:
                return image_path

            # Fallback to placeholder on failure or timeout
            placeholder_path = self.placeholder_dir / f"ph_{key}_{width}x{height}.jpg"
            if not placeholder_path.exists():
                generate_neutral_placeholder(effective_caption, placeholder_path, width, height)
            if warnings is not None:
                warnings.append(f"images_skipped_no_provider:{clean_query[:30]}")
            return str(placeholder_path)

    async def _search_real_image(
        self,
        query: str,
        dest_path: Optional[Path] = None,
        width: int = 800,
        height: int = 450,
    ) -> Optional[str]:
        provider_name = self.provider.__class__.__name__.lower().replace("provider", "")
        key = self.cache.compute_key(provider_name, query, width, height)
        return await self._search_and_download(
            query=query,
            provider_name=provider_name,
            key=key,
            width=width,
            height=height,
            caption=query,
        )

    async def _search_and_download(
        self,
        query: str,
        provider_name: str,
        key: str,
        width: int,
        height: int,
        caption: str,
    ) -> Optional[str]:
        try:
            candidates = await asyncio.wait_for(
                self.provider.search(query, width, height),
                timeout=settings.IMAGE_TIMEOUT_SEC,
            )
            if not candidates:
                return None

            candidate = candidates[0]
            # Validate host SSRF allow-list
            parsed = urlparse(candidate.url)
            if parsed.netloc.lower() not in ALLOWED_IMAGE_HOSTS:
                logger.warning("Rejecting image download from untrusted host: %s", parsed.netloc)
                return None

            async with httpx.AsyncClient(timeout=settings.IMAGE_TIMEOUT_SEC, follow_redirects=True) as client:
                resp = await client.get(candidate.url)
                if resp.status_code != 200:
                    return None

                content_type = resp.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    return None

                if len(resp.content) > 15 * 1024 * 1024:  # 15 MB limit
                    return None

                # Pillow validation and sanitization
                processed_bytes = self._process_image(resp.content, width, height)
                if not processed_bytes:
                    return None

                # Notify download location if Unsplash
                if candidate.download_location and isinstance(self.provider, UnsplashProvider):
                    try:
                        await client.get(
                            candidate.download_location,
                            headers={"Authorization": f"Client-ID {self.provider.access_key}"},
                        )
                    except Exception:
                        pass

                meta = {
                    "query": query,
                    "provider": provider_name,
                    "license": candidate.license,
                    "author": candidate.author,
                    "attribution": candidate.attribution,
                    "source_url": candidate.source_url,
                }
                saved_path = self.cache.put(key, processed_bytes, meta)
                return str(saved_path)
        except Exception as e:
            logger.warning("Failed to search and download image for '%s': %s", query, e)
            return None

    def _process_image(self, raw_bytes: bytes, target_w: int, target_h: int) -> Optional[bytes]:
        try:
            bio = io.BytesIO(raw_bytes)
            img = Image.open(bio)
            img.verify()  # Validate image integrity

            # Reopen after verify
            bio.seek(0)
            img = Image.open(bio)

            # Cap max 20 Megapixels
            if img.width * img.height > 20_000_000:
                return None

            # Min 400x250
            if img.width < 100 or img.height < 100:
                return None

            # Handle animation frames
            if getattr(img, "is_animated", False):
                img.seek(0)

            # Convert to RGB
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Scale if long side > 2000px
            max_side = max(img.width, img.height)
            if max_side > 2000:
                scale = 2000 / max_side
                new_w = max(1, int(img.width * scale))
                new_h = max(1, int(img.height * scale))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=88, optimize=True)
            return out_buf.getvalue()
        except Exception as e:
            logger.warning("Image processing failed: %s", e)
            return None


image_service = ImageService()
__all__ = ["ImageService", "image_service"]

