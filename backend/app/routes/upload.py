from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid
import shutil
from pathlib import Path
import logging

from ..config import settings
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..models.template_spec import TemplateSpecification
from ..errors import AppError

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
            detail=f"Unsupported file type '{file_ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
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
            "template_spec": spec
        }
    except Exception as e:
        logger.exception("Failed to analyze template")
        raise AppError(code="TEMPLATE_ANALYSIS_FAILED", http_status=422, message="Template analysis failed. The document structure could not be parsed.")
