import logging
from pathlib import Path
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from ..analyzer.template_analyzer import TemplateAnalyzer
from ..config import settings
from ..errors import AppError, TemplateNotFound
from ..models.template_spec import TemplateSpecification
from ..security import get_safe_path

router = APIRouter(prefix="/api", tags=["upload"])
analyzer = TemplateAnalyzer()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}


@router.post("/upload")
async def upload_template(file: UploadFile = File(...)):
    """
    Upload a DOCX, PPTX, or PDF template.
    Returns the unique template ID and full extracted TemplateSpecification.
    """
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    template_id = str(uuid.uuid4())
    safe_filename = f"{template_id}_{Path(file.filename).name}"
    target_path = settings.UPLOAD_DIR / safe_filename

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.exception("Failed to save uploaded file")
        raise AppError(code="UPLOAD_SAVE_FAILED", http_status=500, message="Failed to save uploaded file.")

    try:
        spec = analyzer.analyze(str(target_path))
        return {
            "success": True,
            "template_id": safe_filename,
            "original_filename": file.filename,
            "document_type": spec.document_type,
            "extracted_rules": spec.extracted_rules,
            "document_outline": spec.document_outline,
            "template_spec": spec,
        }
    except Exception as e:
        logger.exception("Failed to analyze template")
        raise AppError(
            code="TEMPLATE_ANALYSIS_FAILED",
            http_status=422,
            message="Template analysis failed. The document structure could not be parsed.",
        )


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Retrieve details and parsed specification for an uploaded template (SEC-07/08)."""
    template_path = get_safe_path(settings.UPLOAD_DIR, template_id, "Template")
    if not template_path.exists():
        raise TemplateNotFound(template_id)
    try:
        spec = analyzer.analyze(str(template_path))
        return {
            "template_id": template_id,
            "document_type": spec.document_type,
            "extracted_rules": spec.extracted_rules,
            "document_outline": spec.document_outline,
            "template_spec": spec,
        }
    except Exception as e:
        logger.exception("Failed to analyze template %s: %s", template_id, e)
        raise AppError(code="TEMPLATE_ANALYSIS_FAILED", http_status=422, message="Template analysis failed.")


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete an uploaded template file (SEC-07/08)."""
    template_path = get_safe_path(settings.UPLOAD_DIR, template_id, "Template")
    if not template_path.exists():
        raise TemplateNotFound(template_id)
    try:
        template_path.unlink(missing_ok=True)
        return {"success": True, "message": f"Template '{template_id}' deleted successfully."}
    except Exception as e:
        logger.exception("Failed to delete template %s: %s", template_id, e)
        raise AppError(code="DELETE_FAILED", http_status=500, message="Failed to delete template.")
