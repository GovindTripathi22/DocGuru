from typing import List, Dict, Any, Optional, Tuple
import copy
import difflib
from pathlib import Path
import docx
from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell, _Row

from .style_lock import LockedTemplate, StyleLock, StyleLockViolationError
from .list_resolver import ListStyleResolver
from ..config import settings
from ..errors import AppError
from ..models.generation import DocumentPlan, DocumentSection, TableData, ThemeOverrideRequest
from ..models.template_spec import TemplateSpecification


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

    def clear_body_content_preserving_structure(self, doc: Document) -> List[Any]:
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
        requested_style: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ) -> Paragraph:
        doc = locked_doc.doc
        validated_style = locked_doc.validate_style_allowed(requested_style) if requested_style else None

        if validated_style:
            try:
                p = doc.add_paragraph(text, style=doc.styles[validated_style])
                return p
            except Exception:
                pass

        # Fallback to bold paragraph with default style
        if warnings is not None and requested_style:
            warnings.append(f"heading_style_fallback:{requested_style}")
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        return p

    def insert_paragraph(
        self,
        locked_doc: LockedTemplate,
        text: str,
        requested_style: Optional[str] = None,
    ) -> Paragraph:
        doc = locked_doc.doc
        validated_style = locked_doc.validate_style_allowed(requested_style) if requested_style else None

        if validated_style:
            try:
                return doc.add_paragraph(text, style=doc.styles[validated_style])
            except Exception:
                pass

        return doc.add_paragraph(text)

    def insert_bullet_point(
        self,
        locked_doc: LockedTemplate,
        text: str,
        level: int = 0,
        warnings: Optional[List[str]] = None,
    ) -> Paragraph:
        doc = locked_doc.doc
        p = doc.add_paragraph()
        resolver = ListStyleResolver(doc)
        resolver.apply_bullet(p, text, level=level, warnings=warnings)
        return p

    def insert_cloned_table(
        self,
        locked_doc: LockedTemplate,
        headers: List[str],
        rows: List[List[str]],
        saved_table_xmls: Optional[List[Any]] = None,
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
            except Exception:
                pass

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
        template_data_row_xml = copy.deepcopy(xml_rows[1]) if len(xml_rows) > 1 else (
            copy.deepcopy(xml_rows[0]) if len(xml_rows) > 0 else None
        )

        for r_elem in xml_rows:
            new_tbl_xml.remove(r_elem)

        # Header row
        if headers and template_header_row_xml is not None:
            h_row = copy.deepcopy(template_header_row_xml)
            cells = list(h_row.xpath(".//w:tc"))
            while len(cells) < col_count and len(cells) > 0:
                new_tc = copy.deepcopy(cells[-1])
                h_row.append(new_tc)
                cells.append(new_tc)
            while len(cells) > col_count:
                h_row.remove(cells.pop())
            new_tbl_xml.append(h_row)

        # Data rows
        for _ in rows:
            if template_data_row_xml is not None:
                d_row = copy.deepcopy(template_data_row_xml)
                cells = list(d_row.xpath(".//w:tc"))
                while len(cells) < col_count and len(cells) > 0:
                    new_tc = copy.deepcopy(cells[-1])
                    d_row.append(new_tc)
                    cells.append(new_tc)
                while len(cells) > col_count:
                    d_row.remove(cells.pop())
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
                        self._set_cell_text_preserve_formatting(table.rows[target_r].cells[c], str(val))

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
        caption: Optional[str] = None,
        max_width_inches: Optional[float] = None,
    ) -> Optional[Any]:
        doc = locked_doc.doc
        p_img = Path(image_path)
        if not p_img.exists():
            return None

        sec = doc.sections[-1]
        avail_width = sec.page_width - sec.left_margin - sec.right_margin
        width = avail_width if max_width_inches is None else min(avail_width, Inches(max_width_inches))

        p = doc.add_paragraph()
        run = p.add_run()
        run.add_picture(str(p_img), width=width)

        if caption:
            p_cap = doc.add_paragraph(caption)
            try:
                p_cap.style = doc.styles["Caption"]
            except Exception:
                p_cap.runs[0].italic = True
        return p

    def replace_placeholders_preserving_runs(self, doc: Document, mapping: Dict[str, str]) -> int:
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

    def mark_toc_fields_dirty(self, doc: Document) -> None:
        """Marks Table of Contents fields with w:dirty='true' so Word prompts for refresh (DOCX-03)."""
        body_elem = doc._body._body
        for fld in body_elem.xpath(".//w:fldChar[@w:fldCharType='begin']"):
            fld.set(qn("w:dirty"), "true")

    def apply_overrides(self, doc: Document, overrides: List[ThemeOverrideRequest]) -> None:
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
                        except Exception:
                            pass
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
        edit_action: Optional[str] = None,
        target_heading: Optional[str] = None,
        target_index: Optional[int] = None,
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

        if target_index is not None and 0 <= target_index < len(outline):
            target_text = outline[target_index]
            for i, p in enumerate(doc.paragraphs):
                if target_text.strip().lower() in p.text.strip().lower():
                    resolved_p_idx = i
                    break

        if resolved_p_idx is None and target_heading:
            clean_target = target_heading.strip().lower()
            # Exact match
            for i, p in enumerate(doc.paragraphs):
                if clean_target == p.text.strip().lower():
                    resolved_p_idx = i
                    break

            # Fuzzy match if not exact
            if resolved_p_idx is None:
                scored = []
                for i, p in enumerate(doc.paragraphs):
                    p_clean = p.text.strip().lower()
                    if p_clean:
                        ratio = difflib.SequenceMatcher(None, clean_target, p_clean).ratio()
                        if ratio >= 0.75:
                            scored.append((ratio, i, p.text.strip()))
                scored.sort(reverse=True)
                if scored:
                    if len(scored) == 1 or (len(scored) > 1 and scored[0][0] - scored[1][0] > 0.15):
                        resolved_p_idx = scored[0][1]
                    else:
                        candidates = [s[2] for s in scored[:5]]

        if resolved_p_idx is None and target_heading:
            raise AppError(
                code="EDIT_TARGET_NOT_FOUND",
                http_status=422,
                message=f"Edit target heading '{target_heading}' could not be unambiguously resolved.",
                details={"candidates": candidates or outline[:5]},
            )

        action = edit_action or "append"
        saved_table_xmls = [copy.deepcopy(t._tbl) for t in doc.tables]

        if action == "append" or resolved_p_idx is None:
            # Append before final sectPr
            for s in plan.sections:
                self._render_section(locked_doc, s, saved_table_xmls)
        elif action == "insert_after":
            # Find end of target section (next heading)
            end_idx = len(doc.paragraphs)
            for j in range(resolved_p_idx + 1, len(doc.paragraphs)):
                p = doc.paragraphs[j]
                if p.style and ("heading" in p.style.name.lower() or "title" in p.style.name.lower()):
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
                            except Exception:
                                for st in doc.styles:
                                    if st.name.lower() == style_name.lower():
                                        style_obj = st
                                        break
                        if style_obj:
                            next_p.insert_paragraph_before(s.title, style=style_obj)
                        else:
                            hp = next_p.insert_paragraph_before(s.title)
                            if hp.runs:
                                hp.runs[0].bold = True
                    for p_text in s.paragraphs:
                        next_p.insert_paragraph_before(p_text)
                    for b_text in s.bullets:
                        next_p.insert_paragraph_before(f"•  {b_text}")
            else:
                for s in plan.sections:
                    self._render_section(locked_doc, s, saved_table_xmls)
        elif action == "replace":
            # Keep heading, replace body paragraphs within section
            target_p = doc.paragraphs[resolved_p_idx]
            for s in plan.sections:
                for p_text in s.paragraphs:
                    p_new = doc.add_paragraph(p_text)
                    target_p._p.addnext(p_new._p)
                    target_p = p_new

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path

    def _render_section(
        self,
        locked_doc: LockedTemplate,
        section: DocumentSection,
        saved_table_xmls: List[Any],
        warnings: Optional[List[str]] = None,
    ) -> None:
        if section.title:
            self.insert_heading(
                locked_doc,
                section.title,
                requested_style=section.heading_style or "Heading 1",
                warnings=warnings,
            )

        for p_text in section.paragraphs:
            self.insert_paragraph(locked_doc, p_text)

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
            self._render_section(locked_doc, sub, saved_table_xmls, warnings=warnings)

    def generate_from_plan(
        self,
        locked_doc: LockedTemplate,
        plan: DocumentPlan,
        output_path: str,
        template_mode: str = "auto",
        body_anchor_index: Optional[int] = None,
        overrides: Optional[List[ThemeOverrideRequest]] = None,
        edit_action: Optional[str] = None,
        target_heading: Optional[str] = None,
        target_index: Optional[int] = None,
        warnings: Optional[List[str]] = None,
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

        if template_mode == "fill":
            # Fill mode: keep existing structure, placeholders already replaced
            saved_table_xmls = [copy.deepcopy(t._tbl) for t in doc.tables]
            for s in plan.sections:
                self._render_section(locked_doc, s, saved_table_xmls, warnings=warnings)
        elif template_mode == "append" or (template_mode == "auto" and is_structured and replacements_count == 0 and not body_anchor_index):
            # Append mode: keep all existing body content, append new content before final sectPr
            saved_table_xmls = [copy.deepcopy(t._tbl) for t in doc.tables]
            for s in plan.sections:
                self._render_section(locked_doc, s, saved_table_xmls, warnings=warnings)
        else:
            # Clear or replace body after anchor
            saved_table_xmls = self.clear_body_content_preserving_structure(doc)

            # DOCX-01: Always render document title in create mode
            if plan.title and replacements_count == 0:
                self.insert_heading(locked_doc, plan.title, requested_style="Title", warnings=warnings)

            # Render sections
            for idx, section in enumerate(plan.sections):
                self._render_section(locked_doc, section, saved_table_xmls, warnings=warnings)
                # D13 / DOCX-07: No forced page breaks between sections unless explicitly configured
                if settings.PAGE_BREAK_BETWEEN_SECTIONS and idx < len(plan.sections) - 1:
                    doc.add_page_break()

            # DOCX-01: Render conclusion as a final section with heading "Conclusion"
            if plan.conclusion:
                self.insert_heading(locked_doc, "Conclusion", requested_style="Heading 1", warnings=warnings)
                self.insert_paragraph(locked_doc, plan.conclusion)

        # 3. Apply user overrides if specified (DOCX-05)
        if overrides:
            self.apply_overrides(doc, overrides)

        # 4. Mark TOC dirty for Word refresh
        self.mark_toc_fields_dirty(doc)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path
