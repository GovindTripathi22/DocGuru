from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import logging

from ..config import settings
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..models.template_spec import TemplateSpecification
from ..errors import AppError, TemplateNotFound
from ..security import get_safe_path

router = APIRouter(prefix="/api", tags=["analyze"])
analyzer = TemplateAnalyzer()
logger = logging.getLogger(__name__)

class AnalyzeRequest(BaseModel):
    template_id: str

@router.post("/analyze")
async def analyze_template(req: AnalyzeRequest):
    """
    Re-analyzes an existing uploaded template.
    """
    file_path = get_safe_path(settings.UPLOAD_DIR, req.template_id, "Template")
    if not file_path.exists():
        raise TemplateNotFound(req.template_id)

    try:
        spec = analyzer.analyze(str(file_path))
        return {
            "success": True,
            "template_id": req.template_id,
            "template_spec": spec
        }
    except Exception as e:
        logger.exception("Analysis failed for %s", req.template_id)
        raise AppError(code="TEMPLATE_ANALYSIS_FAILED", http_status=422, message="Template analysis failed.")
