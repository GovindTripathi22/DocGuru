import logging

import anyio
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..analyzer.template_analyzer import TemplateAnalyzer
from ..config import settings
from ..errors import AppError
from ..models.generation import ValidationReport
from ..security import assert_resource_owner, get_safe_path
from ..validation.diff_validator import DiffValidator

router = APIRouter(prefix="/api", tags=["validate"])
analyzer = TemplateAnalyzer()
validator = DiffValidator()
logger = logging.getLogger(__name__)


class ValidateRequest(BaseModel):
    template_id: str
    generated_filename: str


@router.post("/validate", response_model=ValidationReport)
async def validate_document(
    req: ValidateRequest, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    """
    Compares the original template against the generated file to verify zero format drift.
    """
    template_path = get_safe_path(settings.UPLOAD_DIR, req.template_id, "Template")
    generated_path = get_safe_path(settings.OUTPUT_DIR, req.generated_filename, "Generated file")
    assert_resource_owner("template", req.template_id, x_session_id)
    assert_resource_owner("output", req.generated_filename, x_session_id)

    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    if not generated_path.exists():
        raise HTTPException(status_code=404, detail="Generated file not found")

    try:
        report = await anyio.to_thread.run_sync(
            _analyze_and_validate, str(template_path), str(generated_path)
        )
        return report
    except Exception:  # noqa: BLE001 - validation failures are translated to a stable API error
        logger.exception(
            "Validation failed for template=%s, generated=%s",
            req.template_id,
            req.generated_filename,
        )
        raise AppError(code="VALIDATION_FAILED", http_status=422, message="Validation failed.")


def _analyze_and_validate(template_path: str, generated_path: str) -> ValidationReport:
    """Run synchronous document parsing and validation in the bounded worker pool."""
    original_spec = analyzer.analyze(template_path)
    return validator.validate(original_spec, generated_path, original_file_path=template_path)
