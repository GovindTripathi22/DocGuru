import logging
from typing import Any, Dict, Optional, Union
from fastapi import APIRouter, Header, Query, Response
from fastapi.responses import JSONResponse

from ..config import settings
from ..errors import AppError, LLMNotConfigured, TemplateNotFound
from ..jobs import job_manager
from ..models.generation import GenerationRequest, GenerationResponse
from ..security import get_safe_path

router = APIRouter(prefix="/api", tags=["generate"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=None)
async def generate_document(
    req: GenerationRequest,
    wait: bool = Query(False, description="Whether to wait synchronously for generation completion (CLI/test mode)"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """
    Exact template-preserving generation endpoint (API-JOBS / D9).
    Returns 202 Accepted with a job_id for asynchronous polling via GET /api/jobs/{id}.
    If wait=true, executes synchronously and returns the final GenerationResponse.
    """
    if settings.mode == "misconfigured":
        raise LLMNotConfigured()

    # Pre-validate template existence before queueing job
    template_path = get_safe_path(settings.UPLOAD_DIR, req.template_id, "Template")
    if not template_path.exists():
        raise TemplateNotFound(req.template_id)

    if not wait:
        job = job_manager.submit_job(req, session_id=x_session_id)
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job.job_id,
                "status": job.status,
                "stage": job.stage,
                "message": "Job accepted for processing.",
            },
        )

    completed_job = await job_manager.execute_direct(req, session_id=x_session_id)
    return GenerationResponse(**completed_job.result)
