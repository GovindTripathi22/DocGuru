from typing import Optional, Dict, Any
import logging
from .gemma_client import GemmaClient

from ..config import settings
from ..errors import LLMUnavailable

logger = logging.getLogger(__name__)

class PromptEnhancer:
    """
    Enhances user prompts into comprehensive, structured document instructions.
    Budget >= 600 tokens; returns 502 on failure in live mode (LLM-02).
    """
    def __init__(self):
        self.client = GemmaClient()

    async def enhance(self, prompt: str, document_type: str = "docx", template_title: Optional[str] = None) -> str:
        prompt_clean = prompt.strip()
        if not prompt_clean:
            prompt_clean = "Comprehensive organizational overview"

        system_prompt = (
            f"You are an expert prompt engineer for an exact template-preserving AI document generator. "
            f"Your task is to expand the user prompt into a structured, professional specification for a {document_type.upper()} artifact.\n\n"
            f"Output MUST be valid JSON in this exact schema:\n"
            f'{{"enhanced_prompt": "your detailed enhanced prompt string here"}}'
        )

        user_message = f"Enhance this prompt for a {document_type.upper()}: '{prompt_clean}'"

        try:
            res = await self.client.generate_structured_json(
                system_prompt=system_prompt,
                user_prompt=user_message,
                max_tokens=350
            )
            if isinstance(res, dict) and "enhanced_prompt" in res and res["enhanced_prompt"]:
                return str(res["enhanced_prompt"]).strip()
        except Exception as e:
            logger.warning("AI Prompt enhancement error: %s", e)
            raise LLMUnavailable(f"Prompt enhancement service failed: {e}") from e

        raise LLMUnavailable("Prompt enhancer received an invalid response from the AI model.")

prompt_enhancer = PromptEnhancer()
