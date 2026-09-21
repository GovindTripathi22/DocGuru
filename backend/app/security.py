"""Security utilities for safe path resolution and storage boundary enforcement (SEC-01)."""

import os
import re
from pathlib import Path
import unicodedata
from fastapi import HTTPException
import logging

from .errors import AppError

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str, max_length: int = 120) -> str:
    """Sanitizes user filename, normalizing unicode NFC and stripping control characters and path separators."""
    normalized = unicodedata.normalize("NFC", filename)
    # Strip carriage return, line feed, and null bytes
    clean = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f/\\]", "", normalized)
    # Strip dangerous shell/path characters
    clean = clean.strip(". ")
    if not clean:
        clean = "document"
    if len(clean) > max_length:
        stem = Path(clean).stem[: max_length - 10]
        ext = Path(clean).suffix[:10]
        clean = f"{stem}{ext}"
    return clean


def safe_join(base_dir: Path, *parts: str) -> Path:
    """
    Safely joins parts onto base_dir, rejecting directory traversal, absolute paths,
    backslash tricks, and null bytes. Guarantees result is strictly relative to base_dir.
    """
    resolved_base = base_dir.resolve()
    current = resolved_base

    for part in parts:
        if "\x00" in part:
            raise AppError(code="INVALID_PATH", http_status=400, message="Null byte in path is forbidden.")
        if "%2e%2e" in part.lower():
            raise AppError(code="INVALID_PATH", http_status=400, message="URL encoded traversal sequence forbidden.")

        # Check for windows/posix absolute or traversal
        p = Path(part)
        if p.is_absolute() or ".." in p.parts or "/" in part or "\\" in part:
            raise AppError(code="INVALID_PATH", http_status=400, message="Directory traversal or absolute path is forbidden.")

        current = (current / p.name).resolve()

    if not current.is_relative_to(resolved_base):
        raise AppError(code="INVALID_PATH", http_status=400, message="Path escape outside storage root is forbidden.")

    return current


def safe_path_join(base_dir: Path, *parts: str) -> Path:
    """Alias for safe_join."""
    return safe_join(base_dir, *parts)


def get_safe_path(base_dir: Path, untrusted_name: str, resource_name: str = "File") -> Path:
    """
    Validates and resolves a file path strictly within base_dir.
    Rejects absolute paths, directory traversal sequences, and paths outside base_dir.
    """
    raw = untrusted_name.strip()
    try:
        return safe_join(base_dir, raw)
    except AppError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {resource_name.lower()} path: traversal is forbidden.",
        )
