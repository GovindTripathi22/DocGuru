from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid
import shutil
from pathlib import Path
import logging

from ..config import settings
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..models.template_spec import TemplateSpecification

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
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

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
        logger.error(f"Failed to analyze template: {e}")
        raise HTTPException(status_code=422, detail=f"Template analysis failed: {str(e)}")
