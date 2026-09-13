from typing import Optional, Dict, Any
import logging
from .gemma_client import GemmaClient

logger = logging.getLogger(__name__)

class PromptEnhancer:
    """
    Enhances short, ambiguous, or incomplete user prompts into comprehensive,
    highly-structured document instructions optimized for exact template inheritance.
    """
    def __init__(self):
        self.client = GemmaClient()

    async def enhance(self, prompt: str, document_type: str = "docx", template_title: Optional[str] = None) -> str:
        prompt_clean = prompt.strip()
        if not prompt_clean:
            return "Create a comprehensive executive report with executive summary, methodology, comparative analysis tables, and strategic recommendations."

        system_prompt = (
            f"You are an expert prompt engineer for an exact template-preserving AI document generator. "
            f"Your task is to take the user's short input prompt and expand it into a detailed, professional, "
            f"high-impact prompt for generating a {document_type.upper()} artifact.\n\n"
            f"Include:\n"
            f"1. A clear, authoritative title and executive scope\n"
            f"2. 4-5 structured sections with specific analytical focus\n"
            f"3. Explicit request for a comparative benchmark data table\n"
            f"4. Relevant visual figure/image request\n"
            f"5. Clear requirement to preserve 100% of the document's original visual theme and fonts.\n\n"
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
            logger.warning(f"AI Prompt enhancement error: {e}")

        # Deterministic instant enhancement fallback
        topic = prompt_clean
        if document_type == "pptx":
            return (
                f"Create a high-impact, executive presentation on '{topic}'. "
                f"Structure into 5 cohesive slides: (1) Title & Strategic Vision, (2) Executive Problem Statement & Market Context, "
                f"(3) Core Technical Architecture & Methodology, (4) Quantitative Benchmarks with a Comparative Performance Table, "
                f"and (5) Strategic Next Steps & Roadmap. Include high-resolution visual figure placeholders and adhere 100% to the slide master theme."
            )
        else:
            return (
                f"Generate a rigorous, publication-grade technical report on '{topic}'. "
                f"Include: 1. Executive Summary delineating key findings; 2. Domain Background and Architectural Motivation; "
                f"3. Technical Methodology and Subsystem Analysis; 4. System Benchmarks featuring a structured multi-column comparison table; "
                f"5. Strategic Recommendations and Implementation Checklist. Integrate relevant visual figure assets and strictly preserve all original template headings, borders, and margins."
            )

prompt_enhancer = PromptEnhancer()
