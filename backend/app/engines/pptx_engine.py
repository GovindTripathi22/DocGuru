import logging
from pathlib import Path
from typing import Any

import pptx
import pptx.util
from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.presentation import Presentation as PresentationObject
from pptx.slide import Slide

from ..models.generation import PresentationPlan, TableData
from ..models.template_spec import TemplateSpecification
from .style_lock import LockedPresentation

logger = logging.getLogger(__name__)


class PptxEngine:
    """
    Exact template-preserving PPTX engine conforming to PPTX-01..06.
    Never creates blank presentations from scratch.
    Inherits all master and layout structures, typography, and geometries.
    """

    def __init__(self):
        pass

    def load_template(self, file_path: str, spec: TemplateSpecification) -> LockedPresentation:
        prs = Presentation(file_path)
        return LockedPresentation(pptx_presentation=prs, template_path=file_path, spec=spec)

    def resolve_layout(
        self,
        locked_prs: LockedPresentation,
        layout_name: str | None,
        has_content: bool = True,
        warnings: list[str] | None = None,
    ) -> tuple[Any, str]:
        """
        Capability-based layout resolver (PPTX-01).
        Finds exact or closest layout capable of supporting the slide's content.
        Never selects a body-less layout if content is present.
        """
        prs = locked_prs.prs
        layouts = list(prs.slide_layouts)

        # 1. Try exact or case-insensitive match
        matched_layout = None
        matched_name = ""
        if layout_name:
            for candidate_layout in layouts:
                if candidate_layout.name.lower() == layout_name.lower():
                    matched_layout = candidate_layout
                    matched_name = candidate_layout.name
                    break

        # Check if matched layout has a body/content placeholder
        def has_body_placeholder(candidate_layout: Any) -> bool:
            for ph in candidate_layout.placeholders:
                if ph.placeholder_format.type in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT):
                    return True
            return False

        if matched_layout and has_content and not has_body_placeholder(matched_layout):
            # Layout cannot hold content (e.g. Title Only or Title Slide with bullets)
            if warnings is not None:
                warnings.append(f"layout_substituted:{matched_name}->Content")

            # Find first content-capable layout
            for candidate_layout in layouts:
                if has_body_placeholder(candidate_layout):
                    return candidate_layout, candidate_layout.name

        if matched_layout:
            return matched_layout, matched_name

        # Fallback: if has content, find first content-capable layout
        if has_content:
            for candidate_layout in layouts:
                if has_body_placeholder(candidate_layout):
                    if warnings is not None and layout_name:
                        warnings.append(
                            f"layout_substituted:{layout_name}->{candidate_layout.name}"
                        )
                    return candidate_layout, candidate_layout.name

        # Default fallback: layout 0 or 1
        chosen = layouts[1] if len(layouts) > 1 else layouts[0]
        return chosen, chosen.name

    def add_slide_from_layout(
        self,
        locked_prs: LockedPresentation,
        layout_name: str,
        title: str,
        subtitle: str | None = None,
        bullet_points: list[str] | None = None,
        body_paragraphs: list[str] | None = None,
        table_data: TableData | None = None,
        image_path: str | None = None,
        speaker_notes: str | None = None,
        columns: list[list[str]] | None = None,
        warnings: list[str] | None = None,
    ) -> Slide:
        """
        Instantiates a new slide using an existing template layout (PPTX-01..03).
        Renders title, subtitle, body paragraphs, and bullets without silent loss.
        """
        prs = locked_prs.prs
        has_content = bool(bullet_points or body_paragraphs or table_data or columns)
        layout, _ = self.resolve_layout(
            locked_prs, layout_name, has_content=has_content, warnings=warnings
        )
        slide = prs.slides.add_slide(layout)

        # 1. Populate Title Placeholder
        title_placeholder = None
        for shape in slide.placeholders:
            if shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                title_placeholder = shape
                break

        if title_placeholder and title:
            title_placeholder.text = title

        # 2. Populate Subtitle Placeholder
        subtitle_placeholder = None
        for shape in slide.placeholders:
            if shape.placeholder_format.type == PP_PLACEHOLDER.SUBTITLE:
                subtitle_placeholder = shape
                break

        if subtitle_placeholder and subtitle:
            subtitle_placeholder.text = subtitle

        # 3. Populate Content / Body Placeholders
        body_placeholders = []
        picture_placeholders = []
        table_placeholders = []

        for shape in slide.placeholders:
            if shape == title_placeholder or shape == subtitle_placeholder:
                continue
            ph_type = shape.placeholder_format.type
            if ph_type in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT):
                body_placeholders.append(shape)
            elif ph_type == PP_PLACEHOLDER.PICTURE:
                picture_placeholders.append(shape)
            elif ph_type == PP_PLACEHOLDER.TABLE:
                table_placeholders.append(shape)

        # Handle column content for two-content layouts
        if columns and len(body_placeholders) >= 2:
            for c_idx, col_items in enumerate(columns[: len(body_placeholders)]):
                tf = body_placeholders[c_idx].text_frame
                tf.word_wrap = True
                tf.text = ""
                for idx, item in enumerate(col_items):
                    p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                    p.text = item
        elif body_placeholders:
            # Main body placeholder: render paragraphs AND bullets (PPTX-02)
            main_ph = body_placeholders[0]
            tf = main_ph.text_frame
            tf.word_wrap = True
            tf.text = ""

            first_p = True
            if body_paragraphs:
                for para in body_paragraphs:
                    p = tf.paragraphs[0] if first_p else tf.add_paragraph()
                    p.text = para
                    first_p = False

            if bullet_points:
                for bullet in bullet_points:
                    p = tf.paragraphs[0] if first_p else tf.add_paragraph()
                    p.text = bullet
                    p.level = 0
                    first_p = False

        elif has_content and not subtitle:
            # If no body placeholder was present on layout, create non-overlapping text shape
            slide_w = prs.slide_width.inches if hasattr(prs.slide_width, "inches") else 13.333
            slide_h = prs.slide_height.inches if hasattr(prs.slide_height, "inches") else 7.5
            tb = slide.shapes.add_textbox(
                pptx.util.Inches(slide_w * 0.1),
                pptx.util.Inches(slide_h * 0.35),
                pptx.util.Inches(slide_w * 0.8),
                pptx.util.Inches(slide_h * 0.5),
            )
            tf = tb.text_frame
            tf.word_wrap = True
            all_items = (body_paragraphs or []) + (bullet_points or [])
            for idx, item in enumerate(all_items):
                p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                p.text = item

        # 4. Handle Picture (PPTX-03)
        if image_path and Path(image_path).exists():
            slide_w = prs.slide_width.inches if hasattr(prs.slide_width, "inches") else 13.333
            slide_h = prs.slide_height.inches if hasattr(prs.slide_height, "inches") else 7.5

            if picture_placeholders:
                try:
                    picture_placeholders[0].insert_picture(image_path)
                except (OSError, TypeError, ValueError) as e:
                    logger.warning("Picture placeholder insertion failed: %s", e)
            else:
                # Place picture on right side without colliding with body
                img_left = pptx.util.Inches(slide_w * 0.6)
                img_top = pptx.util.Inches(slide_h * 0.35)
                img_w = pptx.util.Inches(slide_w * 0.32)
                try:
                    slide.shapes.add_picture(image_path, img_left, img_top, width=img_w)
                except (OSError, TypeError, ValueError) as e:
                    logger.warning("Slide image insertion failed: %s", e)
                    if warnings is not None:
                        warnings.append(f"image_insertion_failed:{e}")

        # 5. Handle Table (PPTX-03)
        if table_data and (table_data.headers or table_data.rows):
            if table_placeholders:
                try:
                    self._insert_table_on_slide(
                        slide, table_data, prs, target_ph=table_placeholders[0]
                    )
                except (AttributeError, IndexError, TypeError, ValueError) as e:
                    logger.warning("Table placeholder insertion failed: %s", e)
            else:
                self._insert_table_on_slide(slide, table_data, prs)

        # 6. Speaker notes
        if speaker_notes:
            notes_slide = slide.notes_slide
            tf_notes = notes_slide.notes_text_frame
            tf_notes.text = speaker_notes

        # Keep non-content placeholders so layout/master footers and slide numbers survive.
        structural_placeholder_types = {
            PP_PLACEHOLDER.CENTER_TITLE,
            PP_PLACEHOLDER.SUBTITLE,
            PP_PLACEHOLDER.DATE,
            PP_PLACEHOLDER.HEADER,
            PP_PLACEHOLDER.FOOTER,
            PP_PLACEHOLDER.SLIDE_NUMBER,
        }
        # 7. Clean unused empty content placeholders (PPTX-02: never delete title)
        for ph in list(slide.placeholders):
            if ph == title_placeholder:
                continue
            if ph.placeholder_format.type in structural_placeholder_types:
                continue
            if hasattr(ph, "text_frame") and not ph.text_frame.text.strip():
                sp = ph._element
                sp.getparent().remove(sp)

        return slide

    def _insert_table_on_slide(
        self,
        slide: Slide,
        table_data: TableData,
        prs: PresentationObject,
        target_ph: Any | None = None,
    ) -> Any:
        total_rows = len(table_data.rows) + (1 if table_data.headers else 0)
        total_cols = max(len(table_data.headers), max((len(r) for r in table_data.rows), default=1))

        if total_rows == 0 or total_cols == 0:
            return None

        slide_w = prs.slide_width.inches if prs.slide_width is not None else 13.333
        slide_h = prs.slide_height.inches if prs.slide_height is not None else 7.5

        if target_ph is not None:
            left = target_ph.left
            top = target_ph.top
            width = target_ph.width
            height = target_ph.height
        else:
            left = pptx.util.Inches(slide_w * 0.08)
            top = pptx.util.Inches(slide_h * 0.35)
            width = pptx.util.Inches(slide_w * 0.84)
            height = pptx.util.Inches(min(slide_h * 0.55, 0.4 * total_rows + 0.5))

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

    def clear_existing_slides_preserving_masters(self, prs: PresentationObject) -> None:
        """
        Removes existing slide instances while strictly preserving slide masters,
        layouts, and presentation themes. Cleans section list references to prevent repair prompts (PPTX-05).
        """
        slide_count = len(prs.slides)
        for i in range(slide_count - 1, -1, -1):
            rId = prs.slides._sldIdLst[i].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[i]

        # The p14 namespace is not registered in python-pptx's XPath map, so use
        # the local element names and remove only extension lists that reference
        # slides being deleted.
        pres_elm = prs._element
        for list_name in ("sectionLst", "custShowLst"):
            for slide_list in pres_elm.xpath(f".//*[local-name()='{list_name}']"):
                parent = slide_list.getparent()
                if parent is not None:
                    parent.remove(slide_list)

    def generate_from_plan(
        self,
        locked_prs: LockedPresentation,
        plan: PresentationPlan,
        output_path: str,
        keep_existing_slides: bool = False,
        warnings: list[str] | None = None,
    ) -> str:
        """
        Generates presentation slides conforming to PresentationPlan (PPTX-01..06).
        """
        prs = locked_prs.prs

        if not keep_existing_slides:
            self.clear_existing_slides_preserving_masters(prs)

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
                speaker_notes=slide_plan.speaker_notes,
                columns=slide_plan.columns,
                warnings=warnings,
            )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        prs.save(output_path)
        return output_path
