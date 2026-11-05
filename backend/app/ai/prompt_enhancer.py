import logging

from ..config import settings
from ..errors import AppError, LLMUnavailable
from .gemma_client import GemmaClient

logger = logging.getLogger(__name__)


class PromptEnhancer:
    """
    Enhances user prompts into comprehensive, structured document instructions.
    Budget >= 600 tokens; returns 502 on failure in live mode (LLM-02).
    """

    def __init__(self):
        self.client = GemmaClient()

    async def enhance(
        self, prompt: str, document_type: str = "docx", template_title: str | None = None
    ) -> str:
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
                max_tokens=max(600, settings.OUTLINE_MAX_TOKENS),
            )
            if isinstance(res, dict) and "enhanced_prompt" in res and res["enhanced_prompt"]:
                return str(res["enhanced_prompt"]).strip()
        except AppError:
            raise
        except Exception as e:  # noqa: BLE001 - normalize provider failures to a typed LLM error
            logger.warning("AI prompt enhancement request failed (%s)", type(e).__name__)
            raise LLMUnavailable(
                "Prompt enhancement request failed. Retry or edit the prompt directly."
            ) from e

        raise LLMUnavailable("Prompt enhancer received an invalid response from the AI model.")


prompt_enhancer = PromptEnhancer()
