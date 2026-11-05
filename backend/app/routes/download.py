import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..errors import AppError
from ..security import (
    assert_resource_owner,
    get_safe_path,
    remove_resource_owner,
    sanitize_filename,
)

router = APIRouter(prefix="/api", tags=["download"])
logger = logging.getLogger(__name__)

MIME_MAP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".pdf": "application/pdf",
}


@router.get("/download/{filename}")
async def download_file(
    filename: str, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    """
    Download a generated DOCX, PPTX, or PDF document.
    Secured against directory traversal attacks and emits X-Content-Type-Options: nosniff (SEC-04).
    """
    file_path = get_safe_path(settings.OUTPUT_DIR, filename, "Output")
    assert_resource_owner("output", filename, x_session_id)
    if not file_path.exists():
        raise AppError(code="RESOURCE_NOT_FOUND", http_status=404, message="Resource not found.")

    ext = file_path.suffix.lower()
    media_type = MIME_MAP.get(ext, "application/octet-stream")
    safe_name = sanitize_filename(filename)

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type=media_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/outputs/{output_id}")
async def delete_output(
    output_id: str, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    """Delete a generated output file (SEC-07/08)."""
    output_path = get_safe_path(settings.OUTPUT_DIR, output_id, "Output")
    assert_resource_owner("output", output_id, x_session_id)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail=f"Output file '{output_id}' not found.")
    try:
        output_path.unlink(missing_ok=True)
        remove_resource_owner("output", output_id)
        return {"success": True, "message": f"Output '{output_id}' deleted successfully."}
    except OSError:
        logger.exception("Failed to delete output file %s", output_id)
        raise AppError(
            code="DELETE_FAILED", http_status=500, message="Failed to delete output file."
        )
