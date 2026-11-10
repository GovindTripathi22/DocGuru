import copy
import difflib
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, cast

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from ..analyzer.docx_analyzer import is_instruction_or_rule_paragraph
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

    def _resolve_style(self, doc: DocumentObject, style_name: str) -> Any:
        try:
            return doc.styles[style_name]
        except (KeyError, TypeError):
            clean_id = style_name.replace(" ", "").lower()
            for s in doc.styles:
                if s.name.lower() == style_name.lower():
                    return s
                if hasattr(s, "style_id") and s.style_id and s.style_id.lower() == clean_id:
                    return s
        return None

    @staticmethod
    def _apply_typography_rules(
        paragraph: Paragraph,
        role: str,
        locked_doc: LockedTemplate,
    ) -> None:
        spec = locked_doc.spec
        if not spec or not getattr(spec, "parsed_typography_rules", None):
            return
        rules = spec.parsed_typography_rules.get(role)
        if not rules:
            return

        font_name = rules.get("font_name")
        size_pt = rules.get("size_pt")
        bold = rules.get("bold")
        line_spacing = rules.get("line_spacing")
        space_before_pt = rules.get("spacing_before_pt")
        space_after_pt = rules.get("spacing_after_pt")
        alignment = rules.get("alignment")

        if line_spacing is not None:
            paragraph.paragraph_format.line_spacing = line_spacing
        if space_before_pt is not None:
            paragraph.paragraph_format.space_before = Pt(space_before_pt)
        if space_after_pt is not None:
            paragraph.paragraph_format.space_after = Pt(space_after_pt)

        if alignment:
            align_lower = alignment.lower()
            if "center" in align_lower:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif "justify" in align_lower:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            elif "right" in align_lower:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            elif "left" in align_lower:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

        for r in paragraph.runs:
            if font_name:
                r.font.name = font_name
            if size_pt is not None:
                r.font.size = Pt(size_pt)
            if bold is not None:
                r.bold = bold
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

        role = "heading1"
        if requested_style:
            req_lower = requested_style.lower()
            if "heading 2" in req_lower or "sub" in req_lower:
                role = "heading2"
            elif "heading 3" in req_lower:
                role = "heading3"
            elif "title" in req_lower:
                role = "heading1"

        spec_rules = getattr(locked_doc.spec, "parsed_typography_rules", {})
        if role == "heading1" and spec_rules.get("heading1", {}).get("case") == "uppercase":
            text = text.upper()

        if validated_style:
            st = self._resolve_style(doc, validated_style)
            if st is not None:
                try:
                    p = doc.add_paragraph(text, style=st)
                    self._apply_typography_rules(p, role, locked_doc)
                    self._apply_multilingual_properties(p, text, locked_doc)
                    return p
                except (KeyError, TypeError, ValueError):
                    pass
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
        self._apply_typography_rules(p, role, locked_doc)
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
            st = self._resolve_style(doc, validated_style)
            if st is not None:
                try:
                    paragraph = doc.add_paragraph(text, style=st)
                    self._apply_typography_rules(paragraph, "body", locked_doc)
                    self._apply_multilingual_properties(paragraph, text, locked_doc)
                    return paragraph
                except (KeyError, TypeError, ValueError):
                    pass
            if warnings is not None:
                warnings.append(f"paragraph_style_fallback:{validated_style}")

        paragraph = doc.add_paragraph(text)
        self._apply_typography_rules(paragraph, "body", locked_doc)
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
        self._apply_typography_rules(p, "body", locked_doc)
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
                if valid_style and valid_style in locked_doc.valid_doc_table_styles:
                    table.style = doc.styles[valid_style]
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
            self._apply_typography_rules(p_cap, "caption", locked_doc)
            self._apply_multilingual_properties(p_cap, caption, locked_doc)
            if "Caption" in locked_doc.valid_doc_paragraph_styles:
                try:
                    p_cap.style = doc.styles["Caption"]
                except (KeyError, TypeError, ValueError):
                    if p_cap.runs:
                        p_cap.runs[0].italic = True
            elif p_cap.runs:
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
            if sec.header and not sec.header.is_linked_to_previous:
                for p in sec.header.paragraphs:
                    if "{{" in p.text:
                        process_paragraph(p)
            if sec.footer and not sec.footer.is_linked_to_previous:
                for p in sec.footer.paragraphs:
                    if "{{" in p.text:
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

    @staticmethod
    def _set_paragraph_text_preserving_runs(p: Paragraph, new_text: str) -> None:
        if p.runs:
            p.runs[0].text = new_text
            for r in p.runs[1:]:
                if not r._element.xpath(".//w:br[@w:type='page']"):
                    r.text = ""
        else:
            p.text = new_text

    @staticmethod
    def _strip_or_remove_instruction_paragraph(p: Paragraph) -> None:
        elem = p._p
        has_sectPr = bool(elem.xpath("./w:pPr/w:sectPr"))
        has_page_break = bool(elem.xpath(".//w:br[@w:type='page']"))
        if has_sectPr:
            for sub in list(elem):
                if not sub.tag.endswith("pPr"):
                    elem.remove(sub)
        elif has_page_break:
            for r in p.runs:
                r.text = ""
        else:
            parent = elem.getparent()
            if parent is not None:
                try:
                    parent.remove(elem)
                    return
                except ValueError:
                    pass
            p.text = ""

    def _inhabit_institutional_front_matter(
        self,
        doc: DocumentObject,
        plan: DocumentPlan,
        author: str,
        guide: str,
        department: str | None = None,
        institution: str | None = None,
        academic_year: str | None = None,
        body_anchor_idx: int | None = None,
        anchor_elem: Any = None,
        warnings: list[str] | None = None,
    ) -> int:
        title = plan.title or "Document Title"
        replacements = 0

        title_exact = {
            "t i t l e",
            "title",
            "title of seminar/project",
            "title of seminar/project.",
            "[seminar topic]",
            "[title]",
            "project title",
            "seminar topic",
            "<title>",
            "topic of seminar",
            "name of topic",
        }
        protected_headings = {
            "SEMINAR REPORT",
            "PROJECT REPORT",
            "CERTIFICATE",
            "DECLARATION",
            "ACKNOWLEDGEMENT",
            "ACKNOWLEDGEMENTS",
            "ABSTRACT",
            "TABLE OF CONTENT",
            "TABLE OF CONTENTS",
            "INDEX",
            "CONTENTS",
        }

        def process_para(p: Paragraph, allow_remove: bool = False) -> None:
            nonlocal replacements
            t_raw = p.text
            t_strip = t_raw.strip()
            if not t_strip:
                return
            t_lower = t_strip.lower()
            t_upper = " ".join(t_strip.upper().split())

            if t_lower in title_exact:
                self._set_paragraph_text_preserving_runs(p, title)
                replacements += 1
                return

            updated = t_raw
            did_replace = False

            if "title of seminar" in t_lower or "title of project" in t_lower:
                updated = re.sub(
                    r'["\u201c\u2018\u00ab\u201d\u2019\u00bb]?Title of (?:Seminar|Project)(?:/[^\s"\u201d\u2019\u00bb\n.]+)?\.?["\u201c\u2018\u00ab\u201d\u2019\u00bb]?',
                    f'"{title}"',
                    updated,
                    flags=re.IGNORECASE,
                )
                did_replace = True

            for token in ("[Seminar Topic]", "[seminar topic]", "[Project Title]", "[Title]", "<Title>"):
                if token in updated:
                    updated = updated.replace(token, title)
                    did_replace = True

            if "submitted by name of student" in t_lower:
                updated = re.sub(
                    r"Submitted\s+By\s+Name\s+of\s+Student",
                    f"Submitted By {author}",
                    updated,
                    flags=re.IGNORECASE,
                )
                did_replace = True
            elif t_lower in ("name of student", "student name", "[student name]", "<student name>"):
                updated = author
                did_replace = True
            elif "name of student" in t_lower:
                updated = re.sub(r"Name\s+of\s+Student", author, updated, flags=re.IGNORECASE)
                did_replace = True

            if "name of guide" in t_lower:
                updated = re.sub(r"Name\s+of\s+Guide", guide, updated, flags=re.IGNORECASE)
                did_replace = True
            if "dr./prof./guide name" in t_lower:
                updated = re.sub(r"Dr\./Prof\./Guide\s+Name", guide, updated, flags=re.IGNORECASE)
                did_replace = True
            if "prof. name" in t_lower:
                updated = re.sub(r"Prof\.\s*Name", guide, updated, flags=re.IGNORECASE)
                did_replace = True
            if "[guide name]" in t_lower or "<guide name>" in t_lower:
                updated = re.sub(r"[\[<]Guide\s+Name[\]>]", guide, updated, flags=re.IGNORECASE)
                did_replace = True

            if department:
                if "department of [department]" in t_lower or "[department]" in t_lower:
                    updated = re.sub(r"\[Department\]", department, updated, flags=re.IGNORECASE)
                    did_replace = True
                elif re.search(r"department\s+of\s+name", t_lower):
                    updated = re.sub(r"Department\s+of\s+Name", department, updated, flags=re.IGNORECASE)
                    did_replace = True

            if institution:
                if "name of college" in t_lower or "name of institute" in t_lower or "[institution]" in t_lower:
                    updated = re.sub(
                        r"(?:Name\s+of\s+(?:College|Institute|Institution)|\[Institution\])",
                        institution,
                        updated,
                        flags=re.IGNORECASE,
                    )
                    did_replace = True

            if academic_year and re.search(r"20\d{2}\s*[-–]\s*(?:20)?\d{2}", updated):
                updated = re.sub(r"20\d{2}\s*[-–]\s*(?:20)?\d{2}", academic_year, updated)
                did_replace = True

            if did_replace and updated != t_raw:
                self._set_paragraph_text_preserving_runs(p, updated)
                replacements += 1
                return

            if (
                allow_remove
                and t_upper not in protected_headings
                and is_instruction_or_rule_paragraph(t_strip)
            ):
                self._strip_or_remove_instruction_paragraph(p)

        limit = body_anchor_idx if body_anchor_idx is not None else min(100, len(doc.paragraphs))
        for p in list(doc.paragraphs[:limit]):
            if anchor_elem is not None and p._p == anchor_elem:
                break
            process_para(p, allow_remove=True)

        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in list(cell.paragraphs):
                        process_para(p, allow_remove=False)

        return replacements

    def _synthesize_abstract_text(self, plan: DocumentPlan) -> str:
        if plan.abstract and len(plan.abstract.strip()) > 30:
            return plan.abstract.strip()
        parts: list[str] = []
        if plan.sections and plan.sections[0].paragraphs:
            parts.append(plan.sections[0].paragraphs[0].strip())
        if len(plan.sections) > 1 and plan.sections[1].paragraphs:
            first_sentence = plan.sections[1].paragraphs[0].split(". ")[0].strip()
            if first_sentence:
                parts.append(first_sentence.rstrip(".") + ".")
        if plan.conclusion:
            parts.append(plan.conclusion.strip())
        if parts:
            return " ".join(parts)
        return f"This report presents an in-depth technical investigation and architectural analysis of {plan.title}."

    def _inhabit_abstract(
        self,
        doc: DocumentObject,
        plan: DocumentPlan,
        typography_rules: dict[str, Any],
        body_anchor_idx: int | None = None,
    ) -> None:
        abstract_idx = None
        toc_idx = None

        for i, p in enumerate(doc.paragraphs):
            t = " ".join(p.text.strip().upper().split())
            if t == "ABSTRACT" and abstract_idx is None:
                abstract_idx = i
            elif (
                "TABLE OF CONTENT" in t or "TABLE OF CONTENTS" in t or t in ("INDEX", "CONTENTS")
            ) and toc_idx is None:
                if abstract_idx is not None and i > abstract_idx:
                    toc_idx = i
            if abstract_idx is not None and toc_idx is not None:
                break

        if abstract_idx is None:
            return

        end_abstract = (
            toc_idx if toc_idx else (body_anchor_idx if body_anchor_idx else abstract_idx + 25)
        )
        abstract_text = self._synthesize_abstract_text(plan)

        body_rules = typography_rules.get("body", {})
        font_name = body_rules.get("font_name", "Times New Roman")
        size_pt = body_rules.get("size_pt", 12.0)
        line_spacing = body_rules.get("line_spacing", 1.5)

        abstract_written = False
        target_paras = list(doc.paragraphs[abstract_idx + 1 : end_abstract])

        for p in target_paras:
            t = p.text.strip()
            if not t:
                continue
            t_low = t.lower()
            is_abstract_placeholder = (
                t_low.startswith("abstract -")
                or "context/relevance" in t_low
                or "write abstract" in t_low
                or "[abstract]" in t_low
            )
            is_rule_line = is_instruction_or_rule_paragraph(t) or any(
                kw in t_low
                for kw in [
                    "font style:",
                    "spacing:",
                    "font size:",
                    "style: times",
                    "case: lower",
                    "case: upper",
                    "re & after",
                    "act paragraph",
                    "size:-14",
                    "size:-12",
                ]
            )

            if is_abstract_placeholder and not abstract_written:
                p.text = abstract_text
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.line_spacing = line_spacing
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(6)
                for r in p.runs:
                    r.font.name = font_name
                    r.font.size = Pt(size_pt)
                    r.bold = False
                abstract_written = True
            elif is_rule_line or is_abstract_placeholder:
                self._strip_or_remove_instruction_paragraph(p)

        if not abstract_written and target_paras:
            # Populate the first non-heading paragraph under ABSTRACT if none matched placeholder keywords
            first_p = target_paras[0]
            first_p.text = abstract_text
            first_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            first_p.paragraph_format.line_spacing = line_spacing
            first_p.paragraph_format.space_before = Pt(0)
            first_p.paragraph_format.space_after = Pt(6)
            for r in first_p.runs:
                r.font.name = font_name
                r.font.size = Pt(size_pt)
                r.bold = False

    def _inhabit_table_of_contents(
        self,
        doc: DocumentObject,
        plan: DocumentPlan | None = None,
        body_anchor_idx: int | None = None,
        anchor_elem: Any = None,
    ) -> None:
        toc_idx = None
        for i, p in enumerate(doc.paragraphs):
            t = " ".join(p.text.strip().upper().split())
            if ("TABLE OF CONTENT" in t or "TABLE OF CONTENTS" in t or t == "INDEX") and toc_idx is None:
                toc_idx = i
                break

        if toc_idx is None:
            return

        end_toc = body_anchor_idx if body_anchor_idx else toc_idx + 25
        for p in list(doc.paragraphs[toc_idx + 1 : end_toc]):
            if anchor_elem is not None and p._p == anchor_elem:
                break
            t = p.text.strip()
            if not t:
                continue
            t_low = t.lower()
            if is_instruction_or_rule_paragraph(t) or any(
                kw in t_low
                for kw in [
                    "font style:",
                    "spacing:",
                    "font size:",
                    "style: times",
                    "case: lower",
                    "case: upper",
                    "re & after",
                    "heading should be",
                    "pages till index",
                    "size:-14",
                    "size:-12",
                ]
            ):
                self._strip_or_remove_instruction_paragraph(p)

    def _purge_and_inhabit_institutional_body(
        self,
        locked_doc: LockedTemplate,
        plan: DocumentPlan,
        anchor_elem: Any,
        warnings: list[str] | None = None,
        source_numbers: dict[str, int] | None = None,
    ) -> None:
        doc = locked_doc.doc
        body = doc._body._body
        body_children = list(body)

        anchor_pos = (
            body_children.index(anchor_elem)
            if anchor_elem is not None and anchor_elem in body_children
            else None
        )
        if anchor_pos is None:
            # Fallback: scan for first body paragraph with Chapter 1 or Note
            for idx, child in enumerate(body_children):
                if child.tag.endswith("p"):
                    p_text = "".join(child.itertext()).strip().upper()
                    if (
                        "CHAPTER 1" in p_text
                        or "CHAPTER - 1" in p_text
                        or "CHAPTER-1" in p_text
                        or "NOTE: CHAPTER 1" in p_text
                        or "NOTE: CHAPTER - 1" in p_text
                    ):
                        anchor_pos = idx
                        break
        if anchor_pos is None:
            anchor_pos = len(body_children) - 1

        saved_table_xmls = [copy.deepcopy(t._tbl) for t in doc.tables]

        # Purge dummy sample content and tips from anchor_pos onwards
        for child in body_children[anchor_pos:]:
            tag = child.tag.split("}")[-1]
            if tag == "p":
                has_sectPr = bool(child.xpath("./w:pPr/w:sectPr"))
                if has_sectPr:
                    # Strip runs and drawings, keep sectPr
                    for sub in list(child):
                        if not sub.tag.endswith("pPr"):
                            child.remove(sub)
                else:
                    try:
                        body.remove(child)
                    except ValueError:
                        pass
            elif tag == "tbl":
                try:
                    body.remove(child)
                except ValueError:
                    pass

        # Render sections in order
        for idx, section in enumerate(plan.sections, start=1):
            stitle = section.title.strip()
            if not stitle.upper().startswith("CHAPTER") and not re.match(r"^\d+\.", stitle):
                formatted_title = f"CHAPTER {idx}: {stitle.upper()}"
            else:
                formatted_title = stitle

            self.insert_heading(
                locked_doc,
                formatted_title,
                requested_style="Heading 1",
                warnings=warnings,
            )

            for p_text in section.paragraphs:
                if p_text and p_text.strip():
                    self.insert_paragraph(locked_doc, p_text, warnings=warnings)

            for b_text in section.bullets:
                if b_text and b_text.strip():
                    self.insert_bullet_point(locked_doc, b_text, warnings=warnings)

            if section.table_data and (section.table_data.headers or section.table_data.rows):
                if section.table_data.title:
                    p_tbl_cap = doc.add_paragraph(section.table_data.title)
                    self._apply_typography_rules(p_tbl_cap, "caption", locked_doc)
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

            for sub_idx, sub in enumerate(section.subsections, start=1):
                sub_title = sub.title.strip()
                if not re.match(r"^\d+\.\d+", sub_title):
                    sub_title = f"{idx}.{sub_idx} {sub_title}"
                self.insert_heading(
                    locked_doc,
                    sub_title,
                    requested_style="Heading 2",
                    warnings=warnings,
                )
                for sub_p in sub.paragraphs:
                    if sub_p and sub_p.strip():
                        self.insert_paragraph(locked_doc, sub_p, warnings=warnings)
                for sub_b in sub.bullets:
                    if sub_b and sub_b.strip():
                        self.insert_bullet_point(locked_doc, sub_b, warnings=warnings)

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
            "author": getattr(plan, "author", None) or "DocGuru Generator",
            "guide": getattr(plan, "guide", None) or "Faculty Guide",
            "department": getattr(plan, "department", None) or "Department",
            "institution": getattr(plan, "institution", None) or "Institution",
            "date": getattr(plan, "academic_year", None) or "2026",
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

        # Check if template is an institutional format (seminar report, thesis, proposal)
        anchor_idx = (
            body_anchor_index
            if body_anchor_index is not None
            else getattr(locked_doc.spec, "body_anchor_index", None)
        )
        is_inst = getattr(locked_doc.spec, "is_institutional_template", False) or (
            anchor_idx is not None and is_structured and replacements_count == 0
        )

        if is_inst and template_mode != "append":
            # Capture anchor XML element before front-matter instruction stripping mutates paragraph indices
            anchor_elem = (
                doc.paragraphs[anchor_idx]._p
                if anchor_idx is not None and 0 <= anchor_idx < len(doc.paragraphs)
                else None
            )

            author_name = getattr(plan, "author", None) or "Student Name"
            guide_name = getattr(plan, "guide", None) or "Faculty Guide"
            dept_name = getattr(plan, "department", None)
            inst_name = getattr(plan, "institution", None)
            acad_year = getattr(plan, "academic_year", None)

            typography_rules = getattr(locked_doc.spec, "parsed_typography_rules", {})
            self._inhabit_abstract(doc, plan, typography_rules, anchor_idx)
            self._inhabit_table_of_contents(doc, plan, anchor_idx, anchor_elem=anchor_elem)
            self._inhabit_institutional_front_matter(
                doc,
                plan,
                author_name,
                guide_name,
                department=dept_name,
                institution=inst_name,
                academic_year=acad_year,
                body_anchor_idx=anchor_idx,
                anchor_elem=anchor_elem,
                warnings=warnings,
            )

            self._purge_and_inhabit_institutional_body(
                locked_doc=locked_doc,
                plan=plan,
                anchor_elem=anchor_elem,
                warnings=warnings,
                source_numbers=source_numbers,
            )
        elif template_mode == "fill":
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
        elif template_mode == "append":
            # Explicit append mode: keep existing body content, append new content before final sectPr
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
            # Replace body in-place (default for create_document mode)
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
