"""Atomic cache with SHA-256 keying and LRU eviction (IMG-01)."""

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ImageCache:
    def __init__(self, cache_dir: Path, max_mb: int = 500, ttl_sec: int = 86400):
        self.cache_dir = cache_dir
        self.max_bytes = max_mb * 1024 * 1024
        self.ttl_sec = ttl_sec
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def compute_key(
        self,
        provider: str,
        normalized_query: str,
        width: int,
        height: int,
        fit: str = "crop",
    ) -> str:
        data = f"{provider.strip().lower()}:{normalized_query.strip().lower()}:{width}x{height}:{fit}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    async def get_lock(self, key: str) -> asyncio.Lock:
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def get(self, key: str) -> Optional[Tuple[Path, Dict[str, any]]]:
        jpg_path = self.cache_dir / f"{key}.jpg"
        meta_path = self.cache_dir / f"{key}.json"

        if not jpg_path.exists() or not meta_path.exists():
            return None

        try:
            mtime = jpg_path.stat().st_mtime
            if time.time() - mtime > self.ttl_sec:
                # Expired
                jpg_path.unlink(missing_ok=True)
                meta_path.unlink(missing_ok=True)
                return None

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            # Update access time for LRU
            now = time.time()
            os.utime(jpg_path, (now, now))
            return jpg_path, meta
        except Exception as e:
            logger.warning("Failed to read image cache for %s: %s", key, e)
            return None

    def put(self, key: str, image_bytes: bytes, metadata: dict) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        jpg_path = self.cache_dir / f"{key}.jpg"
        meta_path = self.cache_dir / f"{key}.json"

        tmp_jpg = self.cache_dir / f"{key}.jpg.tmp_{os.getpid()}_{time.time()}"
        tmp_meta = self.cache_dir / f"{key}.json.tmp_{os.getpid()}_{time.time()}"

        try:
            tmp_jpg.write_bytes(image_bytes)
            tmp_meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            # Atomic replace
            os.replace(tmp_jpg, jpg_path)
            os.replace(tmp_meta, meta_path)

            self.evict_if_needed()
            return jpg_path
        finally:
            if tmp_jpg.exists():
                tmp_jpg.unlink(missing_ok=True)
            if tmp_meta.exists():
                tmp_meta.unlink(missing_ok=True)

    def evict_if_needed(self) -> None:
        try:
            entries = []
            total_size = 0
            for item in self.cache_dir.glob("*.jpg"):
                if item.is_file():
                    stat = item.stat()
                    entries.append((item, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size

            if total_size <= self.max_bytes:
                return

            # Sort oldest first (LRU)
            entries.sort(key=lambda x: x[1])
            target_size = int(self.max_bytes * 0.85)  # Evict down to 85%

            for path, _, size in entries:
                if total_size <= target_size:
                    break
                meta_file = path.with_suffix(".json")
                path.unlink(missing_ok=True)
                meta_file.unlink(missing_ok=True)
                total_size -= size
        except Exception as e:
            logger.warning("Error during image cache eviction: %s", e)
