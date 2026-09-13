from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from ..config import settings

router = APIRouter(prefix="/api", tags=["download"])

MIME_MAP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".pdf": "application/pdf"
}

@router.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download a generated DOCX, PPTX, or PDF document.
    Secured against directory traversal attacks.
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
        headers={"Content-Disposition": f"attachment; filename={safe_name}"}
    )
