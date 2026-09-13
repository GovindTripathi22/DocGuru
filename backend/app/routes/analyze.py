from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path

from ..config import settings
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..models.template_spec import TemplateSpecification

router = APIRouter(prefix="/api", tags=["analyze"])
analyzer = TemplateAnalyzer()

class AnalyzeRequest(BaseModel):
    template_id: str

@router.post("/analyze")
async def analyze_template(req: AnalyzeRequest):
    """
    Re-analyzes an existing uploaded template.
    """
    file_path = settings.UPLOAD_DIR / req.template_id
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        spec = analyzer.analyze(str(file_path))
        return {
            "success": True,
            "template_id": req.template_id,
            "template_spec": spec
        }
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Analysis failed: {str(e)}")
