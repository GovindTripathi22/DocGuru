from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..ai.prompt_enhancer import prompt_enhancer

router = APIRouter(prefix="/api", tags=["Enhance"])

class EnhancePromptRequest(BaseModel):
    prompt: str
    document_type: str = "docx"
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt enhancement failed: {str(e)}")
