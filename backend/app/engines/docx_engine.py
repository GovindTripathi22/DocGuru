from typing import List, Dict, Any, Optional
import copy
from pathlib import Path
import docx
from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell, _Row

from .style_lock import LockedTemplate, StyleLock, StyleLockViolationError
from ..models.generation import DocumentPlan, DocumentSection, TableData
from ..models.template_spec import TemplateSpecification

class DocxEngine:
    """
    Exact template-preserving DOCX engine.
    
    CRITICAL: Never creates a blank document from scratch.
    Always loads the original template file, preserves all XML structures,
    styles, headers, footers, borders, and margins, and modifies only content.
    """

    def __init__(self):
        pass

    def load_template(self, file_path: str, spec: TemplateSpecification) -> LockedTemplate:
        """
        Load an existing DOCX template and wrap it with StyleLock.
        """
        doc = Document(file_path)
        return LockedTemplate(docx_document=doc, template_path=file_path, spec=spec)

    def clear_body_content_preserving_structure(self, doc: Document) -> List[Any]:
        """
        Clears existing body paragraphs and tables while strictly preserving:
        - Section properties (w:sectPr at the bottom of w:body)
        - Document styles.xml, numbering.xml, theme.xml
        - Headers and footers attached to sections
        - Page margins and dimensions
        
        Returns a list of saved table XML elements (to allow cloning template tables).
        """
        saved_table_xmls = []
        body_elem = doc._body._body

        # Save template table XML elements before clearing for structure cloning
        for child in list(body_elem):
            if child.tag.endswith('tbl'):
                saved_table_xmls.append(copy.deepcopy(child))

        # Remove all children of w:body EXCEPT w:sectPr
        for child in list(body_elem):
            if not child.tag.endswith('sectPr'):
                body_elem.remove(child)

        return saved_table_xmls

    def insert_heading(self, locked_doc: LockedTemplate, text: str, requested_style: Optional[str] = None) -> Paragraph:
        """
        Inserts a heading using an EXACT style from the template if available.
        If the requested style doesn't exist in the template, safely falls back
        to a bold styled paragraph without crashing or corrupting styles.
        """
        if requested_style:
            StyleLock.assert_content_only({"style": requested_style, "content": text})
        doc = locked_doc.doc
        validated_style = locked_doc.validate_style_allowed(requested_style) if requested_style else None
        
        # 1. Try adding paragraph with validated heading style
        if validated_style:
            try:
                if validated_style in doc.styles:
                    p = doc.add_paragraph(text, style=validated_style)
                    return p
            except Exception:
                pass

        # 2. Fallback: use default body style (or no explicit style) and bold the text
        try:
            default_style = locked_doc.default_body_style
            if default_style and default_style in doc.styles:
                p = doc.add_paragraph(style=default_style)
            else:
                p = doc.add_paragraph()
            run = p.add_run(text)
            run.bold = True
            if locked_doc.spec and locked_doc.spec.fonts and locked_doc.spec.fonts.heading1:
                run.font.name = locked_doc.spec.fonts.heading1
            return p
        except Exception:
            p = doc.add_paragraph()
            run = p.add_run(text)
            run.bold = True
            return p

    def insert_paragraph(self, locked_doc: LockedTemplate, text: str, requested_style: Optional[str] = None) -> Paragraph:
        """
        Inserts a paragraph using an EXACT style from the template if available.
        """
        style = locked_doc.validate_style_allowed(requested_style or locked_doc.default_body_style)
        if style:
            StyleLock.assert_content_only({"style": style, "content": text})
        
        doc = locked_doc.doc
        if style:
            try:
                if style in doc.styles:
                    p = doc.add_paragraph(text, style=style)
                    return p
            except Exception:
                pass

        p = doc.add_paragraph(text)
        return p

    def insert_bullet_item(self, locked_doc: LockedTemplate, text: str, level: int = 0) -> Paragraph:
        """
        Inserts a bullet point using the template's List Bullet style if available,
        or falls back to bullet run formatting.
        """
        doc = locked_doc.doc
        bullet_style = None
        for s in locked_doc.allowed_styles:
            if ("bullet" in s.lower() or "list" in s.lower()):
                try:
                    if s in doc.styles:
                        bullet_style = s
                        break
                except Exception:
                    pass

        if bullet_style:
            try:
                p = doc.add_paragraph(style=bullet_style)
                p.add_run(text)
                return p
            except Exception:
                pass

        p = doc.add_paragraph()
        p.add_run(f"•  {text}")
        return p

    def insert_cloned_table(
        self,
        locked_doc: LockedTemplate,
        headers: List[str],
        rows: List[List[str]],
        saved_table_xmls: Optional[List[Any]] = None,
        source_table_index: int = 0
    ) -> Table:
        """
        Clones an existing table's XML structure and fills it with new content.
        Preserves:
        - Table borders (w:tblBorders)
        - Cell borders (w:tcBorders)
        - Cell shading (w:shd)
        - Cell margins (w:tcMar)
        - Column widths (w:gridCol)
        - Header row formatting (w:tblHeader)
        - Cell paragraph styles
        """
        doc = locked_doc.doc
        body_elem = doc._body._body

        # If a saved template table is available, use its XML structure
        if saved_table_xmls and 0 <= source_table_index < len(saved_table_xmls):
            template_tbl_xml = copy.deepcopy(saved_table_xmls[source_table_index])
        elif len(doc.tables) > 0 and 0 <= source_table_index < len(doc.tables):
            template_tbl_xml = copy.deepcopy(doc.tables[source_table_index]._tbl)
        else:
            # If no template table existed, create a standard table using default template style
            col_count = max(len(headers), max((len(r) for r in rows), default=1))
            table = doc.add_table(rows=len(rows) + (1 if headers else 0), cols=col_count)
            # Find a valid table style from template
            table_styles = [s for s in locked_doc.allowed_styles if "Table" in s or "Grid" in s]
            if table_styles:
                table.style = table_styles[0]
            
            # Fill headers
            current_row = 0
            if headers:
                for c_idx, h_text in enumerate(headers):
                    if c_idx < col_count:
                        table.cell(0, c_idx).text = str(h_text)
                current_row = 1

            for r_idx, row_data in enumerate(rows):
                for c_idx, cell_data in enumerate(row_data):
                    if c_idx < col_count:
                        table.cell(current_row + r_idx, c_idx).text = str(cell_data)
            return table

        # We have a template table XML!
        # Insert cloned XML before sectPr
        sect_pr = None
        for child in list(body_elem):
            if child.tag.endswith('sectPr'):
                sect_pr = child
                break

        new_tbl_xml = copy.deepcopy(template_tbl_xml)
        if sect_pr is not None:
            body_elem.insert(body_elem.index(sect_pr), new_tbl_xml)
        else:
            body_elem.append(new_tbl_xml)

        table = Table(new_tbl_xml, doc)

        # Inspect template table rows to clone row formatting
        template_header_row_xml = None
        template_data_row_xml = None
        
        xml_rows = list(new_tbl_xml.xpath('.//w:tr'))
        if len(xml_rows) > 0:
            template_header_row_xml = copy.deepcopy(xml_rows[0])
        if len(xml_rows) > 1:
            template_data_row_xml = copy.deepcopy(xml_rows[1])
        elif len(xml_rows) > 0:
            template_data_row_xml = copy.deepcopy(xml_rows[0])

        # Remove existing rows from table XML
        for r_elem in xml_rows:
            new_tbl_xml.remove(r_elem)

        total_cols = max(len(headers), max((len(r) for r in rows), default=1))

        # Add header row if headers provided
        if headers and template_header_row_xml is not None:
            h_row_elem = copy.deepcopy(template_header_row_xml)
            cells = list(h_row_elem.xpath('.//w:tc'))
            while len(cells) < total_cols and len(cells) > 0:
                new_tc = copy.deepcopy(cells[-1])
                h_row_elem.append(new_tc)
                cells.append(new_tc)
            while len(cells) > total_cols:
                excess = cells.pop()
                h_row_elem.remove(excess)
            new_tbl_xml.append(h_row_elem)

        # Add data rows
        for _ in rows:
            if template_data_row_xml is not None:
                d_row_elem = copy.deepcopy(template_data_row_xml)
                cells = list(d_row_elem.xpath('.//w:tc'))
                while len(cells) < total_cols and len(cells) > 0:
                    new_tc = copy.deepcopy(cells[-1])
                    d_row_elem.append(new_tc)
                    cells.append(new_tc)
                while len(cells) > total_cols:
                    excess = cells.pop()
                    d_row_elem.remove(excess)
                new_tbl_xml.append(d_row_elem)

        # Now re-wrap and populate text in table cells while keeping cell styling
        table = Table(new_tbl_xml, doc)
        row_offset = 0
        if headers:
            for c_idx, h_text in enumerate(headers):
                if c_idx < len(table.rows[0].cells):
                    cell = table.rows[0].cells[c_idx]
                    self._set_cell_text_preserve_formatting(cell, str(h_text))
            row_offset = 1

        for r_idx, row_data in enumerate(rows):
            target_row_idx = row_offset + r_idx
            if target_row_idx < len(table.rows):
                for c_idx, cell_value in enumerate(row_data):
                    if c_idx < len(table.rows[target_row_idx].cells):
                        cell = table.rows[target_row_idx].cells[c_idx]
                        self._set_cell_text_preserve_formatting(cell, str(cell_value))

        return table

    def _set_cell_text_preserve_formatting(self, cell: _Cell, text: str) -> None:
        """
        Sets text in a cell while preserving the cell's original paragraph and run styling.
        """
        if not cell.paragraphs:
            p = cell.add_paragraph()
            p.text = text
            return

        p = cell.paragraphs[0]
        if p.runs:
            # Keep first run formatting, update text
            p.runs[0].text = text
            for r in p.runs[1:]:
                r.text = ""
        else:
            p.text = text

        # Clean any extra paragraphs left from template
        for extra_p in cell.paragraphs[1:]:
            extra_p.text = ""

    def replace_text_preserving_runs(self, doc: Document, search_text: str, replacement_text: str) -> int:
        """
        Replaces text in existing paragraphs without wiping out runs, fonts, bold, or colors.
        Returns the number of replacements made.
        """
        replacements = 0
        for p in doc.paragraphs:
            if search_text in p.text:
                full_text = "".join(r.text for r in p.runs)
                if search_text in full_text:
                    # Check if search_text is contained inside a single run
                    replaced_in_run = False
                    for r in p.runs:
                        if search_text in r.text:
                            r.text = r.text.replace(search_text, replacement_text)
                            replaced_in_run = True
                            replacements += 1
                            break

                    if not replaced_in_run and p.runs:
                        # Reconstruct runs keeping primary run formatting
                        new_text = full_text.replace(search_text, replacement_text)
                        p.runs[0].text = new_text
                        for r in p.runs[1:]:
                            r.text = ""
                        replacements += 1

        # Also search in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if search_text in p.text:
                            for r in p.runs:
                                if search_text in r.text:
                                    r.text = r.text.replace(search_text, replacement_text)
                                    replacements += 1
                                    break
        return replacements

    def generate_from_plan(
        self,
        locked_doc: LockedTemplate,
        plan: DocumentPlan,
        output_path: str
    ) -> str:
        """
        Applies a complete DocumentPlan onto the locked template DOCX.
        Preserves all headers, footers, styles, page borders, and section properties.
        """
        doc = locked_doc.doc

        # Clear existing body paragraphs/tables, but save template table structures
        saved_table_xmls = self.clear_body_content_preserving_structure(doc)

        # Process each section in the plan
        for section in plan.sections:
            self._render_section(locked_doc, section, saved_table_xmls)

        # If user explicitly requested theme overrides (e.g., change blue border to yellow)
        if plan.theme_overrides:
            self.apply_theme_overrides(doc, plan.theme_overrides)

        # Save the result
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path

    def apply_theme_overrides(self, doc: Document, overrides: List[Any]) -> int:
        """
        Surgically modifies ONLY the specific visual properties explicitly requested by the user
        (e.g., change blue border to yellow) while keeping all other template properties locked.
        """
        color_name_map = {
            "yellow": "FFFF00",
            "gold": "FFD700",
            "blue": "0000FF",
            "dark blue": "002060",
            "red": "FF0000",
            "dark red": "C00000",
            "green": "008000",
            "dark green": "004d00",
            "black": "000000",
            "white": "FFFFFF",
            "orange": "FF6600",
            "purple": "800080",
            "gray": "808080"
        }

        changes_applied = 0
        body_elem = doc._body._body

        for override in overrides:
            elem_type = getattr(override, "element_type", "").lower()
            target_id = (getattr(override, "target_identifier", "") or "").lower()
            new_val = getattr(override, "new_value", "")
            
            # Normalize hex color
            clean_color = color_name_map.get(new_val.lower(), new_val.replace("#", "").upper())

            if "border" in elem_type:
                # Find all border XML elements (pBdr, tblBorders, tcBorders, pgBorders)
                for border_elem in body_elem.xpath('.//w:top | .//w:bottom | .//w:left | .//w:right | .//w:insideH | .//w:insideV'):
                    current_color = border_elem.get(qn('w:color'), '')
                    
                    # If target specified (e.g. "blue" or "bottom")
                    should_change = False
                    if not target_id:
                        should_change = True
                    elif target_id in current_color.lower() or color_name_map.get(target_id, "") == current_color.upper():
                        should_change = True
                    elif border_elem.tag.endswith(target_id):
                        should_change = True
                    elif "blue" in target_id and ("00" in current_color.upper() and ("FF" in current_color.upper() or "70" in current_color.upper())):
                        should_change = True

                    if should_change:
                        border_elem.set(qn('w:color'), clean_color)
                        changes_applied += 1

            elif "heading" in elem_type or "font" in elem_type:
                # Change font color of specific style
                for s in doc.styles:
                    if target_id in s.name.lower() or (not target_id and "heading" in s.name.lower()):
                        if hasattr(s, 'font') and s.font:
                            from docx.shared import RGBColor
                            try:
                                r = int(clean_color[0:2], 16)
                                g = int(clean_color[2:4], 16)
                                b = int(clean_color[4:6], 16)
                                s.font.color.rgb = RGBColor(r, g, b)
                                changes_applied += 1
                            except Exception:
                                pass

        return changes_applied

    def _render_section(
        self,
        locked_doc: LockedTemplate,
        section: DocumentSection,
        saved_table_xmls: List[Any]
    ) -> None:
        """
        Renders a single document section into the locked document.
        """
        # Heading
        if section.title:
            self.insert_heading(locked_doc, section.title, requested_style=section.heading_style)

        # Paragraphs
        for para in section.paragraphs:
            if para.strip():
                self.insert_paragraph(locked_doc, para)

        # Bullets
        for bullet in section.bullets:
            if bullet.strip():
                self.insert_bullet_item(locked_doc, bullet)

        # Image / Figure
        if section.image_path and Path(section.image_path).exists():
            self.insert_image(
                locked_doc=locked_doc,
                image_path=section.image_path,
                caption=section.image_caption or f"Figure: {section.title}"
            )

        # Table
        if section.table_data and (section.table_data.headers or section.table_data.rows):
            if section.table_data.title:
                self.insert_paragraph(locked_doc, section.table_data.title, requested_style=locked_doc.default_body_style)
            self.insert_cloned_table(
                locked_doc=locked_doc,
                headers=section.table_data.headers,
                rows=section.table_data.rows,
                saved_table_xmls=saved_table_xmls,
                source_table_index=section.table_data.source_table_index
            )
            # Add an empty paragraph after table for spacing
            self.insert_paragraph(locked_doc, "")

        # Subsections
        for subsec in section.subsections:
            self._render_section(locked_doc, subsec, saved_table_xmls)

    def insert_image(
        self,
        locked_doc: LockedTemplate,
        image_path: str,
        caption: Optional[str] = None,
        width_inches: float = 5.5
    ) -> None:
        """
        Inserts an image into the document with center alignment and an optional caption.
        """
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = locked_doc.doc
        try:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(image_path, width=Inches(width_inches))

            if caption:
                cap_p = doc.add_paragraph()
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_run = cap_p.add_run(caption)
                cap_run.italic = True
                try:
                    if "Caption" in doc.styles:
                        cap_p.style = doc.styles["Caption"]
                except Exception:
                    pass
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not insert image {image_path}: {e}")
