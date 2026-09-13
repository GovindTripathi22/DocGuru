from typing import List, Dict, Any, Optional
import copy
from pathlib import Path
import pptx
from pptx import Presentation
from pptx.slide import Slide
from pptx.shapes.placeholder import PlaceholderGraphicFrame
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN

from .style_lock import LockedPresentation, StyleLock, StyleLockViolationError
from ..models.generation import PresentationPlan, SlidePlan, TableData
from ..models.template_spec import TemplateSpecification

class PptxEngine:
    """
    Exact template-preserving PPTX engine.
    
    CRITICAL: Never creates a blank presentation from scratch.
    Always loads the original presentation file, preserves theme XML,
    slide masters, slide layouts, and background definitions, and
    creates new slides strictly by instantiating existing slide layouts.
    """

    def __init__(self):
        pass

    def load_template(self, file_path: str, spec: TemplateSpecification) -> LockedPresentation:
        """
        Load an existing PPTX presentation and wrap it with StyleLock.
        """
        prs = Presentation(file_path)
        return LockedPresentation(pptx_presentation=prs, template_path=file_path, spec=spec)

    def get_layout_by_name_or_closest(self, locked_prs: LockedPresentation, layout_name: str) -> Any:
        """
        Finds the exact slide layout by name, or selects the closest matching layout from the master.
        """
        return locked_prs.get_layout(layout_name)

    def add_slide_from_layout(
        self,
        locked_prs: LockedPresentation,
        layout_name: str,
        title: str,
        subtitle: Optional[str] = None,
        bullet_points: Optional[List[str]] = None,
        body_paragraphs: Optional[List[str]] = None,
        table_data: Optional[TableData] = None,
        image_path: Optional[str] = None,
        speaker_notes: Optional[str] = None
    ) -> Slide:
        """
        Instantiates a new slide using an EXISTING template layout.
        Populates placeholders while inheriting all master/layout typography, colors, and alignments.
        """
        StyleLock.assert_content_only({
            "layout_name": layout_name,
            "title": title,
            "subtitle": subtitle
        })

        prs = locked_prs.prs
        layout = self.get_layout_by_name_or_closest(locked_prs, layout_name)
        slide = prs.slides.add_slide(layout)

        # 1. Populate Title Placeholder
        title_placeholder = None
        for shape in slide.placeholders:
            if shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                title_placeholder = shape
                break
        
        if title_placeholder and title:
            title_placeholder.text = title

        # 2. Populate Subtitle Placeholder (if on Title Slide)
        subtitle_placeholder = None
        for shape in slide.placeholders:
            if shape.placeholder_format.type == PP_PLACEHOLDER.SUBTITLE:
                subtitle_placeholder = shape
                break
        
        if subtitle_placeholder and subtitle:
            subtitle_placeholder.text = subtitle

        # 3. Populate Content / Body Placeholder
        body_placeholder = None
        for shape in slide.placeholders:
            if shape.placeholder_format.type in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT):
                if shape != title_placeholder and shape != subtitle_placeholder:
                    body_placeholder = shape
                    break

        if body_placeholder:
            tf = body_placeholder.text_frame
            tf.word_wrap = True

            # If bullet points provided
            if bullet_points and len(bullet_points) > 0:
                tf.text = ""  # Clear default text
                for idx, bullet in enumerate(bullet_points):
                    if idx == 0:
                        p = tf.paragraphs[0]
                    else:
                        p = tf.add_paragraph()
                    p.text = bullet
                    p.level = 0  # Inherits level 0 bullet styling from slide master

            # If body paragraphs provided
            elif body_paragraphs and len(body_paragraphs) > 0:
                tf.text = ""
                for idx, para in enumerate(body_paragraphs):
                    if idx == 0:
                        p = tf.paragraphs[0]
                    else:
                        p = tf.add_paragraph()
                    p.text = para

        # 4. If image provided, insert image shape or picture placeholder
        if image_path and Path(image_path).exists():
            import pptx.util
            # Calculate dynamic coordinates proportional to slide dimensions
            slide_w = prs.slide_width.inches if hasattr(prs.slide_width, 'inches') else 13.333
            img_left = pptx.util.Inches(slide_w * 0.55)
            img_top = pptx.util.Inches(2.0)
            img_width = pptx.util.Inches(slide_w * 0.38)
            try:
                slide.shapes.add_picture(image_path, img_left, img_top, width=img_width)
            except Exception as e:
                pass

        # 5. If table data is provided, add table shape or fill table placeholder
        if table_data and (table_data.headers or table_data.rows):
            self._insert_table_on_slide(slide, table_data, prs)

        # 6. Add speaker notes if provided
        if speaker_notes:
            notes_slide = slide.notes_slide
            text_frame = notes_slide.notes_text_frame
            text_frame.text = speaker_notes

        return slide

    def _insert_table_on_slide(self, slide: Slide, table_data: TableData, prs: Presentation) -> Any:
        """
        Inserts or populates a table on the slide, respecting dimensions and inheriting slide master theme.
        """
        import pptx.util
        total_rows = len(table_data.rows) + (1 if table_data.headers else 0)
        total_cols = max(len(table_data.headers), max((len(r) for r in table_data.rows), default=1))
        
        if total_rows == 0 or total_cols == 0:
            return None

        # Dynamically scale table according to slide width/height
        slide_w = prs.slide_width.inches if hasattr(prs.slide_width, 'inches') else 13.333
        slide_h = prs.slide_height.inches if hasattr(prs.slide_height, 'inches') else 7.5

        left = pptx.util.Inches(slide_w * 0.08)
        top = pptx.util.Inches(slide_h * 0.28)
        width = pptx.util.Inches(slide_w * 0.84)
        height = pptx.util.Inches(min(slide_h * 0.58, 0.6 * total_rows + 0.5))

        table_shape = slide.shapes.add_table(total_rows, total_cols, left, top, width, height)
        table = table_shape.table

        current_row = 0
        if table_data.headers:
            for c_idx, h_val in enumerate(table_data.headers):
                if c_idx < total_cols:
                    cell = table.cell(0, c_idx)
                    cell.text = str(h_val)
            current_row = 1

        for r_idx, row in enumerate(table_data.rows):
            for c_idx, val in enumerate(row):
                if c_idx < total_cols:
                    cell = table.cell(current_row + r_idx, c_idx)
                    cell.text = str(val)

        return table_shape

    def duplicate_slide(self, locked_prs: LockedPresentation, source_slide_idx: int) -> Slide:
        """
        Deep-copies an existing slide (preserving all shapes, layout, and part relationships).
        """
        prs = locked_prs.prs
        if source_slide_idx < 0 or source_slide_idx >= len(prs.slides):
            raise ValueError(f"Slide index {source_slide_idx} out of range (0-{len(prs.slides)-1})")

        source_slide = prs.slides[source_slide_idx]
        new_slide = prs.slides.add_slide(source_slide.slide_layout)

        # Clear default placeholder shapes from new slide
        for shape in list(new_slide.shapes):
            sp = shape._element
            sp.getparent().remove(sp)

        # Deep-copy shapes from source slide
        for shape in source_slide.shapes:
            new_el = copy.deepcopy(shape._element)
            try:
                new_slide.shapes._spTree.insert_element_before(new_el, 'p:extLst')
            except Exception:
                new_slide.shapes._spTree.append(new_el)

        # Copy relationships (images, media, etc.)
        for rel_id, rel in source_slide.part.rels.items():
            if "notesSlide" not in rel.reltype:
                try:
                    new_slide.part.rels.add_relationship(rel.reltype, rel._target, rel.rId)
                except Exception:
                    pass

        return new_slide

    def clear_existing_slides_preserving_masters(self, prs: Presentation) -> None:
        """
        Removes all existing slide instances from the presentation,
        while strictly preserving all Slide Masters, Slide Layouts, and Themes.
        """
        # Remove slide parts using OpenXML element removal
        slide_count = len(prs.slides)
        for i in range(slide_count - 1, -1, -1):
            rId = prs.slides._sldIdLst[i].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[i]

    def generate_from_plan(
        self,
        locked_prs: LockedPresentation,
        plan: PresentationPlan,
        output_path: str
    ) -> str:
        """
        Generates a full presentation from a PresentationPlan using the locked template.
        Preserves all slide masters, themes, layouts, and colors.
        """
        prs = locked_prs.prs

        # Clear old slides while preserving masters/layouts
        self.clear_existing_slides_preserving_masters(prs)

        # Generate each slide from the plan
        for slide_plan in plan.slides:
            self.add_slide_from_layout(
                locked_prs=locked_prs,
                layout_name=slide_plan.layout_name,
                title=slide_plan.title,
                subtitle=slide_plan.subtitle,
                bullet_points=slide_plan.bullet_points,
                body_paragraphs=slide_plan.body_paragraphs,
                table_data=slide_plan.table_data,
                image_path=slide_plan.image_path,
                speaker_notes=slide_plan.speaker_notes
            )

        # Save output
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        prs.save(output_path)
        return output_path
