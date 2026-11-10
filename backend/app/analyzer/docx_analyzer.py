import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from lxml import etree

from ..models.template_spec import (
    BorderSpec,
    FontSpec,
    HeaderFooterSpec,
    LockStatus,
    MarginSpec,
    NumberingSpec,
    PageSpec,
    ParagraphRuleSpec,
    StyleSpec,
    TableRuleSpec,
    TemplateSpecification,
)


def _xpath_elements(root: etree._Element, expression: str) -> list[etree._Element]:
    results: object = root.xpath(expression)
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, etree._Element)]


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
            table_rules=table_rules,
        )

        # 8. Extract Rules, Guidelines, and Outline from Document Content
        extracted_rules, document_outline, doc_summary = self._extract_rules_and_outline(doc)
        is_inst, typography_rules, body_anchor_idx = self._analyze_institutional_template(
            doc, extracted_rules
        )

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
            lock_status=LockStatus(),
            is_institutional_template=is_inst,
            body_anchor_index=body_anchor_idx,
            parsed_typography_rules=typography_rules,
        )

    def _extract_rules_and_outline(self, doc: DocumentObject):
        """
        Scans the document for internal formatting guidelines, submission rules,
        style requirements, and existing chapter headings/outline using anchored regex.
        """
        rule_anchor_re = re.compile(
            r"^\s*(rule|note|guideline|requirement|instruction|format|font|margin|spacing|style)s?(\s+\w+)?\s*[:\-–]",
            re.IGNORECASE,
        )
        must_format_re = re.compile(
            r"\b(must|shall)\b.*\b(format|font|margin|spacing|size|heading|style|table|figure|page|color|border|citation|ieee)\b",
            re.IGNORECASE,
        )

        extracted_rules: list[str] = []
        document_outline: list[str] = []
        seen_rules: set[str] = set()
        summary_paragraphs: list[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            # Detect headings / outline
            style_name = (p.style.name if p.style else "").strip().lower()
            is_toc_style = style_name == "toc" or style_name.startswith("toc ")
            is_heading = (
                style_name.startswith("heading") or style_name == "title"
            ) and not is_toc_style
            if is_heading and len(text) < 120:
                document_outline.append(text)

            # Detect rule / guideline paragraphs via line-anchored whole-word patterns
            is_rule = bool(rule_anchor_re.search(text) or must_format_re.search(text))
            if is_rule and 8 < len(text) <= 300 and len(extracted_rules) < 12:
                clean_text = " ".join(text.split())
                if clean_text not in seen_rules:
                    seen_rules.add(clean_text)
                    extracted_rules.append(clean_text)

            if len(summary_paragraphs) < 15 and len(text) > 30 and not is_rule:
                summary_paragraphs.append(text[:150])

        doc_summary = " | ".join(summary_paragraphs[:8])
        return extracted_rules, document_outline, doc_summary

    def _analyze_institutional_template(
        self, doc: DocumentObject, extracted_rules: list[str]
    ) -> tuple[bool, dict[str, Any], int | None]:
        """
        Detects institutional / academic report formats (seminar reports, theses, project proposals)
        that have structured front matter (Cover, Certificate, Acknowledgement) and explicit
        typographic guidelines, identifying the body anchor where real chapters begin.
        """
        full_text_paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(full_text_paras)

        has_front_matter = any(
            kw in full_text.upper()
            for kw in [
                "SEMINAR REPORT",
                "PROJECT REPORT",
                "CERTIFICATE",
                "ACKNOWLEDGEMENT",
                "SUBMITTED BY NAME OF STUDENT",
                "GUIDED BY",
                "BONAFIDE WORK",
                "BACHELOR OF TECH",
                "DEPARTMENT OF COMPUTER",
            ]
        )
        has_guidelines = bool(
            re.search(r"font\s+style\s*:", full_text, re.I)
            or re.search(r"line\s+spacing\s*:", full_text, re.I)
            or re.search(r"formatting\s+tips\s*:", full_text, re.I)
            or re.search(r"note:\s*chapter\s*1", full_text, re.I)
        )

        is_institutional = has_front_matter and (has_guidelines or len(doc.sections) > 1)
        if not is_institutional:
            return False, {}, None

        h1_case = "uppercase" if re.search(r"case\s*:\s*uppercase", full_text, re.I) else "normal"

        # Baseline typography rules
        typography_rules = {
            "heading1": {
                "font_name": "Times New Roman",
                "size_pt": 14.0,
                "bold": True,
                "line_spacing": 1.5,
                "spacing_before_pt": 12.0,
                "spacing_after_pt": 6.0,
                "alignment": "center",
                "case": h1_case,
            },
            "heading2": {
                "font_name": "Times New Roman",
                "size_pt": 12.0,
                "bold": True,
                "line_spacing": 1.5,
                "spacing_before_pt": 6.0,
                "spacing_after_pt": 6.0,
                "alignment": "left",
                "case": "titlecase",
            },
            "heading3": {
                "font_name": "Times New Roman",
                "size_pt": 12.0,
                "bold": True,
                "line_spacing": 1.5,
                "spacing_before_pt": 6.0,
                "spacing_after_pt": 6.0,
                "alignment": "left",
                "case": "titlecase",
            },
            "body": {
                "font_name": "Times New Roman",
                "size_pt": 12.0,
                "bold": False,
                "line_spacing": 1.5,
                "spacing_before_pt": 0.0,
                "spacing_after_pt": 6.0,
                "alignment": "justify",
                "case": "sentence",
            },
            "caption": {
                "font_name": "Times New Roman",
                "size_pt": 11.0,
                "bold": False,
                "line_spacing": 1.5,
                "spacing_before_pt": 6.0,
                "spacing_after_pt": 6.0,
                "alignment": "center",
                "case": "sentence",
            },
        }

        # Dynamically refine font if explicitly stated
        font_match = re.search(
            r"(?:font\s+style|style)\s*:\s*([A-Za-z\s]+?)(?:\s*\(|\s+size|\s+spacing|\n|$)",
            full_text,
            re.I,
        )
        if font_match:
            detected_font = font_match.group(1).strip()
            if "times" in detected_font.lower():
                detected_font = "Times New Roman"
            for k in typography_rules:
                typography_rules[k]["font_name"] = detected_font

        # Dynamically refine line spacing if explicitly stated
        ls_match = re.search(r"line\s+spacing\s*:\s*([0-9.]+)", full_text, re.I)
        if ls_match:
            try:
                ls_val = float(ls_match.group(1))
                for k in typography_rules:
                    typography_rules[k]["line_spacing"] = ls_val
            except ValueError:
                pass

        # Locate body anchor index (where Chapter 1 starts)
        body_anchor_idx = None
        for i, p in enumerate(doc.paragraphs):
            t = p.text.strip().upper()
            if re.search(r"NOTE:\s*CHAPTER\s*1\s*WILL\s*START", t, re.I) or t in (
                "INTRODUCTION",
                "1. INTRODUCTION",
                "CHAPTER 1",
                "CHAPTER 1: INTRODUCTION",
            ):
                body_anchor_idx = i
                break

        if body_anchor_idx is None:
            found_prelim = False
            for i, p in enumerate(doc.paragraphs):
                t = p.text.strip().upper()
                if "TABLE OF CONTENT" in t or "ABSTRACT" in t:
                    found_prelim = True
                if found_prelim and p._p.xpath("./w:pPr/w:sectPr"):
                    body_anchor_idx = i + 1
                    break

        return is_institutional, typography_rules, body_anchor_idx

    def _extract_page_spec(self, doc: DocumentObject) -> PageSpec:
        if not doc.sections:
            return PageSpec()

        section = doc.sections[0]

        # Convert EMU or twips to points (1 pt = 12700 EMU, 1 pt = 20 twips)
        width_pt = section.page_width.pt if section.page_width else 612.0
        height_pt = section.page_height.pt if section.page_height else 792.0
        orientation: Literal["portrait", "landscape"] = (
            "landscape" if width_pt > height_pt else "portrait"
        )

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
            columns_count=1,
        )

    def _extract_styles(self, doc: DocumentObject):
        styles_dict: dict[str, StyleSpec] = {}
        all_fonts: set[str] = set()
        heading_styles: list[str] = []
        body_styles: list[str] = []

        heading1_font = None
        heading2_font = None

        for style in doc.styles:
            if style.type not in (WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER):
                continue

            name = style.name
            is_paragraph_style = style.type == WD_STYLE_TYPE.PARAGRAPH
            font_name = None
            font_size = None
            bold = None
            italic = None
            color_hex = None

            if hasattr(style, "font") and style.font:
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
                is_heading=is_heading,
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
                    if s.name.lower() == hs.lower() or (
                        hasattr(s, "style_id") and s.style_id.lower() == clean_id.lower()
                    ):
                        exists = True
                        break
            if exists:
                validated_headings.append(hs)
        heading_styles = validated_headings

        # If no heading paragraph styles were found, leave the list empty.
        # Downstream code (planner, engine) will fall back to bold formatting.
        if not body_styles:
            body_styles = ["Normal"]

        script_fonts = self._extract_script_fonts(doc)
        normal_style = doc.styles["Normal"]
        normal_font = normal_style.font.name
        detected_fallback = min(all_fonts) if all_fonts else None
        default_font = normal_font or script_fonts.ascii_font or detected_fallback
        detected_fonts = all_fonts | {
            font
            for font in (
                script_fonts.ascii_font,
                script_fonts.east_asian_font,
                script_fonts.complex_script_font,
            )
            if font
        }
        font_spec = FontSpec(
            default=default_font,
            body=normal_font or script_fonts.ascii_font or detected_fallback,
            heading1=heading1_font or default_font,
            heading2=heading2_font or default_font,
            ascii_font=script_fonts.ascii_font,
            east_asian_font=script_fonts.east_asian_font,
            complex_script_font=script_fonts.complex_script_font,
            all_detected_fonts=sorted(detected_fonts),
        )

        return styles_dict, font_spec, heading_styles, body_styles

    def _extract_script_fonts(self, doc: DocumentObject) -> FontSpec:
        """Resolve script-specific fonts from Normal, docDefaults, and the theme."""
        theme_fonts: dict[str, str] = {}
        theme_root: etree._Element | None = None
        try:
            theme_part = doc.part.part_related_by(RT.THEME)
            theme_root = etree.fromstring(theme_part.blob)
        except (KeyError, etree.XMLSyntaxError, ValueError):
            theme_root = None

        if theme_root is not None:
            suffixes = {"latin": "HAnsi", "ea": "EastAsia", "cs": "Bidi"}
            for group in ("major", "minor"):
                group_nodes = _xpath_elements(theme_root, f".//*[local-name()='{group}Font']")
                if not group_nodes:
                    continue
                for child_name, suffix in suffixes.items():
                    nodes = _xpath_elements(group_nodes[0], f"./*[local-name()='{child_name}']")
                    if nodes and nodes[0].get("typeface"):
                        theme_fonts[f"{group}{suffix}"] = str(nodes[0].get("typeface"))
                    if child_name == "latin" and nodes and nodes[0].get("typeface"):
                        theme_fonts[f"{group}Ascii"] = str(nodes[0].get("typeface"))

        normal_style = doc.styles["Normal"]
        normal_rpr = normal_style._element.rPr
        normal_fonts = normal_rpr.rFonts if normal_rpr is not None else None
        defaults: list[Any] = doc.styles.element.xpath(
            "./w:docDefaults/w:rPrDefault/w:rPr/w:rFonts"
        )
        default_fonts: Any | None = defaults[0] if defaults else None

        def resolve(direct_names: tuple[str, ...], theme_names: tuple[str, ...]) -> str | None:
            for font_elements in (normal_fonts, default_fonts):
                if font_elements is None:
                    continue
                for name in direct_names:
                    value = font_elements.get(qn(f"w:{name}"))
                    if value:
                        return value
                for name in theme_names:
                    theme_key = font_elements.get(qn(f"w:{name}"))
                    if theme_key and theme_key in theme_fonts:
                        return theme_fonts[theme_key]
            return None

        return FontSpec(
            ascii_font=resolve(("ascii", "hAnsi"), ("asciiTheme", "hAnsiTheme")),
            east_asian_font=resolve(("eastAsia",), ("eastAsiaTheme",)),
            complex_script_font=resolve(("cs",), ("cstheme",)),
        )

    def _extract_paragraph_rules(self, doc: DocumentObject) -> dict[str, ParagraphRuleSpec]:
        rules: dict[str, ParagraphRuleSpec] = {}
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

                space_before = (
                    p.paragraph_format.space_before.pt if p.paragraph_format.space_before else 0.0
                )
                space_after = (
                    p.paragraph_format.space_after.pt if p.paragraph_format.space_after else 6.0
                )
                line_spacing = (
                    p.paragraph_format.line_spacing if p.paragraph_format.line_spacing else 1.15
                )

                keep_with_next = getattr(p.paragraph_format, "keep_with_next", False)
                keep_together = getattr(p.paragraph_format, "keep_together", False)
                widow_control = getattr(p.paragraph_format, "widow_control", True)

                rules[style_name] = ParagraphRuleSpec(
                    alignment=align_str,
                    spacing_before_pt=space_before,
                    spacing_after_pt=space_after,
                    line_spacing=float(line_spacing)
                    if isinstance(line_spacing, (int, float))
                    else 1.15,
                    keep_with_next=bool(keep_with_next),
                    keep_lines_together=bool(keep_together),
                    widow_orphan=bool(widow_control),
                )
        return rules

    def _extract_tables(self, doc: DocumentObject) -> list[TableRuleSpec]:
        table_rules: list[TableRuleSpec] = []
        for idx, table in enumerate(doc.tables):
            col_widths = []
            if table.columns:
                for col in table.columns:
                    col_widths.append(float(col.width.pt) if col.width else 100.0)

            table_rules.append(
                TableRuleSpec(
                    table_index=idx,
                    rows=len(table.rows),
                    cols=len(table.columns) if table.columns else 0,
                    col_widths_pt=col_widths,
                    alignment="center",
                    style_name=table.style.name if table.style else "Table Grid",
                )
            )
        return table_rules

    def _extract_headers_footers(self, doc: DocumentObject):
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
                    paragraph_count=len(sec.header.paragraphs),
                )

            if sec.footer and not sec.footer.is_linked_to_previous:
                f_text = " ".join([p.text for p in sec.footer.paragraphs if p.text.strip()])
                # Check for page number XML codes
                has_page_num = False
                for p in sec.footer.paragraphs:
                    if "PAGE" in p._p.xml:
                        has_page_num = True
                        break

                footer_spec = HeaderFooterSpec(
                    has_content=bool(f_text) or has_page_num,
                    text_preview=f_text[:100] if f_text else None,
                    distance_pt=sec.footer_distance.pt if sec.footer_distance else 36.0,
                    has_page_number=has_page_num,
                    paragraph_count=len(sec.footer.paragraphs),
                )

        return header_spec, footer_spec

    def _extract_numbering(self, doc: DocumentObject) -> NumberingSpec:
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
            has_numbered_lists=has_numbered,
        )

    def _extract_borders(self, doc: DocumentObject) -> dict[str, BorderSpec]:
        borders: dict[str, BorderSpec] = {}
        # Paragraph or page borders
        return borders

    def _compute_docx_style_hash(
        self,
        page_spec: PageSpec,
        font_spec: FontSpec,
        styles: dict[str, StyleSpec],
        header: HeaderFooterSpec,
        footer: HeaderFooterSpec,
        table_rules: list[TableRuleSpec] | None = None,
    ) -> str:
        """
        Computes a stable SHA256 hash of all formatting properties.
        Any change to font definitions, margins, page dimensions, or header/footer distance
        will change this hash.
        """
        hash_payload = {
            "page": page_spec.model_dump(),
            "fonts": font_spec.model_dump(),
            "styles": {k: v.model_dump() for k, v in sorted(styles.items())},
            "header_distance": header.distance_pt,
            "footer_distance": footer.distance_pt,
        }
        raw_json = json.dumps(hash_payload, sort_keys=True)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()[:16]
