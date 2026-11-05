import logging
import uuid
from pathlib import Path
from typing import BinaryIO

import anyio
from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from ..analyzer.template_analyzer import TemplateAnalyzer
from ..config import settings
from ..errors import AppError, PayloadTooLarge, TemplateNotFound, UnsupportedFile
from ..security import (
    assert_resource_owner,
    check_rate_limit,
    get_safe_path,
    register_resource_owner,
    remove_resource_owner,
    sanitize_filename,
)
from ..validation.upload_file import validate_uploaded_file

router = APIRouter(prefix="/api", tags=["upload"])
analyzer = TemplateAnalyzer()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}
UPLOAD_FILE_REQUIRED = File(...)


def _copy_upload(source: BinaryIO, target_path: Path, max_bytes: int) -> None:
    total_bytes = 0
    with target_path.open("wb") as buffer:
        while chunk := source.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise PayloadTooLarge()
            buffer.write(chunk)


@router.post("/upload")
async def upload_template(
    file: UploadFile = UPLOAD_FILE_REQUIRED,
    x_session_id: str | None = Header(None, alias="X-Session-Id"),
):
    """
    Upload a DOCX, PPTX, or PDF template.
    Returns the unique template ID and full extracted TemplateSpecification.
    """
    filename = file.filename
    check_rate_limit("uploads", x_session_id, 10)
    file_ext = Path(filename).suffix.lower() if filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    safe_display_name = sanitize_filename(filename or "upload")
    template_id = f"{uuid.uuid4().hex}{file_ext}"
    target_path = settings.UPLOAD_DIR / template_id

    try:
        await anyio.to_thread.run_sync(
            _copy_upload, file.file, target_path, settings.MAX_UPLOAD_MB * 1024 * 1024
        )
        validate_uploaded_file(target_path, file_ext)
        with anyio.fail_after(settings.ANALYZE_TIMEOUT_SEC):
            spec = await anyio.to_thread.run_sync(
                analyzer.analyze, str(target_path), abandon_on_cancel=True
            )
        spec.filename = safe_display_name
        register_resource_owner("template", template_id, x_session_id)
        return {
            "success": True,
            "template_id": template_id,
            "original_filename": safe_display_name,
            "document_type": spec.document_type,
            "extracted_rules": spec.extracted_rules,
            "document_outline": spec.document_outline,
            "template_spec": spec,
        }
    except PayloadTooLarge:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        remove_resource_owner("template", template_id)
        raise
    except UnsupportedFile:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        remove_resource_owner("template", template_id)
        raise
    except TimeoutError as exc:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        remove_resource_owner("template", template_id)
        raise AppError(
            code="TEMPLATE_ANALYSIS_TIMEOUT",
            http_status=504,
            message="Template analysis exceeded its time limit.",
        ) from exc
    except AppError:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        remove_resource_owner("template", template_id)
        raise
    except OSError as exc:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        logger.exception("Failed to save uploaded template")
        raise AppError(
            code="UPLOAD_SAVE_FAILED", http_status=500, message="Failed to save uploaded file."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - parser failures are translated and partial uploads are removed
        # Remove invalid uploads after an unexpected parser failure.
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        remove_resource_owner("template", template_id)
        logger.exception("Failed to analyze template")
        raise AppError(
            code="TEMPLATE_ANALYSIS_FAILED",
            http_status=422,
            message="Template analysis failed. The document structure could not be parsed.",
        ) from exc


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    """Retrieve details and parsed specification for an uploaded template (SEC-07/08)."""
    template_path = get_safe_path(settings.UPLOAD_DIR, template_id, "Template")
    assert_resource_owner("template", template_id, x_session_id)
    if not template_path.exists():
        raise TemplateNotFound(template_id)
    try:
        with anyio.fail_after(settings.ANALYZE_TIMEOUT_SEC):
            spec = await anyio.to_thread.run_sync(
                analyzer.analyze, str(template_path), abandon_on_cancel=True
            )
        return {
            "template_id": template_id,
            "document_type": spec.document_type,
            "extracted_rules": spec.extracted_rules,
            "document_outline": spec.document_outline,
            "template_spec": spec,
        }
    except TimeoutError as exc:
        raise AppError(
            code="TEMPLATE_ANALYSIS_TIMEOUT",
            http_status=504,
            message="Template analysis exceeded its time limit.",
        ) from exc
    except Exception:  # noqa: BLE001 - analyzer failures are translated to a stable API error
        logger.exception("Failed to analyze template %s", template_id)
        raise AppError(
            code="TEMPLATE_ANALYSIS_FAILED", http_status=422, message="Template analysis failed."
        )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    """Delete an uploaded template file (SEC-07/08)."""
    template_path = get_safe_path(settings.UPLOAD_DIR, template_id, "Template")
    assert_resource_owner("template", template_id, x_session_id)
    if not template_path.exists():
        raise TemplateNotFound(template_id)
    try:
        template_path.unlink(missing_ok=True)
        remove_resource_owner("template", template_id)
        return {"success": True, "message": f"Template '{template_id}' deleted successfully."}
    except OSError:
        logger.exception("Failed to delete template %s", template_id)
        raise AppError(code="DELETE_FAILED", http_status=500, message="Failed to delete template.")
