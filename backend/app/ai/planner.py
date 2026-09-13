from typing import Dict, Any, Optional
import json
import logging

from .gemma_client import GemmaClient
from .content_fitter import ContentFitter
from ..models.template_spec import TemplateSpecification
from ..models.generation import (
    DocumentPlan,
    DocumentSection,
    PresentationPlan,
    SlidePlan,
    TableData,
)

logger = logging.getLogger(__name__)

class DocumentPlanner:
    """
    PLANNER mode (§24).
    Uses Gemma 4 to analyze the user request and template specification,
    producing a structured DocumentPlan or PresentationPlan.
    """

    def __init__(self):
        self.client = GemmaClient()

    async def plan_document(
        self,
        user_prompt: str,
        template_spec: TemplateSpecification,
        target_pages: Optional[int] = None,
        custom_instructions: Optional[str] = None,
        include_images: bool = True,
        image_mode: str = "auto"
    ) -> DocumentPlan:
        """
        Creates a structured DocumentPlan strictly using the available styles in template_spec.
        """
        available_headings = template_spec.available_heading_styles or []
        default_heading = available_headings[0] if available_headings else None

        system_prompt = f"""
You are Gemma 4, an advanced reasoning and document planning AI.
Your task is to plan the exact content structure for a professional document.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. YOU DO NOT CONTROL FORMATTING (fonts, colors, borders, margins are LOCKED).
2. You must strictly assign headings to one of the PRE-EXISTING template heading styles:
   Available Heading Styles: {json.dumps(available_headings if available_headings else ["Default Heading"])}
3. Write high quality, authoritative, factual, well-organized content matching the user request.
4. If tabular data is relevant to the topic, structure it cleanly into headers and rows.

Output MUST be a valid JSON object with the following schema:
{{
  "title": "Document Title",
  "target_audience": "Audience Description",
  "sections": [
    {{
      "title": "Section Title",
      "heading_style": {json.dumps(default_heading) if default_heading else "null"},
      "paragraphs": ["Paragraph 1 text", "Paragraph 2 text"],
      "bullets": ["Bullet 1", "Bullet 2"],
      "image_query": "Descriptive search query for high-res illustration or null",
      "table_data": {{
        "title": "Table Title",
        "headers": ["Col 1", "Col 2"],
        "rows": [["Val 1", "Val 2"]]
      }}
    }}
  ],
  "conclusion": "Final concluding synthesis"
}}
"""

        user_message = f"""
User Topic / Request: {user_prompt}
Target Length: {target_pages or 'Comprehensive'} pages.
Custom Instructions: {custom_instructions or 'None'}
"""

        raw_json = await self.client.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=user_message,
            max_tokens=1500
        )

        try:
            plan = DocumentPlan.model_validate(raw_json)
        except Exception as e:
            logger.warning(f"Plan validation failed: {e}. Re-synthesizing plan.")
            raw_sections = raw_json.get("sections", []) if isinstance(raw_json, dict) else []
            parsed_sections = []
            for i, s in enumerate(raw_sections):
                t_data = None
                raw_tbl = s.get("table_data")
                if isinstance(raw_tbl, dict) and ("headers" in raw_tbl or "rows" in raw_tbl):
                    t_data = TableData(
                        headers=raw_tbl.get("headers", []),
                        rows=raw_tbl.get("rows", []),
                        title=raw_tbl.get("title")
                    )
                parsed_sections.append(
                    DocumentSection(
                        title=s.get("title", f"Section {i+1}"),
                        heading_style=s.get("heading_style") if (s.get("heading_style") in available_headings) else default_heading,
                        paragraphs=s.get("paragraphs", []),
                        bullets=s.get("bullets", []),
                        table_data=t_data,
                        image_query=s.get("image_query"),
                        image_caption=s.get("image_caption")
                    )
                )
            plan = DocumentPlan(
                title=raw_json.get("title", "Document Report") if isinstance(raw_json, dict) else "Document Report",
                target_audience=raw_json.get("target_audience", "General") if isinstance(raw_json, dict) else "General",
                sections=parsed_sections,
                conclusion=raw_json.get("conclusion", "") if isinstance(raw_json, dict) else ""
            )

        # Validate heading styles recursively
        def _fix_headings(sections: list[DocumentSection]):
            for sec in sections:
                if available_headings:
                    if sec.heading_style not in available_headings:
                        sec.heading_style = default_heading
                else:
                    sec.heading_style = None
                if sec.subsections:
                    _fix_headings(sec.subsections)

        _fix_headings(plan.sections)

        # Sourcing / Generating Images for Sections
        if include_images:
            from .image_service import image_service
            for idx, sec in enumerate(plan.sections):
                should_add_image = False
                if sec.image_query:
                    should_add_image = True
                elif "image" in user_prompt.lower() or "figure" in user_prompt.lower() or "diagram" in user_prompt.lower() or "picture" in user_prompt.lower() or "visual" in user_prompt.lower():
                    if idx in (1, 2):  # Add visual figures to core analytical sections
                        should_add_image = True
                        sec.image_query = f"{plan.title} {sec.title}"

                if should_add_image and sec.image_query:
                    try:
                        sec.image_path = await image_service.fetch_or_generate_image(
                            query_or_prompt=sec.image_query,
                            mode=image_mode
                        )
                        sec.image_caption = f"Figure {idx}: Visual Analysis for {sec.title}"
                    except Exception as e:
                        logger.warning(f"Failed to fetch image for section {sec.title}: {e}")

        # Apply Content Fitting Engine
        plan = ContentFitter.fit_document_plan(plan)
        return plan

    async def plan_presentation(
        self,
        user_prompt: str,
        template_spec: TemplateSpecification,
        target_slides: Optional[int] = None,
        custom_instructions: Optional[str] = None,
        include_images: bool = True,
        image_mode: str = "auto"
    ) -> PresentationPlan:
        """
        Creates a structured PresentationPlan strictly using the available layouts in template_spec.
        """
        available_layouts = template_spec.available_layout_names or ["Title Slide", "Title and Content"]

        system_prompt = f"""
You are Gemma 4, an advanced presentation architect AI.
Your task is to plan a structured slide deck.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. YOU DO NOT CONTROL THEME (master slides, colors, fonts, backgrounds are LOCKED).
2. Every slide must specify an EXACT layout name from the available layouts in the master:
   Available Layouts: {json.dumps(available_layouts)}
3. Keep bullet points punchy and concise (maximum 4-5 bullets per slide).
4. Slide 1 should typically use the Title layout.

Output MUST be a valid JSON object with the following schema:
{{
  "presentation_title": "Deck Title",
  "audience": "Audience Description",
  "slides": [
    {{
      "slide_number": 1,
      "title": "Slide Title",
      "subtitle": "Subtitle (if title slide)",
      "layout_name": "{available_layouts[0]}",
      "bullet_points": ["Bullet 1", "Bullet 2"],
      "body_paragraphs": [],
      "image_query": "Descriptive visual query or null",
      "table_data": {{
        "headers": ["Col 1", "Col 2"],
        "rows": [["Val 1", "Val 2"]]
      }},
      "speaker_notes": "Key speaking points"
    }}
  ]
}}
"""

        user_message = f"""
User Topic / Presentation Request: {user_prompt}
Target Slides: {target_slides or '5-8'} slides.
Custom Instructions: {custom_instructions or 'None'}
"""

        raw_json = await self.client.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=user_message,
            max_tokens=1000
        )

        try:
            plan = PresentationPlan.model_validate(raw_json)
        except Exception as e:
            logger.warning(f"Presentation plan validation failed: {e}. Re-synthesizing.")
            raw_slides = raw_json.get("slides", []) if isinstance(raw_json, dict) else []
            parsed_slides = []
            for i, s in enumerate(raw_slides):
                t_data = None
                raw_tbl = s.get("table_data")
                if isinstance(raw_tbl, dict) and ("headers" in raw_tbl or "rows" in raw_tbl):
                    t_data = TableData(
                        headers=raw_tbl.get("headers", []),
                        rows=raw_tbl.get("rows", [])
                    )
                parsed_slides.append(
                    SlidePlan(
                        slide_number=i+1,
                        title=s.get("title", f"Slide {i+1}"),
                        subtitle=s.get("subtitle"),
                        layout_name=s.get("layout_name", available_layouts[0]),
                        bullet_points=s.get("bullet_points", []),
                        body_paragraphs=s.get("body_paragraphs", []),
                        table_data=t_data,
                        image_query=s.get("image_query"),
                        image_path=s.get("image_path"),
                        speaker_notes=s.get("speaker_notes")
                    )
                )
            plan = PresentationPlan(
                presentation_title=raw_json.get("presentation_title", "Presentation Deck") if isinstance(raw_json, dict) else "Presentation Deck",
                audience=raw_json.get("audience", "General") if isinstance(raw_json, dict) else "General",
                slides=parsed_slides
            )

        # Validate layouts are within available layouts
        for slide in plan.slides:
            if slide.layout_name not in available_layouts:
                for l_name in available_layouts:
                    if "content" in l_name.lower() or "title" in l_name.lower():
                        slide.layout_name = l_name
                        break
                else:
                    slide.layout_name = available_layouts[0]

        # Sourcing / Generating Images for Presentation Slides
        if include_images:
            from .image_service import image_service
            for idx, slide in enumerate(plan.slides):
                should_add_image = False
                if slide.image_query:
                    should_add_image = True
                elif "image" in user_prompt.lower() or "picture" in user_prompt.lower() or "diagram" in user_prompt.lower() or "visual" in user_prompt.lower():
                    if idx in (1, 2, 3):  # Add visuals to content slides
                        should_add_image = True
                        slide.image_query = f"{plan.presentation_title} {slide.title}"

                if should_add_image and slide.image_query:
                    try:
                        slide.image_path = await image_service.fetch_or_generate_image(
                            query_or_prompt=slide.image_query,
                            mode=image_mode,
                            width=600,
                            height=400
                        )
                    except Exception as e:
                        logger.warning(f"Failed to fetch image for slide {slide.title}: {e}")

        # Apply Content Fitting Engine
        plan = ContentFitter.fit_presentation_plan(plan)
        return plan
