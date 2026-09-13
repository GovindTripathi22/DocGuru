from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path

from ..config import settings
from ..models.generation import ValidationReport
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..validation.diff_validator import DiffValidator

router = APIRouter(prefix="/api", tags=["validate"])
analyzer = TemplateAnalyzer()
validator = DiffValidator()

class ValidateRequest(BaseModel):
    template_id: str
    generated_filename: str

@router.post("/validate", response_model=ValidationReport)
async def validate_document(req: ValidateRequest):
    """
    Compares the original template against the generated file to verify zero format drift.
    """
    template_path = settings.UPLOAD_DIR / req.template_id
    generated_path = settings.OUTPUT_DIR / req.generated_filename

    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    if not generated_path.exists():
        raise HTTPException(status_code=404, detail="Generated file not found")

    try:
        orig_spec = analyzer.analyze(str(template_path))
        report = validator.validate(orig_spec, str(generated_path))
        return report
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Validation failed: {str(e)}")
