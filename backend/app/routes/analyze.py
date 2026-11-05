import logging

import anyio
from fastapi import APIRouter, Header
from pydantic import BaseModel

from ..analyzer.template_analyzer import TemplateAnalyzer
from ..config import settings
from ..errors import AppError, TemplateNotFound
from ..security import assert_resource_owner, get_safe_path

router = APIRouter(prefix="/api", tags=["analyze"])
analyzer = TemplateAnalyzer()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    template_id: str


@router.post("/analyze")
async def analyze_template(
    req: AnalyzeRequest, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    """
    Re-analyzes an existing uploaded template.
    """
    file_path = get_safe_path(settings.UPLOAD_DIR, req.template_id, "Template")
    assert_resource_owner("template", req.template_id, x_session_id)
    if not file_path.exists():
        raise TemplateNotFound(req.template_id)

    try:
        with anyio.fail_after(settings.ANALYZE_TIMEOUT_SEC):
            spec = await anyio.to_thread.run_sync(
                analyzer.analyze, str(file_path), abandon_on_cancel=True
            )
        return {"success": True, "template_id": req.template_id, "template_spec": spec}
    except TimeoutError as exc:
        raise AppError(
            code="TEMPLATE_ANALYSIS_TIMEOUT",
            http_status=504,
            message="Template analysis exceeded its time limit.",
        ) from exc
    except Exception:  # noqa: BLE001 - analyzer failures are translated to a stable API error
        logger.exception("Analysis failed for %s", req.template_id)
        raise AppError(
            code="TEMPLATE_ANALYSIS_FAILED", http_status=422, message="Template analysis failed."
        )
