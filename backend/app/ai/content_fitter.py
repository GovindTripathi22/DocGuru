import re
from math import ceil, floor

from ..models.generation import (
    DocumentPlan,
    DocumentSection,
    PresentationPlan,
    SlidePlan,
)
from ..models.template_spec import TemplateSpecification


class ContentFitter:
    """
    Content Fitting Engine (§17).

    If content is too lengthy for a single section or slide:
    NEVER modify the template fonts, margins, or sizes.
    INSTEAD:
    1. Shorten verbose sentences.
    2. Convert paragraphs into bullet points.
    3. Split content across multiple slides / pages using the SAME existing layout.
    """

    MAX_BULLETS_PER_SLIDE = 5
    MAX_WORDS_PER_BULLET = 25
    MAX_PARAGRAPH_WORDS = 150
    SENTENCE_BOUNDARY = re.compile(r"[.!?][\"')\]]*[ \t\r\n]+")
    CLAUSE_BOUNDARY = re.compile(r"[,;:—–][\"')\]]*[ \t\r\n]+")

    @classmethod
    def _split_paragraph_at_sentences(cls, paragraph: str) -> list[str]:
        """Split oversized text at sentence ends while preserving every character."""
        word_spans = list(re.finditer(r"\S+", paragraph))
        if len(word_spans) <= cls.MAX_PARAGRAPH_WORDS:
            return [paragraph]

        chunks: list[str] = []
        segment_start = 0
        first_word = 0
        while len(word_spans) - first_word > cls.MAX_PARAGRAPH_WORDS:
            limit = word_spans[first_word + cls.MAX_PARAGRAPH_WORDS - 1].end()
            search_limit = word_spans[first_word + cls.MAX_PARAGRAPH_WORDS].start()
            boundaries = list(cls.SENTENCE_BOUNDARY.finditer(paragraph, segment_start, search_limit))
            if boundaries:
                cut = boundaries[-1].end()
            else:
                clause_boundaries = list(
                    cls.CLAUSE_BOUNDARY.finditer(paragraph, segment_start, search_limit)
                )
                cut = clause_boundaries[-1].end() if clause_boundaries else limit
            chunks.append(paragraph[segment_start:cut])
            segment_start = cut
            while first_word < len(word_spans) and word_spans[first_word].end() <= cut:
                first_word += 1
        if segment_start < len(paragraph):
            chunks.append(paragraph[segment_start:])
        return chunks

    @classmethod
    def _slide_bullet_capacity(
        cls, slide: SlidePlan, template_spec: TemplateSpecification | None
    ) -> tuple[int, int]:
        """Estimate bullet capacity from the selected layout's body placeholder geometry."""
        fallback = (cls.MAX_BULLETS_PER_SLIDE, 90)
        if template_spec is None or not template_spec.layouts:
            return fallback

        layout = next(
            (
                item
                for item in template_spec.layouts
                if item.name.casefold() == slide.layout_name.casefold()
            ),
            None,
        )
        if layout is None:
            return fallback
        body = next(
            (item for item in layout.placeholders if item.type.upper() in {"BODY", "OBJECT"}),
            None,
        )
        if body is None or body.width_inches <= 0 or body.height_inches <= 0:
            return fallback

        chars_per_line = max(24, int(body.width_inches * 11))
        line_capacity = max(1, floor(max(0.25, body.height_inches - 0.2) / 0.28))
        return min(cls.MAX_BULLETS_PER_SLIDE, line_capacity), chars_per_line

    @classmethod
    def fit_presentation_plan(
        cls,
        plan: PresentationPlan,
        template_spec: TemplateSpecification | None = None,
    ) -> PresentationPlan:
        """Split overflow using body placeholder capacity while retaining every item."""
        fitted_slides: list[SlidePlan] = []
        slide_num = 1

        for slide in plan.slides:
            bullets = slide.bullet_points or []
            bullet_capacity, chars_per_line = cls._slide_bullet_capacity(slide, template_spec)
            line_capacity = bullet_capacity
            chunks: list[list[str]] = []
            current_chunk: list[str] = []
            used_lines = 0

            for bullet in bullets:
                bullet_lines = max(1, ceil(len(bullet.strip()) / chars_per_line))
                if current_chunk and (
                    len(current_chunk) >= bullet_capacity
                    or used_lines + bullet_lines > line_capacity
                ):
                    chunks.append(current_chunk)
                    current_chunk = []
                    used_lines = 0
                current_chunk.append(bullet)
                used_lines += min(bullet_lines, line_capacity)
            if current_chunk:
                chunks.append(current_chunk)

            if len(chunks) > 1:
                for idx, chunk in enumerate(chunks):
                    fitted_slides.append(
                        SlidePlan(
                            slide_number=slide_num,
                            title=slide.title if idx == 0 else f"{slide.title} (Cont.)",
                            subtitle=slide.subtitle if idx == 0 else None,
                            layout_name=slide.layout_name,
                            bullet_points=chunk,
                            body_paragraphs=slide.body_paragraphs if idx == 0 else [],
                            table_data=slide.table_data if idx == 0 else None,
                            image_query=slide.image_query if idx == 0 else None,
                            image_path=slide.image_path if idx == 0 else None,
                            speaker_notes=slide.speaker_notes,
                        )
                    )
                    slide_num += 1
            else:
                slide.slide_number = slide_num
                fitted_slides.append(slide)
                slide_num += 1

        plan.slides = fitted_slides
        return plan

    @classmethod
    def fit_document_plan(cls, plan: DocumentPlan) -> DocumentPlan:
        """
        Ensures document sections are well-structured without overwhelming single blocks.
        """

        def _fit_section(sec: DocumentSection) -> DocumentSection:
            fitted_paras = []
            for p in sec.paragraphs:
                chunks = cls._split_paragraph_at_sentences(p)
                fitted_paras.extend(chunks)
                for chunk in chunks[:-1]:
                    ending = chunk.rstrip()
                    if re.search(r"[.!?][\"')\]]*$", ending):
                        continue
                    warning = (
                        "long_sentence_split_at_clause_boundary"
                        if re.search(r"[,;:—–][\"')\]]*$", ending)
                        else "long_sentence_split_at_word_boundary"
                    )
                    if warning not in plan.warnings:
                        plan.warnings.append(warning)
            sec.paragraphs = fitted_paras
            if sec.subsections:
                sec.subsections = [_fit_section(sub) for sub in sec.subsections]
            return sec

        plan.sections = [_fit_section(sec) for sec in plan.sections]
        return plan
