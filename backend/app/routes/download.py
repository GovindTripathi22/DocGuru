import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..errors import AppError
from ..security import get_safe_path

router = APIRouter(prefix="/api", tags=["download"])
logger = logging.getLogger(__name__)

MIME_MAP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".pdf": "application/pdf",
}


@router.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download a generated DOCX, PPTX, or PDF document.
    Secured against directory traversal attacks and emits X-Content-Type-Options: nosniff (SEC-04).
    """
    safe_name = Path(filename).name
    file_path = (settings.OUTPUT_DIR / safe_name).resolve()

    if not file_path.exists() or not file_path.is_relative_to(settings.OUTPUT_DIR.resolve()):
        # Also check uploads folder if user wants to download uploaded template
        upload_path = (settings.UPLOAD_DIR / safe_name).resolve()
        if upload_path.exists() and upload_path.is_relative_to(settings.UPLOAD_DIR.resolve()):
            file_path = upload_path
        else:
            raise HTTPException(status_code=404, detail=f"File '{safe_name}' not found.")

    ext = file_path.suffix.lower()
    media_type = MIME_MAP.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={safe_name}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/outputs/{output_id}")
async def delete_output(output_id: str):
    """Delete a generated output file (SEC-07/08)."""
    output_path = get_safe_path(settings.OUTPUT_DIR, output_id, "Output")
    if not output_path.exists():
        raise HTTPException(status_code=404, detail=f"Output file '{output_id}' not found.")
    try:
        output_path.unlink(missing_ok=True)
        return {"success": True, "message": f"Output '{output_id}' deleted successfully."}
    except Exception as e:
        logger.exception("Failed to delete output file %s: %s", output_id, e)
        raise AppError(code="DELETE_FAILED", http_status=500, message="Failed to delete output file.")
