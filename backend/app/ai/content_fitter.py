from typing import List, Dict, Any
from ..models.generation import DocumentPlan, DocumentSection, PresentationPlan, SlidePlan

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

    @classmethod
    def fit_presentation_plan(cls, plan: PresentationPlan) -> PresentationPlan:
        """
        Splits overloaded slides into multiple slides using the identical layout.
        """
        fitted_slides: List[SlidePlan] = []
        slide_num = 1

        for slide in plan.slides:
            bullets = slide.bullet_points or []
            
            # If slide has more than max bullets, split into Part 1, Part 2
            if len(bullets) > cls.MAX_BULLETS_PER_SLIDE:
                chunks = [
                    bullets[i:i + cls.MAX_BULLETS_PER_SLIDE]
                    for i in range(0, len(bullets), cls.MAX_BULLETS_PER_SLIDE)
                ]
                for idx, chunk in enumerate(chunks):
                    sub_title = slide.title if idx == 0 else f"{slide.title} (Cont.)"
                    fitted_slides.append(SlidePlan(
                        slide_number=slide_num,
                        title=sub_title,
                        subtitle=slide.subtitle if idx == 0 else None,
                        layout_name=slide.layout_name,
                        bullet_points=chunk,
                        body_paragraphs=[],
                        table_data=slide.table_data if idx == 0 else None,
                        image_query=slide.image_query if idx == 0 else None,
                        image_path=slide.image_path if idx == 0 else None,
                        speaker_notes=slide.speaker_notes
                    ))
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
                current = p
                words = current.split()
                if len(words) > cls.MAX_PARAGRAPH_WORDS:
                    while len(words) > cls.MAX_PARAGRAPH_WORDS:
                        fitted_paras.append(" ".join(words[:cls.MAX_PARAGRAPH_WORDS]))
                        words = words[cls.MAX_PARAGRAPH_WORDS:]
                    if words:
                        fitted_paras.append(" ".join(words))
                else:
                    fitted_paras.append(p)
            sec.paragraphs = fitted_paras
            if sec.subsections:
                sec.subsections = [_fit_section(sub) for sub in sec.subsections]
            return sec

        plan.sections = [_fit_section(sec) for sec in plan.sections]
        return plan
