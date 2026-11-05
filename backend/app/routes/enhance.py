import logging
from typing import Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel

from ..ai.prompt_enhancer import prompt_enhancer
from ..errors import AppError
from ..security import check_rate_limit

router = APIRouter(prefix="/api", tags=["Enhance"])
logger = logging.getLogger(__name__)


class EnhancePromptRequest(BaseModel):
    prompt: str
    document_type: Literal["docx", "pptx", "pdf"] = "docx"
    template_title: str | None = None


class EnhancePromptResponse(BaseModel):
    original_prompt: str
    enhanced_prompt: str


@router.post("/enhance-prompt", response_model=EnhancePromptResponse)
async def enhance_prompt_endpoint(
    req: EnhancePromptRequest, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    check_rate_limit("prompt enhancements", x_session_id, 20)
    try:
        enhanced = await prompt_enhancer.enhance(
            prompt=req.prompt, document_type=req.document_type, template_title=req.template_title
        )
        return EnhancePromptResponse(original_prompt=req.prompt, enhanced_prompt=enhanced)
    except AppError:
        raise
    except Exception:  # noqa: BLE001 - prompt provider failures are translated to an API error
        logger.exception("Prompt enhancement failed")
        raise AppError(
            code="PROMPT_ENHANCEMENT_FAILED", http_status=500, message="Prompt enhancement failed."
        )
