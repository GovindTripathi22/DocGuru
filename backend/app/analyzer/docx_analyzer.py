from typing import Dict, List, Any, Optional, Set
import hashlib
import json
from pathlib import Path
import docx
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH

from ..models.template_spec import (
    TemplateSpecification,
    PageSpec,
    MarginSpec,
    FontSpec,
    StyleSpec,
    ParagraphRuleSpec,
    TableRuleSpec,
    HeaderFooterSpec,
    NumberingSpec,
    BorderSpec,
    BorderItemSpec,
    ThemeSpec,
    LockStatus,
)

class DocxAnalyzer:
    """
    Deterministic template analyzer for DOCX files.
    Extracts a machine-readable TemplateSpecification while maintaining
    the original file as the authoritative source of truth.
    """

    def __init__(self):
        pass

    def analyze(self, file_path: str) -> TemplateSpecification:
        doc = Document(file_path)
        filename = Path(file_path).name

        # 1. Extract Page & Margin specifications
        page_spec = self._extract_page_spec(doc)

        # 2. Extract Styles & Typography
        styles_dict, font_spec, available_headings, available_body = self._extract_styles(doc)

        # 3. Extract Paragraph Rules
        paragraph_rules = self._extract_paragraph_rules(doc)

        # 4. Extract Tables
        table_rules = self._extract_tables(doc)

        # 5. Extract Header and Footer
        header_spec, footer_spec = self._extract_headers_footers(doc)

        # 6. Extract Numbering
        numbering_spec = self._extract_numbering(doc)

        # 7. Extract Borders
        borders = self._extract_borders(doc)

        # Calculate deterministic style hash
        style_hash = self._compute_docx_style_hash(
            page_spec=page_spec,
            font_spec=font_spec,
            styles=styles_dict,
            header=header_spec,
            footer=footer_spec,
            table_rules=table_rules
        )

        # 8. Extract Rules, Guidelines, and Outline from Document Content
        extracted_rules, document_outline, doc_summary = self._extract_rules_and_outline(doc)

        return TemplateSpecification(
            filename=filename,
            document_type="docx",
            total_pages_or_slides=max(1, len(doc.sections)),
            page=page_spec,
            fonts=font_spec,
            styles=styles_dict,
            paragraph_rules=paragraph_rules,
            table_rules=table_rules,
            header=header_spec,
            footer=footer_spec,
            numbering=numbering_spec,
            borders=borders,
            available_heading_styles=available_headings,
            available_body_styles=available_body,
            extracted_rules=extracted_rules,
            document_outline=document_outline,
            document_text_summary=doc_summary,
            style_hash=style_hash,
            lock_status=LockStatus()
        )

    def _extract_rules_and_outline(self, doc: Document):
        """
        Scans the document for internal formatting guidelines, submission rules,
        style requirements, and existing chapter headings/outline.
        """
        rule_keywords = [
            "STYLE:", "FONT", "SPACING:", "RULE", "NOTE:", "GUIDELINE", 
            "INSTRUCTION", "FORMAT", "ALIGNMENT:", "CASE:", "CITATION", 
            "MUST", "SHALL", "SHOULD", "TIPS:", "REQUIREMENT", "CRITERIA",
            "SPECIFICATION", "FOR EXAMPLE:", "FIGURE NUMBERING:", "TABLE NUMBERING:",
            "MARGIN", "MARGINS", "PAGE SETUP", "LINE SPACING", "PAPER SIZE",
            "REFERENCES:", "BIBLIOGRAPHY", "TABLE:", "FIGURE:", "SUBMISSION",
            "HEADER:", "FOOTER:", "PAGINATION", "INDENT"
        ]
        
        extracted_rules: List[str] = []
        document_outline: List[str] = []
        outline_set: Set[str] = set()
        seen_rules: Set[str] = set()
        summary_paragraphs: List[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            # Detect headings / outline
            style_name = (p.style.name if p.style else "").lower()
            is_heading = "heading" in style_name or "title" in style_name
            if (is_heading or (len(text) < 100 and any(text.upper().startswith(kw) for kw in ["CHAPTER", "SECTION", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."]))):
                if text not in outline_set and len(text) < 120:
                    outline_set.add(text)
                    document_outline.append(text)

            # Detect rule / guideline paragraphs
            upper_text = text.upper()
            has_rule_keyword = any(kw in upper_text for kw in rule_keywords)
            if has_rule_keyword and len(text) > 8 and len(text) < 300:
                clean_text = " ".join(text.split())
                if clean_text not in seen_rules:
                    seen_rules.add(clean_text)
                    extracted_rules.append(clean_text)

            if len(summary_paragraphs) < 15 and len(text) > 30 and not has_rule_keyword:
                summary_paragraphs.append(text[:150])

        doc_summary = " | ".join(summary_paragraphs[:8])
        return extracted_rules, document_outline, doc_summary

    def _extract_page_spec(self, doc: Document) -> PageSpec:
        if not doc.sections:
            return PageSpec()

        section = doc.sections[0]
        
        # Convert EMU or twips to points (1 pt = 12700 EMU, 1 pt = 20 twips)
        width_pt = section.page_width.pt if section.page_width else 612.0
        height_pt = section.page_height.pt if section.page_height else 792.0
        orientation = "landscape" if width_pt > height_pt else "portrait"

        margins = MarginSpec(
            top_pt=section.top_margin.pt if section.top_margin else 72.0,
            bottom_pt=section.bottom_margin.pt if section.bottom_margin else 72.0,
            left_pt=section.left_margin.pt if section.left_margin else 72.0,
            right_pt=section.right_margin.pt if section.right_margin else 72.0,
            header_pt=section.header_distance.pt if section.header_distance else 36.0,
            footer_pt=section.footer_distance.pt if section.footer_distance else 36.0,
        )

        return PageSpec(
            width_pt=width_pt,
            height_pt=height_pt,
            orientation=orientation,
            margins=margins,
            columns_count=1
        )

    def _extract_styles(self, doc: Document):
        styles_dict: Dict[str, StyleSpec] = {}
        all_fonts: Set[str] = set()
        heading_styles: List[str] = []
        body_styles: List[str] = []

        default_font = "Calibri"
        heading1_font = None
        heading2_font = None

        for style in doc.styles:
            if style.type not in (WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER):
                continue

            name = style.name
            is_paragraph_style = (style.type == WD_STYLE_TYPE.PARAGRAPH)
            font_name = None
            font_size = None
            bold = None
            italic = None
            color_hex = None

            if hasattr(style, 'font') and style.font:
                if style.font.name:
                    font_name = style.font.name
                    all_fonts.add(font_name)
                if style.font.size:
                    font_size = float(style.font.size.pt)
                bold = style.font.bold
                italic = style.font.italic
                if style.font.color and style.font.color.rgb:
                    color_hex = str(style.font.color.rgb)

            is_heading = "heading" in name.lower() or "title" in name.lower()

            # CRITICAL: Only add PARAGRAPH styles to heading/body lists.
            # Character styles (e.g. "Heading 1 Char") cannot be used with
            # doc.add_paragraph() and will raise KeyError.
            if is_heading and is_paragraph_style:
                heading_styles.append(name)
                if "1" in name:
                    heading1_font = font_name
                elif "2" in name:
                    heading2_font = font_name
            elif not is_heading and is_paragraph_style:
                body_styles.append(name)

            styles_dict[name] = StyleSpec(
                name=name,
                type="paragraph" if is_paragraph_style else "character",
                font_name=font_name,
                font_size_pt=font_size,
                bold=bold,
                italic=italic,
                color_hex=color_hex,
                is_heading=is_heading
            )

        # Validate that heading styles actually exist in the document's style
        # collection before using them. DO NOT fabricate styles that don't exist.
        validated_headings = []
        for hs in heading_styles:
            exists = False
            try:
                doc.styles[hs]
                exists = True
            except (KeyError, UserWarning):
                clean_id = hs.replace(" ", "")
                for s in doc.styles:
                    if s.name.lower() == hs.lower() or (hasattr(s, 'style_id') and s.style_id.lower() == clean_id.lower()):
                        exists = True
                        break
            if exists:
                validated_headings.append(hs)
        heading_styles = validated_headings

        # If no heading paragraph styles were found, leave the list empty.
        # Downstream code (planner, engine) will fall back to bold formatting.
        if not body_styles:
            body_styles = ["Normal"]

        font_spec = FontSpec(
            default=default_font,
            body="Calibri",
            heading1=heading1_font or "Calibri Light",
            heading2=heading2_font or "Calibri Light",
            all_detected_fonts=sorted(list(all_fonts))
        )

        return styles_dict, font_spec, heading_styles, body_styles

    def _extract_paragraph_rules(self, doc: Document) -> Dict[str, ParagraphRuleSpec]:
        rules: Dict[str, ParagraphRuleSpec] = {}
        for p in doc.paragraphs[:10]:
            style_name = p.style.name if p.style else "Normal"
            if style_name not in rules:
                align_str = "left"
                if p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
                    align_str = "center"
                elif p.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
                    align_str = "right"
                elif p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
                    align_str = "justify"

                space_before = p.paragraph_format.space_before.pt if p.paragraph_format.space_before else 0.0
                space_after = p.paragraph_format.space_after.pt if p.paragraph_format.space_after else 6.0
                line_spacing = p.paragraph_format.line_spacing if p.paragraph_format.line_spacing else 1.15

                keep_with_next = getattr(p.paragraph_format, "keep_with_next", False)
                keep_together = getattr(p.paragraph_format, "keep_together", False)
                widow_control = getattr(p.paragraph_format, "widow_control", True)

                rules[style_name] = ParagraphRuleSpec(
                    alignment=align_str,
                    spacing_before_pt=space_before,
                    spacing_after_pt=space_after,
                    line_spacing=float(line_spacing) if isinstance(line_spacing, (int, float)) else 1.15,
                    keep_with_next=bool(keep_with_next),
                    keep_lines_together=bool(keep_together),
                    widow_orphan=bool(widow_control)
                )
        return rules

    def _extract_tables(self, doc: Document) -> List[TableRuleSpec]:
        table_rules: List[TableRuleSpec] = []
        for idx, table in enumerate(doc.tables):
            col_widths = []
            if table.columns:
                for col in table.columns:
                    col_widths.append(float(col.width.pt) if col.width else 100.0)

            table_rules.append(TableRuleSpec(
                table_index=idx,
                rows=len(table.rows),
                cols=len(table.columns) if table.columns else 0,
                col_widths_pt=col_widths,
                alignment="center",
                style_name=table.style.name if table.style else "Table Grid"
            ))
        return table_rules

    def _extract_headers_footers(self, doc: Document):
        header_spec = HeaderFooterSpec()
        footer_spec = HeaderFooterSpec()

        if doc.sections:
            sec = doc.sections[0]
            if sec.header and not sec.header.is_linked_to_previous:
                h_text = " ".join([p.text for p in sec.header.paragraphs if p.text.strip()])
                header_spec = HeaderFooterSpec(
                    has_content=bool(h_text),
                    text_preview=h_text[:100] if h_text else None,
                    distance_pt=sec.header_distance.pt if sec.header_distance else 36.0,
                    paragraph_count=len(sec.header.paragraphs)
                )

            if sec.footer:
                f_text = " ".join([p.text for p in sec.footer.paragraphs if p.text.strip()])
                # Check for page number XML codes
                has_page_num = False
                for p in sec.footer.paragraphs:
                    if 'PAGE' in p._p.xml:
                        has_page_num = True
                        break

                footer_spec = HeaderFooterSpec(
                    has_content=bool(f_text) or has_page_num,
                    text_preview=f_text[:100] if f_text else None,
                    distance_pt=sec.footer_distance.pt if sec.footer_distance else 36.0,
                    has_page_number=has_page_num,
                    paragraph_count=len(sec.footer.paragraphs)
                )

        return header_spec, footer_spec

    def _extract_numbering(self, doc: Document) -> NumberingSpec:
        has_bullets = False
        has_numbered = False
        for p in doc.paragraphs:
            if p.style and "bullet" in p.style.name.lower():
                has_bullets = True
            if p.style and "number" in p.style.name.lower():
                has_numbered = True

        return NumberingSpec(
            detected=has_bullets or has_numbered,
            has_bullet_lists=has_bullets,
            has_numbered_lists=has_numbered
        )

    def _extract_borders(self, doc: Document) -> Dict[str, BorderSpec]:
        borders: Dict[str, BorderSpec] = {}
        # Paragraph or page borders
        return borders

    def _compute_docx_style_hash(
        self,
        page_spec: PageSpec,
        font_spec: FontSpec,
        styles: Dict[str, StyleSpec],
        header: HeaderFooterSpec,
        footer: HeaderFooterSpec,
        table_rules: Optional[List[TableRuleSpec]] = None
    ) -> str:
        """
        Computes a stable SHA256 hash of all formatting properties.
        Any change to font definitions, margins, page dimensions, or header/footer distance
        will change this hash.
        """
        hash_payload = {
            "page": page_spec.model_dump(),
            "fonts": font_spec.model_dump(),
            "style_names": sorted(list(styles.keys())),
            "header_distance": header.distance_pt,
            "footer_distance": footer.distance_pt
        }
        raw_json = json.dumps(hash_payload, sort_keys=True)
        return hashlib.sha256(raw_json.encode('utf-8')).hexdigest()[:16]
