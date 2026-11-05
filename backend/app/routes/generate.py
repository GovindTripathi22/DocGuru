import logging

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from ..config import settings
from ..errors import AppError, LLMNotConfigured, TemplateNotFound
from ..jobs import job_manager
from ..models.generation import GenerationRequest, GenerationResponse
from ..security import assert_resource_owner, check_rate_limit, get_safe_path

router = APIRouter(prefix="/api", tags=["generate"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=None)
async def generate_document(
    req: GenerationRequest,
    wait: bool = Query(
        False, description="Whether to wait synchronously for generation completion (CLI/test mode)"
    ),
    x_session_id: str | None = Header(None, alias="X-Session-Id"),
):
    """
    Exact template-preserving generation endpoint (API-JOBS / D9).
    Returns 202 Accepted with a job_id for asynchronous polling via GET /api/jobs/{id}.
    If wait=true, executes synchronously and returns the final GenerationResponse.
    """
    if settings.mode == "misconfigured":
        raise LLMNotConfigured()

    check_rate_limit("generates", x_session_id, 5)

    # Pre-validate template existence before queueing job
    template_path = get_safe_path(settings.UPLOAD_DIR, req.template_id, "Template")
    assert_resource_owner("template", req.template_id, x_session_id)
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
    if completed_job.result is None:
        raise AppError(
            code="JOB_RESULT_MISSING",
            http_status=500,
            message="The generation job completed without a result payload.",
        )
    return GenerationResponse(**completed_job.result)
