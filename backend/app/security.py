"""Security utilities for safe path resolution and storage boundary enforcement (SEC-01)."""

from pathlib import Path
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


def get_safe_path(base_dir: Path, untrusted_name: str, resource_name: str = "File") -> Path:
    """
    Validates and resolves a file path strictly within base_dir.
    Rejects absolute paths, directory traversal sequences, and paths outside base_dir.
    Raises HTTPException(400) on traversal / absolute path attempt.
    """
    raw = untrusted_name.strip()
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts or p.name != raw:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {resource_name.lower()} path: absolute paths and directory traversal are forbidden.",
        )

    resolved_base = base_dir.resolve()
    resolved_target = (base_dir / p.name).resolve()

    if not resolved_target.is_relative_to(resolved_base):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {resource_name.lower()} path: access outside authorized storage is forbidden.",
        )

    return resolved_target
