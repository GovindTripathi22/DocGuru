"""Security utilities for safe path resolution and storage boundary enforcement (SEC-01)."""

import hashlib
import json
import logging
import re
import unicodedata
from collections import defaultdict, deque
from pathlib import Path
from time import monotonic

from fastapi import HTTPException

from .config import settings
from .errors import AppError

logger = logging.getLogger(__name__)
_RATE_WINDOWS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _owner_path(resource_type: str, resource_id: str) -> Path:
    if resource_type not in {"template", "output"}:
        raise ValueError("Unknown resource type.")
    digest = hashlib.sha256(resource_id.encode("utf-8")).hexdigest()
    return settings.DATA_DIR / "ownership" / f"{resource_type}-{digest}.json"


def register_resource_owner(resource_type: str, resource_id: str, session_id: str | None) -> None:
    """Persist resource ownership independently of the client-visible filename."""
    path = _owner_path(resource_type, resource_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    owner = session_id or "anonymous"
    temporary.write_text(json.dumps({"owner": owner}), encoding="utf-8")
    temporary.replace(path)


def remove_resource_owner(resource_type: str, resource_id: str) -> None:
    _owner_path(resource_type, resource_id).unlink(missing_ok=True)


def assert_resource_owner(resource_type: str, resource_id: str, session_id: str | None) -> None:
    """Return 404 for foreign or unowned resources to avoid disclosing their existence."""
    path = _owner_path(resource_type, resource_id)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Preserve manually managed local files when authentication is disabled.
        if not settings.API_KEYS.strip():
            return
        raise AppError(code="RESOURCE_NOT_FOUND", http_status=404, message="Resource not found.")
    owner = record.get("owner") if isinstance(record, dict) else None
    if owner != (session_id or "anonymous"):
        raise AppError(code="RESOURCE_NOT_FOUND", http_status=404, message="Resource not found.")


def check_rate_limit(action: str, session_id: str | None, limit: int) -> None:
    """Apply an in-process rolling one-minute limit and report a retry delay."""
    now = monotonic()
    window = _RATE_WINDOWS[(action, session_id or "anonymous")]
    while window and window[0] <= now - 60:
        window.popleft()
    if len(window) >= limit:
        from .errors import LLMRateLimited

        retry_after = max(1, int(60 - (now - window[0])))
        raise LLMRateLimited(
            f"Too many {action} requests. Wait before trying again.", retry_after=retry_after
        )
    window.append(now)


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
            raise AppError(
                code="INVALID_PATH", http_status=400, message="Null byte in path is forbidden."
            )
        if "%2e%2e" in part.lower():
            raise AppError(
                code="INVALID_PATH",
                http_status=400,
                message="URL encoded traversal sequence forbidden.",
            )

        # Check for windows/posix absolute or traversal
        p = Path(part)
        if p.is_absolute() or ".." in p.parts or "/" in part or "\\" in part:
            raise AppError(
                code="INVALID_PATH",
                http_status=400,
                message="Directory traversal or absolute path is forbidden.",
            )

        current = (current / p.name).resolve()

    if not current.is_relative_to(resolved_base):
        raise AppError(
            code="INVALID_PATH",
            http_status=400,
            message="Path escape outside storage root is forbidden.",
        )

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
    except (OSError, TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {resource_name.lower()} path: traversal is forbidden.",
        )
