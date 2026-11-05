import copy
import difflib
import logging
import unicodedata
from pathlib import Path
from typing import Any, cast

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, RGBColor
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from ..config import settings
from ..errors import AppError
from ..models.generation import DocumentPlan, DocumentSection, ThemeOverrideRequest
from ..models.template_spec import TemplateSpecification
from .list_resolver import ListStyleResolver
from .style_lock import LockedTemplate

logger = logging.getLogger(__name__)


class DocxEngine:
    """
    Exact template-preserving DOCX engine conforming to DOCX-01..09 and VAL-01..05.
    Never creates blank documents from scratch; operates directly on locked templates.
    """

    def __init__(self):
        pass

    def load_template(self, file_path: str, spec: TemplateSpecification) -> LockedTemplate:
        doc = Document(file_path)
        return LockedTemplate(docx_document=doc, template_path=file_path, spec=spec)

    def clear_body_content_preserving_structure(self, doc: DocumentObject) -> list[Any]:
        """
        Clears existing body paragraphs and tables while preserving:
        - Section properties (w:sectPr at bottom of w:body)
        - Document styles, numbering, theme, headers/footers, margins
        Returns saved template table XMLs for structure cloning.
        """
        saved_table_xmls = []
        body_elem = doc._body._body

        for child in list(body_elem):
            if child.tag.endswith("tbl"):
                saved_table_xmls.append(copy.deepcopy(child))

        for child in list(body_elem):
            if not child.tag.endswith("sectPr"):
                body_elem.remove(child)

        return saved_table_xmls

    def insert_heading(
        self,
        locked_doc: LockedTemplate,
        text: str,
        requested_style: str | None = None,
        warnings: list[str] | None = None,
    ) -> Paragraph:
        doc = locked_doc.doc
        validated_style = (
            locked_doc.validate_style_allowed(requested_style) if requested_style else None
        )

        if validated_style:
            try:
                p = doc.add_paragraph(text, style=doc.styles[validated_style])
                self._apply_multilingual_properties(p, text, locked_doc)
                return p
            except (KeyError, TypeError, ValueError):
                logger.warning(
                    "Heading style %s could not be applied; using inherited body formatting.",
                    validated_style,
                )

        # Fallback to bold paragraph with default style
        if warnings is not None and requested_style:
            warnings.append(f"heading_style_fallback:{requested_style}")
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        self._apply_multilingual_properties(p, text, locked_doc)
        return p

    def insert_paragraph(
        self,
        locked_doc: LockedTemplate,
        text: str,
        requested_style: str | None = None,
        warnings: list[str] | None = None,
    ) -> Paragraph:
        doc = locked_doc.doc
        validated_style = (
            locked_doc.validate_style_allowed(requested_style) if requested_style else None
        )

        if validated_style:
            try:
                paragraph = doc.add_paragraph(text, style=doc.styles[validated_style])
                self._apply_multilingual_properties(paragraph, text, locked_doc)
                return paragraph
            except (KeyError, TypeError, ValueError):
                if warnings is not None:
                    warnings.append(f"paragraph_style_fallback:{validated_style}")

        paragraph = doc.add_paragraph(text)
        self._apply_multilingual_properties(paragraph, text, locked_doc)
        return paragraph

    def insert_bullet_point(
        self,
        locked_doc: LockedTemplate,
        text: str,
        level: int = 0,
        warnings: list[str] | None = None,
    ) -> Paragraph:
        doc = locked_doc.doc
        p = doc.add_paragraph()
        resolver = ListStyleResolver(doc)
        resolver.apply_bullet(p, text, level=level, warnings=warnings)
        self._apply_multilingual_properties(p, text, locked_doc)
        return p

    @staticmethod
    def _apply_multilingual_properties(
        paragraph: Paragraph,
        text: str,
        locked_doc: LockedTemplate,
    ) -> None:
        """Apply only template-derived script fonts and required RTL metadata."""
        fonts = locked_doc.spec.fonts
        is_rtl = any(unicodedata.bidirectional(char) in {"R", "AL", "AN"} for char in text)
        if is_rtl:
            ppr = paragraph._p.get_or_add_pPr()
            if ppr.find(qn("w:bidi")) is None:
                ppr.insert_element_before(
                    cast(Any, OxmlElement("w:bidi")),
                    "w:adjustRightInd",
                    "w:snapToGrid",
                    "w:spacing",
                    "w:ind",
                    "w:contextualSpacing",
                    "w:mirrorIndents",
                    "w:suppressOverlap",
                    "w:jc",
                    "w:textDirection",
                    "w:textAlignment",
                    "w:textboxTightWrap",
                    "w:outlineLvl",
                    "w:divId",
                    "w:cnfStyle",
                    "w:rPr",
                    "w:sectPr",
                    "w:pPrChange",
                )
            bidi = ppr.find(qn("w:bidi"))
            if bidi is not None:
                bidi.set(qn("w:val"), "1")

        for run in paragraph.runs:
            run_text = run.text
            has_east_asian = any(
                unicodedata.name(char, "").startswith(
                    ("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "BOPOMOFO", "YI ")
                )
                for char in run_text
            )
            has_complex_script = any(
                unicodedata.name(char, "").startswith(
                    (
                        "ARABIC",
                        "HEBREW",
                        "SYRIAC",
                        "THAANA",
                        "DEVANAGARI",
                        "BENGALI",
                        "GURMUKHI",
                        "GUJARATI",
                        "ORIYA",
                        "TAMIL",
                        "TELUGU",
                        "KANNADA",
                        "MALAYALAM",
                        "SINHALA",
                        "THAI",
                        "LAO",
                        "TIBETAN",
                        "MYANMAR",
                        "KHMER",
                    )
                )
                for char in run_text
            )
            has_rtl_run = is_rtl and any(
                unicodedata.bidirectional(char) in {"R", "AL", "AN"} for char in run_text
            )
            needs_script_font = (has_complex_script and fonts.complex_script_font) or (
                has_east_asian and fonts.east_asian_font
            )
            if not has_rtl_run and not needs_script_font:
                continue

            rpr = run._element.get_or_add_rPr()
            if has_rtl_run:
                if rpr.find(qn("w:rtl")) is None:
                    rpr.insert_element_before(
                        cast(Any, OxmlElement("w:rtl")),
                        "w:cs",
                        "w:em",
                        "w:lang",
                        "w:eastAsianLayout",
                        "w:specVanish",
                        "w:oMath",
                    )
                rtl = rpr.find(qn("w:rtl"))
                if rtl is not None:
                    rtl.set(qn("w:val"), "1")
            if needs_script_font:
                rfonts = rpr.get_or_add_rFonts()
                if has_complex_script and fonts.complex_script_font:
                    rfonts.set(qn("w:cs"), fonts.complex_script_font)
                if has_east_asian and fonts.east_asian_font:
                    rfonts.set(qn("w:eastAsia"), fonts.east_asian_font)

    def _apply_table_multilingual_properties(
        self, table: Table, locked_doc: LockedTemplate
    ) -> None:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    self._apply_multilingual_properties(paragraph, paragraph.text, locked_doc)

    def insert_cloned_table(
        self,
        locked_doc: LockedTemplate,
        headers: list[str],
        rows: list[list[str]],
        saved_table_xmls: list[Any] | None = None,
        source_table_index: int = 0,
    ) -> Table:
        doc = locked_doc.doc
        body_elem = doc._body._body
        col_count = max(len(headers), max((len(r) for r in rows), default=1))

        if saved_table_xmls and 0 <= source_table_index < len(saved_table_xmls):
            template_tbl_xml = copy.deepcopy(saved_table_xmls[source_table_index])
        elif len(doc.tables) > 0 and 0 <= source_table_index < len(doc.tables):
            template_tbl_xml = copy.deepcopy(doc.tables[source_table_index]._tbl)
        else:
            # Create standard table with fallback style
            table = doc.add_table(rows=len(rows) + (1 if headers else 0), cols=col_count)
            try:
                valid_style = locked_doc.get_valid_table_style()
                if valid_style and valid_style in doc.styles:
                    table.style = doc.styles[valid_style]
                elif "Table Grid" in doc.styles:
                    table.style = doc.styles["Table Grid"]
            except (KeyError, TypeError, ValueError):
                logger.warning(
                    "Table style could not be applied; the template table structure is retained."
                )

            curr_row = 0
            if headers:
                for c, h in enumerate(headers):
                    if c < col_count:
                        table.cell(0, c).text = str(h)
                curr_row = 1
            for r_idx, r_data in enumerate(rows):
                for c, val in enumerate(r_data):
                    if c < col_count:
                        table.cell(curr_row + r_idx, c).text = str(val)
            self._apply_table_multilingual_properties(table, locked_doc)
            return table

        # Cloned table XML handling
        sect_pr = None
        for child in list(body_elem):
            if child.tag.endswith("sectPr"):
                sect_pr = child
                break

        new_tbl_xml = copy.deepcopy(template_tbl_xml)
        if sect_pr is not None:
            sect_pr.addprevious(new_tbl_xml)
        else:
            body_elem.append(new_tbl_xml)

        xml_rows = list(new_tbl_xml.xpath(".//w:tr"))
        template_header_row_xml = copy.deepcopy(xml_rows[0]) if len(xml_rows) > 0 else None
        template_data_row_xml = (
            copy.deepcopy(xml_rows[1])
            if len(xml_rows) > 1
            else (copy.deepcopy(xml_rows[0]) if len(xml_rows) > 0 else None)
        )

        for r_elem in xml_rows:
            new_tbl_xml.remove(r_elem)

        # Synchronize tblGrid column definitions with col_count so table.cell indexing matches
        tbl_grids = list(new_tbl_xml.xpath(".//w:tblGrid"))
        if tbl_grids:
            grid_elem = tbl_grids[0]
            grid_cols = list(grid_elem.xpath(".//w:gridCol"))
            while len(grid_cols) < col_count and len(grid_cols) > 0:
                new_gc = copy.deepcopy(grid_cols[-1])
                grid_elem.append(new_gc)
                grid_cols.append(new_gc)
            while len(grid_cols) > col_count:
                grid_elem.remove(grid_cols.pop())

        def get_row_grid_span(tr_elem) -> int:
            tc_list = tr_elem.xpath(".//w:tc")
            span = 0
            for tc in tc_list:
                spans = tc.xpath(".//w:gridSpan/@w:val")
                span += int(spans[0]) if spans else 1
            return span

        # Header row
        if headers and template_header_row_xml is not None:
            h_row = copy.deepcopy(template_header_row_xml)
            while get_row_grid_span(h_row) < col_count:
                cells = list(h_row.xpath(".//w:tc"))
                if not cells:
                    break
                new_tc = copy.deepcopy(cells[-1])
                for gs in new_tc.xpath(".//w:gridSpan"):
                    gs.getparent().remove(gs)
                h_row.append(new_tc)
            while get_row_grid_span(h_row) > col_count:
                cells = list(h_row.xpath(".//w:tc"))
                if len(cells) <= 1:
                    break
                h_row.remove(cells[-1])
            new_tbl_xml.append(h_row)

        # Data rows
        for _ in rows:
            if template_data_row_xml is not None:
                d_row = copy.deepcopy(template_data_row_xml)
                while get_row_grid_span(d_row) < col_count:
                    cells = list(d_row.xpath(".//w:tc"))
                    if not cells:
                        break
                    new_tc = copy.deepcopy(cells[-1])
                    for gs in new_tc.xpath(".//w:gridSpan"):
                        gs.getparent().remove(gs)
                    d_row.append(new_tc)
                while get_row_grid_span(d_row) > col_count:
                    cells = list(d_row.xpath(".//w:tc"))
                    if len(cells) <= 1:
                        break
                    d_row.remove(cells[-1])
                new_tbl_xml.append(d_row)

        table = Table(new_tbl_xml, doc)
        row_offset = 1 if headers else 0
        if headers:
            for c, h in enumerate(headers):
                if c < len(table.rows[0].cells):
                    self._set_cell_text_preserve_formatting(table.rows[0].cells[c], str(h))

        for r_idx, row_data in enumerate(rows):
            target_r = row_offset + r_idx
            if target_r < len(table.rows):
                for c, val in enumerate(row_data):
                    if c < len(table.rows[target_r].cells):
                        self._set_cell_text_preserve_formatting(
                            table.rows[target_r].cells[c], str(val)
                        )

        self._apply_table_multilingual_properties(table, locked_doc)
        return table

    def _set_cell_text_preserve_formatting(self, cell: _Cell, text: str) -> None:
        if not cell.paragraphs:
            p = cell.add_paragraph()
            p.text = text
            return

        p = cell.paragraphs[0]
        if p.runs:
            p.runs[0].text = text
            for r in p.runs[1:]:
                r.text = ""
        else:
            p.text = text

        for extra_p in cell.paragraphs[1:]:
            extra_p.text = ""

    def insert_image(
        self,
        locked_doc: LockedTemplate,
        image_path: str,
        caption: str | None = None,
        max_width_inches: float | None = None,
    ) -> Any | None:
        doc = locked_doc.doc
        p_img = Path(image_path)
        if not p_img.exists():
            return None

        sec = doc.sections[-1]
        avail_width = sec.page_width - sec.left_margin - sec.right_margin
        width = (
            avail_width if max_width_inches is None else min(avail_width, Inches(max_width_inches))
        )

        p = doc.add_paragraph()
        run = p.add_run()
        run.add_picture(str(p_img), width=width)

        if caption:
            p_cap = doc.add_paragraph(caption)
            self._apply_multilingual_properties(p_cap, caption, locked_doc)
            try:
                p_cap.style = doc.styles["Caption"]
            except KeyError:
                p_cap.runs[0].italic = True
        return p

    def replace_placeholders_preserving_runs(
        self, doc: DocumentObject, mapping: dict[str, str]
    ) -> int:
        """
        Replaces {{key}} placeholders across body, tables, headers, and footers,
        preserving run formatting (bold, size, color) of the matched element.
        """
        replacements = 0

        def process_paragraph(p: Paragraph) -> None:
            nonlocal replacements
            text = p.text
            for key, val in mapping.items():
                token = f"{{{{{key}}}}}"
                if token in text:
                    # Check runs
                    matched_in_run = False
                    for r in p.runs:
                        if token in r.text:
                            r.text = r.text.replace(token, val)
                            replacements += 1
                            matched_in_run = True
                            break

                    # If token spanned across runs
                    if not matched_in_run and token in p.text and p.runs:
                        p.runs[0].text = p.text.replace(token, val)
                        for r in p.runs[1:]:
                            r.text = ""
                        replacements += 1

        for p in doc.paragraphs:
            process_paragraph(p)

        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        process_paragraph(p)

        for sec in doc.sections:
            for p in sec.header.paragraphs:
                process_paragraph(p)
            for p in sec.footer.paragraphs:
                process_paragraph(p)

        return replacements

    def mark_toc_fields_dirty(self, doc: DocumentObject) -> None:
        """Marks Table of Contents fields with w:dirty='true' so Word prompts for refresh (DOCX-03)."""
        body_elem = doc._body._body
        for fld in body_elem.xpath(".//w:fldChar[@w:fldCharType='begin']"):
            fld.set(qn("w:dirty"), "true")

    def apply_overrides(self, doc: DocumentObject, overrides: list[ThemeOverrideRequest]) -> None:
        """Applies validated user theme overrides safely without mutating arbitrary styles (DOCX-05)."""
        for ov in overrides:
            val = ov.value
            if ov.target == "heading_color":
                for s_name in doc.styles:
                    if "heading" in s_name.name.lower() or "title" in s_name.name.lower():
                        try:
                            if val != "auto":
                                r = int(val[:2], 16)
                                g = int(val[2:4], 16)
                                b = int(val[4:6], 16)
                                s_name.font.color.rgb = RGBColor(r, g, b)
                        except ValueError as exc:
                            raise AppError(
                                code="INVALID_THEME_OVERRIDE",
                                http_status=422,
                                message="Heading color override must be a validated six-digit hexadecimal value.",
                            ) from exc
            elif ov.target in ("table_border", "page_border"):
                # Apply to tblBorders
                for tbl in doc.tables:
                    tbl_pr = tbl._tbl.tblPr
                    tbl_borders = tbl_pr.xpath("./w:tblBorders")
                    if tbl_borders:
                        for b_elem in tbl_borders[0]:
                            b_elem.set(qn("w:color"), val)

    def apply_content_edits(
        self,
        locked_doc: LockedTemplate,
        plan: DocumentPlan,
        output_path: str,
        edit_action: str | None = None,
        target_heading: str | None = None,
        target_index: int | None = None,
    ) -> str:
        """
        Executes surgical outline-indexed content edits (DOCX-04).
        Resolves target heading index -> text -> fuzzy match.
        """
        doc = locked_doc.doc
        spec = locked_doc.spec
        outline = spec.document_outline if spec else []

        if not edit_action and plan.sections:
            edit_action = getattr(plan.sections[0], "action", None)
        if not target_heading and plan.sections:
            target_heading = getattr(plan.sections[0], "target_heading", None)

        # Target resolution
        resolved_p_idx = None
        candidates = []

        # Find actual heading paragraphs in document (excluding TOC styles)
        heading_indices: list[int] = []
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            style_name = (p.style.name if p.style else "").strip().lower()
            is_toc = style_name == "toc" or style_name.startswith("toc ")
            is_h = (style_name.startswith("heading") or style_name == "title") and not is_toc
            if is_h and len(text) < 120:
                heading_indices.append(i)

        action = edit_action or "append"
        if action not in ("append", "insert_after"):
            raise AppError(
                code="UNSUPPORTED_ACTION",
                http_status=422,
                message=f"Edit action '{action}' is not supported.",
                details={"supported_actions": ["append", "insert_after"]},
            )

        if target_index is not None:
            if 0 <= target_index < len(heading_indices):
                resolved_p_idx = heading_indices[target_index]
            else:
                raise AppError(
                    code="EDIT_TARGET_NOT_FOUND",
                    http_status=422,
                    message=f"Edit target index {target_index} is out of bounds (0..{len(heading_indices) - 1}).",
                    details={"candidates": outline[:5]},
                )

        if resolved_p_idx is None and target_heading:
            clean_target = target_heading.strip().lower()
            exact_matches = [
                i for i in heading_indices if clean_target == doc.paragraphs[i].text.strip().lower()
            ]
            if len(exact_matches) == 1:
                resolved_p_idx = exact_matches[0]
            elif len(exact_matches) > 1:
                raise AppError(
                    code="EDIT_TARGET_NOT_FOUND",
                    http_status=422,
                    message=f"Edit target heading '{target_heading}' is ambiguous ({len(exact_matches)} matches found). Please specify an outline index.",
                    details={"candidates": [doc.paragraphs[i].text.strip() for i in exact_matches]},
                )
            else:
                scored = []
                for i in heading_indices:
                    p_clean = doc.paragraphs[i].text.strip().lower()
                    ratio = difflib.SequenceMatcher(None, clean_target, p_clean).ratio()
                    if ratio >= 0.75:
                        scored.append((ratio, i, doc.paragraphs[i].text.strip()))
                scored.sort(reverse=True)
                if scored and (
                    len(scored) == 1 or (len(scored) > 1 and scored[0][0] - scored[1][0] > 0.15)
                ):
                    resolved_p_idx = scored[0][1]
                else:
                    candidates = [s[2] for s in scored[:5]]
                    raise AppError(
                        code="EDIT_TARGET_NOT_FOUND",
                        http_status=422,
                        message=f"Edit target heading '{target_heading}' could not be unambiguously resolved.",
                        details={"candidates": candidates or outline[:5]},
                    )

        if action == "insert_after" and resolved_p_idx is None:
            raise AppError(
                code="EDIT_TARGET_NOT_FOUND",
                http_status=422,
                message="Edit action 'insert_after' requires a valid target heading or outline index.",
                details={"candidates": outline[:5]},
            )

        saved_table_xmls = [copy.deepcopy(t._tbl) for t in doc.tables]

        if action == "append":
            # Append before final sectPr
            for s in plan.sections:
                self._render_section(locked_doc, s, saved_table_xmls)
        elif action == "insert_after":
            assert resolved_p_idx is not None
            # Find end of target section (next heading)
            end_idx = len(doc.paragraphs)
            for j in range(resolved_p_idx + 1, len(doc.paragraphs)):
                p = doc.paragraphs[j]
                if p.style and (
                    "heading" in p.style.name.lower() or "title" in p.style.name.lower()
                ):
                    end_idx = j
                    break

            if end_idx < len(doc.paragraphs):
                next_p = doc.paragraphs[end_idx]
                for s in plan.sections:
                    if s.title:
                        style_name = locked_doc.validate_style_allowed(s.heading_style)
                        style_obj = None
                        if style_name:
                            try:
                                style_obj = doc.styles[style_name]
                            except KeyError:
                                for st in doc.styles:
                                    if st.name.lower() == style_name.lower():
                                        style_obj = st
                                        break
                        if style_obj:
                            heading = next_p.insert_paragraph_before(s.title, style=style_obj)
                            self._apply_multilingual_properties(heading, s.title, locked_doc)
                        else:
                            hp = next_p.insert_paragraph_before(s.title)
                            if hp.runs:
                                hp.runs[0].bold = True
                            self._apply_multilingual_properties(hp, s.title, locked_doc)
                    for p_text in s.paragraphs:
                        paragraph = next_p.insert_paragraph_before(p_text)
                        self._apply_multilingual_properties(paragraph, p_text, locked_doc)
                    for b_text in s.bullets:
                        text = f"•  {b_text}"
                        paragraph = next_p.insert_paragraph_before(text)
                        self._apply_multilingual_properties(paragraph, text, locked_doc)
            else:
                for s in plan.sections:
                    self._render_section(locked_doc, s, saved_table_xmls)

        if plan.generation_mode == "demo":
            demo_note = "DEMO CONTENT — not AI generated. Treat this output as a scaffold and validate details before use."
            self.insert_paragraph(locked_doc, demo_note)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path

    def _render_section(
        self,
        locked_doc: LockedTemplate,
        section: DocumentSection,
        saved_table_xmls: list[Any],
        warnings: list[str] | None = None,
        source_numbers: dict[str, int] | None = None,
    ) -> None:
        if section.title:
            self.insert_heading(
                locked_doc,
                section.title,
                requested_style=section.heading_style or "Heading 1",
                warnings=warnings,
            )

        for p_text in section.paragraphs:
            self.insert_paragraph(locked_doc, p_text, warnings=warnings)

        for b_text in section.bullets:
            self.insert_bullet_point(locked_doc, b_text, warnings=warnings)

        if section.table_data and (section.table_data.headers or section.table_data.rows):
            self.insert_cloned_table(
                locked_doc,
                headers=section.table_data.headers,
                rows=section.table_data.rows,
                saved_table_xmls=saved_table_xmls,
                source_table_index=section.table_data.source_table_index,
            )

        if section.image_path:
            self.insert_image(
                locked_doc,
                section.image_path,
                caption=section.image_caption,
            )

        for sub in section.subsections:
            self._render_section(
                locked_doc,
                sub,
                saved_table_xmls,
                warnings=warnings,
                source_numbers=source_numbers,
            )

        valid_numbers = [
            source_numbers[item]
            for item in section.citations
            if source_numbers and item in source_numbers
        ]
        if valid_numbers:
            markers = " ".join(f"[{number}]" for number in valid_numbers)
            self.insert_paragraph(locked_doc, markers)

    def generate_from_plan(
        self,
        locked_doc: LockedTemplate,
        plan: DocumentPlan,
        output_path: str,
        template_mode: str = "auto",
        body_anchor_index: int | None = None,
        overrides: list[ThemeOverrideRequest] | None = None,
        edit_action: str | None = None,
        target_heading: str | None = None,
        target_index: int | None = None,
        warnings: list[str] | None = None,
    ) -> str:
        """
        Applies a DocumentPlan onto a locked template DOCX conforming to DOCX-01..09.
        """
        doc = locked_doc.doc

        if edit_action or getattr(plan, "edit_mode", None) == "edit":
            return self.apply_content_edits(
                locked_doc,
                plan,
                output_path,
                edit_action=edit_action,
                target_heading=target_heading,
                target_index=target_index,
            )

        # 1. Fill placeholders if present
        mapping = {
            "title": plan.title or "Document Title",
            "subtitle": "Generated Document",
            "author": "DocGuru Generator",
            "date": "2026",
            "abstract": plan.abstract or plan.conclusion or "Executive Summary",
        }
        replacements_count = self.replace_placeholders_preserving_runs(doc, mapping)

        # 2. Body inhabitation strategy
        is_structured = len(doc.sections) > 1 or len(doc.paragraphs) > 20 or replacements_count > 0

        def flatten_sections(sections: list[DocumentSection]) -> list[DocumentSection]:
            flattened = []
            for item in sections:
                flattened.append(item)
                flattened.extend(flatten_sections(item.subsections))
            return flattened

        cited_source_ids = {
            citation
            for section in flatten_sections(plan.sections)
            for citation in section.citations
        }
        referenced_sources = [
            source for source in plan.research_sources if source.id in cited_source_ids
        ]
        source_numbers = {
            source.id: index for index, source in enumerate(referenced_sources, start=1)
        }

        if template_mode == "fill":
            # Fill mode: keep existing structure, placeholders already replaced
            saved_table_xmls = [copy.deepcopy(t._tbl) for t in doc.tables]
            for s in plan.sections:
                self._render_section(
                    locked_doc,
                    s,
                    saved_table_xmls,
                    warnings=warnings,
                    source_numbers=source_numbers,
                )
        elif template_mode == "append" or (
            template_mode == "auto"
            and is_structured
            and replacements_count == 0
            and not body_anchor_index
        ):
            # Append mode: keep all existing body content, append new content before final sectPr
            saved_table_xmls = [copy.deepcopy(t._tbl) for t in doc.tables]
            for s in plan.sections:
                self._render_section(
                    locked_doc,
                    s,
                    saved_table_xmls,
                    warnings=warnings,
                    source_numbers=source_numbers,
                )
        else:
            # Clear or replace body after anchor
            saved_table_xmls = self.clear_body_content_preserving_structure(doc)

            # DOCX-01: Always render document title in create mode
            if plan.title and replacements_count == 0:
                self.insert_heading(
                    locked_doc, plan.title, requested_style="Title", warnings=warnings
                )

            # Render sections
            for idx, section in enumerate(plan.sections):
                self._render_section(
                    locked_doc,
                    section,
                    saved_table_xmls,
                    warnings=warnings,
                    source_numbers=source_numbers,
                )
                # D13 / DOCX-07: No forced page breaks between sections unless explicitly configured
                if settings.PAGE_BREAK_BETWEEN_SECTIONS and idx < len(plan.sections) - 1:
                    doc.add_page_break()

        # Shared footer content must appear in fill, append, and replace modes.
        if plan.conclusion:
            self.insert_heading(
                locked_doc, "Conclusion", requested_style="Heading 1", warnings=warnings
            )
            self.insert_paragraph(locked_doc, plan.conclusion)

        if referenced_sources:
            self.insert_heading(
                locked_doc, "References", requested_style="Heading 1", warnings=warnings
            )
            for source in referenced_sources:
                number = source_numbers[source.id]
                published = f" Published: {source.published_date}." if source.published_date else ""
                self.insert_paragraph(
                    locked_doc,
                    f"[{number}] {source.title}.{published} {source.url}",
                )

        if plan.generation_mode == "demo":
            self.insert_paragraph(
                locked_doc,
                "DEMO CONTENT — not AI generated. Treat this output as a scaffold and validate details before use.",
            )

        # 3. Apply user overrides if specified (DOCX-05)
        if overrides:
            self.apply_overrides(doc, overrides)

        # 4. Mark TOC dirty for Word refresh
        self.mark_toc_fields_dirty(doc)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path
