from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from ..ai.prompt_enhancer import prompt_enhancer
from ..errors import AppError

router = APIRouter(prefix="/api", tags=["Enhance"])
logger = logging.getLogger(__name__)

from typing import Literal, Optional

class EnhancePromptRequest(BaseModel):
    prompt: str
    document_type: Literal["docx", "pptx", "pdf"] = "docx"
    template_title: Optional[str] = None

class EnhancePromptResponse(BaseModel):
    original_prompt: str
    enhanced_prompt: str

@router.post("/enhance-prompt", response_model=EnhancePromptResponse)
async def enhance_prompt_endpoint(req: EnhancePromptRequest):
    try:
        enhanced = await prompt_enhancer.enhance(
            prompt=req.prompt,
            document_type=req.document_type,
            template_title=req.template_title
        )
        return EnhancePromptResponse(
            original_prompt=req.prompt,
            enhanced_prompt=enhanced
        )
    except AppError:
        raise
    except Exception as e:
        logger.exception("Prompt enhancement failed")
        raise AppError(code="PROMPT_ENHANCEMENT_FAILED", http_status=500, message="Prompt enhancement failed.")
