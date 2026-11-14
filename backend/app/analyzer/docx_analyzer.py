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


INSTRUCTION_PATTERNS = [
    re.compile(
        r"^\s*(?:formatting\s+)?(?:rule|note|guideline|requirement|instruction|tip|format|font|margin|margins|spacing|style|case|alignment|size|paper\s*size|page\s*size|citation|abstract)s?(?:\s+\w+){0,3}\s*[:\-–]",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:font\s+style|font\s+family|font\s+name|font\s+size|line\s+spacing|spacing\s+before|spacing\s+after|formatting\s+tips?|sub\s*heading\s*\d*\s*formatting|page\s+margins?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:for\s+giving\s+long\s+space|do\s+not\s+use\s+space\s+bar|chapter\s*1\s*will\s*start|pages?\s+till\s+index|all\s+content\s+font\s+size|heading\s+should\s+be|numbered\s+in\s+roman|required\s+sections?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:size\s*:\s*-?\s*\d+|style\s*:\s*(?:times\s+new\s+roman|arial|calibri|aptos|cambria|georgia)|case\s*:\s*(?:upper|lower|title|sentence)|re\s*&\s*after)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:must|shall|should)\b.*\b(?:times\s+new\s+roman|arial|calibri|aptos|cambria|georgia|verdana|font|margin|margins|spacing|size|heading|justified|centered|left\s+aligned|uppercase|roman\s+numeral|ieee|apa|a4|letter)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*[\(\[]\s*(?:font|size|bold|italic|times\s+new\s+roman|arial|calibri|write\s+approx|enter\s+|insert\s+|approx\.?\s*\d+\s*words).*[\)\]]\s*$",
        re.IGNORECASE,
    ),
]

KNOWN_FONT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btimes\s+new\s+roman\b", re.I), "Times New Roman"),
    (re.compile(r"\baptos\s+display\b", re.I), "Aptos Display"),
    (re.compile(r"\baptos\b", re.I), "Aptos"),
    (re.compile(r"\barial\b", re.I), "Arial"),
    (re.compile(r"\bcalibri\b", re.I), "Calibri"),
    (re.compile(r"\bcambria\b", re.I), "Cambria"),
    (re.compile(r"\bgeorgia\b", re.I), "Georgia"),
    (re.compile(r"\bverdana\b", re.I), "Verdana"),
    (re.compile(r"\btahoma\b", re.I), "Tahoma"),
    (re.compile(r"\bgaramond\b", re.I), "Garamond"),
    (re.compile(r"\btrebuchet\s+ms\b", re.I), "Trebuchet MS"),
    (re.compile(r"\bbook\s+antiqua\b", re.I), "Book Antiqua"),
    (re.compile(r"\bcourier\s+new\b", re.I), "Courier New"),
    (re.compile(r"\bhelvetica\b", re.I), "Helvetica"),
]


def is_instruction_or_rule_paragraph(text: str) -> bool:
    """Return True if the paragraph text is an embedded formatting rule, tip, or template instruction."""
    clean = " ".join(text.strip().split())
    if not clean or len(clean) > 450:
        return False
    return any(pattern.search(clean) for pattern in INSTRUCTION_PATTERNS)


def _detect_font_in_text(text: str) -> str | None:
    for pat, canonical in KNOWN_FONT_PATTERNS:
        if pat.search(text):
            return canonical
    font_match = re.search(
        r"(?:font\s+(?:style|family|name)|typeface|font)\s*[:\-]\s*([A-Za-z][A-Za-z\s]{1,30}?)(?:\s*\(|\s*,|\s*;|\s+font|\s+size|\s+spacing|\n|$)",
        text,
        re.I,
    )
    if font_match:
        cand = font_match.group(1).strip()
        if 2 <= len(cand) <= 32 and cand.lower() not in {"size", "style", "color", "must", "should"}:
            return cand
    return None


def _detect_alignment_in_text(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\bjustif(?:y|ied)\b|\bboth\b(?=\s+align)", low):
        return "justify"
    if re.search(r"\bcent(?:er|re|ered|red)\b", low):
        return "center"
    if re.search(r"\bright[\s\-]+align(?:ed)?\b|\balign\s*[:\-]\s*right\b", low):
        return "right"
    if re.search(r"\bleft[\s\-]+align(?:ed)?\b|\balign\s*[:\-]\s*left\b", low):
        return "left"
    return None


def _detect_line_spacing_in_text(text: str) -> float | None:
    low = text.lower()
    if re.search(r"\bdouble[\s\-]*(?:line\s*)?spac(?:ed|ing)\b", low):
        return 2.0
    if re.search(r"\bsingle[\s\-]*(?:line\s*)?spac(?:ed|ing)\b", low):
        return 1.0
    m = re.search(
        r"(?:line\s+spacing|spacing)\s*(?:should\s+be|must\s+be|of|is|=|:|-)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:x|lines?)?",
        low,
    )
    if m:
        try:
            val = float(m.group(1))
            if 1.0 <= val <= 3.0:
                return val
        except ValueError:
            pass
    m2 = re.search(r"\b(1\.0|1\.15|1\.25|1\.5|2\.0)\s*(?:line\s*spacing|spacing)\b", low)
    if m2:
        return float(m2.group(1))
    return None


def _to_inches(value: float, unit: str | None) -> float:
    u = (unit or "in").lower()
    if u.startswith("cm"):
        return round(value / 2.54, 3)
    if u.startswith("mm"):
        return round(value / 25.4, 3)
    if u.startswith("pt"):
        return round(value / 72.0, 3)
    return round(value, 3)


def parse_document_rules_from_lines(
    lines: list[str],
    *,
    default_font: str = "Times New Roman",
    is_institutional: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], list[str], bool]:
    """
    Parse explicit formatting and structural rules written inside document instructions.
    Returns: (typography_rules, structural_rules, rule_categories, has_explicit_overrides).
    """
    rule_lines = [line.strip() for line in lines if line and is_instruction_or_rule_paragraph(line)]
    full_rule_text = "\n".join(rule_lines)
    has_explicit_rules = len(rule_lines) > 0

    base_ls = 1.5 if is_institutional else 1.15
    base_body_align = "justify" if is_institutional else "left"
    base_h1_align = "center" if is_institutional else "left"
    base_h1_case = (
        "uppercase"
        if (
            re.search(r"case\s*:\s*uppercase|all\s+caps|capital", full_rule_text, re.I)
            or (is_institutional and any(re.search(r"CHAPTER\s*1|1\.\s*INTRODUCTION", l) for l in lines))
        )
        else "normal"
    )

    typography_rules: dict[str, Any] = {
        "heading1": {
            "font_name": default_font,
            "size_pt": 14.0 if is_institutional else 16.0,
            "bold": True,
            "italic": False,
            "line_spacing": base_ls,
            "spacing_before_pt": 12.0,
            "spacing_after_pt": 6.0,
            "alignment": base_h1_align,
            "case": base_h1_case,
        },
        "heading2": {
            "font_name": default_font,
            "size_pt": 12.0 if is_institutional else 13.0,
            "bold": True,
            "italic": False,
            "line_spacing": base_ls,
            "spacing_before_pt": 6.0,
            "spacing_after_pt": 6.0,
            "alignment": "left",
            "case": "titlecase" if is_institutional else "normal",
        },
        "heading3": {
            "font_name": default_font,
            "size_pt": 12.0,
            "bold": True,
            "italic": False,
            "line_spacing": base_ls,
            "spacing_before_pt": 6.0,
            "spacing_after_pt": 4.0,
            "alignment": "left",
            "case": "normal",
        },
        "body": {
            "font_name": default_font,
            "size_pt": 12.0 if is_institutional else 11.0,
            "bold": False,
            "italic": False,
            "line_spacing": base_ls,
            "spacing_before_pt": 0.0,
            "spacing_after_pt": 6.0,
            "alignment": base_body_align,
            "case": "sentence",
        },
        "caption": {
            "font_name": default_font,
            "size_pt": 11.0 if is_institutional else 10.0,
            "bold": False,
            "italic": True,
            "line_spacing": base_ls,
            "spacing_before_pt": 6.0,
            "spacing_after_pt": 6.0,
            "alignment": "center",
            "case": "sentence",
        },
    }

    structural_rules: dict[str, Any] = {}
    categories: list[str] = []
    explicit_font_found = False

    # Parse global font first if mentioned on a general font rule
    for line in rule_lines:
        low = line.lower()
        is_role_specific = any(
            k in low for k in ("heading", "chapter", "title", "sub", "caption", "figure", "table", "body", "content", "paragraph")
        )
        font = _detect_font_in_text(line)
        if font and not is_role_specific:
            explicit_font_found = True
            for role in typography_rules:
                typography_rules[role]["font_name"] = font
            if "Typography" not in categories:
                categories.append("Typography")

    for line in rule_lines:
        low = line.lower()
        roles_targeted: list[str] = []
        if any(k in low for k in ("sub heading", "subheading", "heading 2", "h2", "sub-heading")):
            roles_targeted.append("heading2")
        elif any(k in low for k in ("heading 3", "h3")):
            roles_targeted.append("heading3")
        elif any(k in low for k in ("heading", "chapter", "title")):
            roles_targeted.append("heading1")
        if any(k in low for k in ("caption", "figure", "table caption")):
            roles_targeted.append("caption")
        if any(k in low for k in ("body", "content", "paragraph", "prose", "text", "abstract")):
            roles_targeted.append("body")
        if not roles_targeted:
            # General formatting rule applies font/spacing broadly
            roles_targeted = ["heading1", "heading2", "heading3", "body", "caption"]

        font = _detect_font_in_text(line)
        if font:
            explicit_font_found = True
            for role in roles_targeted:
                typography_rules[role]["font_name"] = font
            if "Typography" not in categories:
                categories.append("Typography")

        # Font sizes and alignments per comma/semicolon clause (avoids assigning body pt to headings in mixed sentences)
        for clause in [c.strip() for c in re.split(r"[,;]+", low) if c.strip()]:
            c_roles: list[str] = []
            c_h2 = any(k in clause for k in ("sub heading", "subheading", "heading 2", "h2", "sub-heading"))
            c_h3 = any(k in clause for k in ("heading 3", "h3"))
            c_h1 = not c_h2 and not c_h3 and any(k in clause for k in ("heading", "chapter", "title"))
            c_cap = any(k in clause for k in ("caption", "figure", "table caption"))
            c_body = any(k in clause for k in ("body", "content", "paragraph", "prose", "text", "abstract"))

            if c_h2:
                c_roles.append("heading2")
            elif c_h3:
                c_roles.append("heading3")
            elif c_h1 and c_body:
                pt_m = re.search(r"\d+(?:\.\d+)?\s*pt\b", clause)
                b_m = re.search(r"\b(?:body|content|paragraph|prose|text|abstract)\b", clause)
                h_m = re.search(r"\b(?:heading|chapter|title)\b", clause)
                if pt_m and b_m and h_m:
                    c_roles.append("body" if abs(pt_m.start() - b_m.start()) <= abs(pt_m.start() - h_m.start()) else "heading1")
                elif b_m and h_m and b_m.start() <= h_m.start():
                    c_roles.append("body")
                else:
                    c_roles.append("heading1")
            elif c_h1:
                c_roles.append("heading1")
            if c_cap and not c_h1 and not c_body:
                c_roles.append("caption")
            if c_body and "body" not in c_roles and not c_h1:
                c_roles.append("body")

            pt_matches = [float(m.group(1)) for m in re.finditer(r"(\d+(?:\.\d+)?)\s*pt\b", clause)]
            if not pt_matches:
                sz_m = re.search(
                    r"(?:for\s+all\s+content\s+font\s+size|font\s+size|size)\s*[:\-–]*\s*(\d{1,2}(?:\.\d+)?)\b",
                    clause,
                )
                if sz_m:
                    pt_matches = [float(sz_m.group(1))]
            if pt_matches:
                sz = pt_matches[0]
                if 8.0 <= sz <= 48.0:
                    target_roles = c_roles if c_roles else (roles_targeted if len(roles_targeted) < 5 else ["body"])
                    for role in target_roles:
                        if role in typography_rules:
                            typography_rules[role]["size_pt"] = sz
                    if "Font Size" not in categories:
                        categories.append("Font Size")

            align = _detect_alignment_in_text(clause)
            if align:
                target_roles = c_roles if c_roles else (roles_targeted if len(roles_targeted) < 5 else ["body"])
                for role in target_roles:
                    if role in typography_rules:
                        typography_rules[role]["alignment"] = align
                if "Alignment" not in categories:
                    categories.append("Alignment")

        ls = _detect_line_spacing_in_text(line)
        if ls is not None:
            for role in roles_targeted:
                if role in typography_rules:
                    typography_rules[role]["line_spacing"] = ls
            if "Line Spacing" not in categories:
                categories.append("Line Spacing")

        if "heading1" in roles_targeted:
            if re.search(r"\b(?:uppercase|upper\s*case|all\s*caps|capital(?:s|ized)?)\b", low):
                typography_rules["heading1"]["case"] = "uppercase"
            elif re.search(r"\btitle\s*case\b", low):
                typography_rules["heading1"]["case"] = "titlecase"
            elif re.search(r"\bsentence\s*case|normal\s*case\b", low):
                typography_rules["heading1"]["case"] = "normal"

        if "bold" in low and "not bold" not in low:
            for role in roles_targeted:
                if role != "body" or "body" in low or "all" in low:
                    typography_rules[role]["bold"] = True

        # Margins
        side_margins: dict[str, float] = {}
        for side in ("top", "bottom", "left", "right"):
            sm = re.search(
                rf"\b{side}\s*(?:margin)?\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*(inches?|in|\"|cm|mm|pt)?\b",
                low,
            )
            if sm and ("margin" in low or sm.group(2)):
                val = _to_inches(float(sm.group(1)), sm.group(2))
                if 0.25 <= val <= 3.0:
                    side_margins[side] = val
        if side_margins:
            margins_obj = structural_rules.setdefault("margins_in", {})
            margins_obj.update(side_margins)
            if "Margins" not in categories:
                categories.append("Margins")
        elif "margin" in low:
            gm = re.search(
                r"margins?\s*(?:of|should\s+be|must\s+be|:|-)?\s*(\d+(?:\.\d+)?)\s*(inches?|in|\"|cm|mm|pt)?",
                low,
            )
            if gm:
                val = _to_inches(float(gm.group(1)), gm.group(2))
                if 0.25 <= val <= 3.0:
                    structural_rules["margins_in"] = {
                        "top": val,
                        "bottom": val,
                        "left": val,
                        "right": val,
                    }
                    if "Margins" not in categories:
                        categories.append("Margins")

        # Paper size
        if re.search(r"\ba4\b", low):
            structural_rules["page_size"] = "A4"
            if "Page Size" not in categories:
                categories.append("Page Size")
        elif re.search(r"\blegal\b", low):
            structural_rules["page_size"] = "Legal"
            if "Page Size" not in categories:
                categories.append("Page Size")
        elif re.search(r"\bletter\b", low) and ("size" in low or "paper" in low or "page" in low):
            structural_rules["page_size"] = "Letter"
            if "Page Size" not in categories:
                categories.append("Page Size")

        # Citations / tables / sections
        if re.search(r"\bieee\b", low):
            structural_rules["citation_style"] = "IEEE"
            if "Citations" not in categories:
                categories.append("Citations")
        elif re.search(r"\bapa\b", low):
            structural_rules["citation_style"] = "APA"
            if "Citations" not in categories:
                categories.append("Citations")
        elif re.search(r"bracketed\s+numeric|\[\d+\]", low):
            structural_rules["citation_style"] = "numeric"
            if "Citations" not in categories:
                categories.append("Citations")

        if "table" in low:
            structural_rules["require_tables"] = True

        req_sec_m = re.search(
            r"(?:required\s+sections?|must\s+include\s+(?:sections?|chapters?)|chapters?)\s*[:\-]\s*(.+)$",
            line,
            re.I,
        )
        if req_sec_m:
            raw_items = [
                item.strip(" .;:")
                for item in re.split(r"[,;|]", req_sec_m.group(1))
                if 2 <= len(item.strip(" .;:")) <= 80
            ]
            if raw_items:
                structural_rules["required_sections"] = raw_items
                if "Structure" not in categories:
                    categories.append("Structure")

    if not explicit_font_found and default_font:
        for role in typography_rules:
            typography_rules[role]["font_name"] = default_font

    return typography_rules, structural_rules, categories, has_explicit_rules


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
        (
            is_inst,
            typography_rules,
            body_anchor_idx,
            has_embedded_rules,
            detected_categories,
            structural_rules,
        ) = self._analyze_institutional_template(doc, extracted_rules)

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
            has_embedded_rules=has_embedded_rules,
            detected_rule_categories=detected_categories,
            parsed_structural_rules=structural_rules,
        )

    def _extract_rules_and_outline(self, doc: DocumentObject):
        """
        Scans the document (paragraphs, tables, and textboxes) for internal formatting guidelines,
        submission rules, style requirements, and existing chapter headings/outline.
        """
        rule_anchor_re = re.compile(
            r"^\s*(rule|note|guideline|requirement|instruction|format|font|margin|margins|spacing|style|paper\s*size|page\s*size)s?(\s+\w+)?\s*[:\-–]",
            re.IGNORECASE,
        )
        must_format_re = re.compile(
            r"\b(must|shall|should)\b.*\b(format|font|margin|margins|spacing|size|heading|style|table|figure|page|color|border|citation|ieee|apa|justified|centered|uppercase)\b",
            re.IGNORECASE,
        )

        extracted_rules: list[str] = []
        document_outline: list[str] = []
        seen_rules: set[str] = set()
        summary_paragraphs: list[str] = []

        def collect_rule(text: str) -> bool:
            is_rule = bool(
                rule_anchor_re.search(text)
                or must_format_re.search(text)
                or is_instruction_or_rule_paragraph(text)
            )
            if is_rule and 8 < len(text) <= 350 and len(extracted_rules) < 12:
                clean_text = " ".join(text.split())
                if clean_text not in seen_rules:
                    seen_rules.add(clean_text)
                    extracted_rules.append(clean_text)
            return is_rule

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            is_rule = collect_rule(text)

            # Detect headings / outline (excluding TOC styles and instruction lines)
            style_name = (p.style.name if p.style else "").strip().lower()
            is_toc_style = style_name == "toc" or style_name.startswith("toc ")
            is_heading = (
                style_name.startswith("heading") or style_name == "title"
            ) and not is_toc_style
            if is_heading and len(text) < 120 and not is_rule:
                document_outline.append(text)

            if len(summary_paragraphs) < 15 and len(text) > 30 and not is_rule:
                summary_paragraphs.append(text[:150])

        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for line in cell.text.splitlines():
                        clean = line.strip()
                        if clean:
                            collect_rule(clean)

        for node in doc._body._body.xpath(".//w:txbxContent"):
            for p_elem in node.xpath(".//w:p"):
                txt = "".join(p_elem.xpath(".//w:t/text()")).strip()
                if txt:
                    collect_rule(txt)

        doc_summary = " | ".join(summary_paragraphs[:8])
        return extracted_rules, document_outline, doc_summary

    def _analyze_institutional_template(
        self, doc: DocumentObject, extracted_rules: list[str]
    ) -> tuple[bool, dict[str, Any], int | None, bool, list[str], dict[str, Any]]:
        """
        Detects institutional / academic report formats (seminar reports, theses, project proposals)
        AND parses explicit written rules (typography, alignments, margins, page size, structure)
        for ANY document that contains written instructions.
        """
        full_text_paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        table_texts = [
            line.strip()
            for tbl in doc.tables
            for row in tbl.rows
            for cell in row.cells
            for line in cell.text.splitlines()
            if line.strip()
        ]
        txbx_texts = [
            " ".join(t.strip() for t in node.itertext() if t.strip())
            for node in doc._body._body.xpath(".//w:txbxContent")
        ]
        all_lines = [*full_text_paras, *table_texts, *txbx_texts, *extracted_rules]
        full_text = "\n".join(all_lines)
        upper_text = full_text.upper()

        front_matter_keywords = [
            "SEMINAR REPORT",
            "PROJECT REPORT",
            "TECHNICAL REPORT",
            "INTERNSHIP REPORT",
            "DISSERTATION",
            "THESIS",
            "CERTIFICATE",
            "DECLARATION",
            "ACKNOWLEDGEMENT",
            "SUBMITTED BY",
            "NAME OF STUDENT",
            "GUIDED BY",
            "UNDER THE GUIDANCE OF",
            "BONAFIDE WORK",
            "BACHELOR OF",
            "MASTER OF",
            "DEPARTMENT OF",
        ]
        matched_front_kw = sum(1 for kw in front_matter_keywords if kw in upper_text)
        has_prelim_sections = (
            "ABSTRACT" in upper_text
            or "TABLE OF CONTENT" in upper_text
            or "ACKNOWLEDGEMENT" in upper_text
            or "CERTIFICATE" in upper_text
        )

        is_institutional = (matched_front_kw >= 2) or (
            matched_front_kw >= 1 and (has_prelim_sections or len(doc.sections) > 1)
        )

        normal_font = doc.styles["Normal"].font.name if "Normal" in doc.styles else None
        default_font = "Times New Roman" if is_institutional else (normal_font or "Calibri")

        typography_rules, structural_rules, rule_categories, has_explicit_rules = (
            parse_document_rules_from_lines(
                all_lines,
                default_font=default_font,
                is_institutional=is_institutional,
            )
        )
        has_embedded_rules = has_explicit_rules or len(extracted_rules) > 0

        if not is_institutional:
            return (
                False,
                typography_rules if has_embedded_rules else {},
                None,
                has_embedded_rules,
                rule_categories,
                structural_rules if has_embedded_rules else {},
            )

        # Locate preliminary front-matter end so we don't mistake a TOC entry for the Chapter 1 body anchor
        last_prelim_idx = -1
        for i, p in enumerate(doc.paragraphs):
            t_up = " ".join(p.text.strip().upper().split())
            if t_up in (
                "CERTIFICATE",
                "DECLARATION",
                "ACKNOWLEDGEMENT",
                "ACKNOWLEDGEMENTS",
                "ABSTRACT",
                "TABLE OF CONTENT",
                "TABLE OF CONTENTS",
                "CONTENTS",
                "INDEX",
                "LIST OF FIGURES",
                "LIST OF TABLES",
                "ABBREVIATIONS",
                "NOMENCLATURE",
            ):
                last_prelim_idx = i

        body_anchor_idx = None
        search_start = max(0, last_prelim_idx + 1)

        for i in range(search_start, len(doc.paragraphs)):
            p = doc.paragraphs[i]
            t = " ".join(p.text.strip().split())
            t_up = t.upper()
            style_name = (p.style.name if p.style else "").strip().lower()
            if style_name.startswith("toc") or re.search(r"\.{3,}\s*\d+$|\t\d+$", t):
                continue

            if re.search(r"NOTE:\s*CHAPTER\s*1\s*WILL\s*START", t_up, re.I) or re.match(
                r"^(?:CHAPTER\s*[-–:]?\s*(?:1|01|I|ONE)\b(?:\s*[:\-–]?\s*INTRODUCTION)?|(?:1\.?\s+|1\.0\s+)?INTRODUCTION)$",
                t_up,
            ):
                body_anchor_idx = i
                break

        # Fallback: scan entire paragraph list if not found after prelim
        if body_anchor_idx is None:
            for i, p in enumerate(doc.paragraphs):
                t_up = " ".join(p.text.strip().upper().split())
                if re.search(r"NOTE:\s*CHAPTER\s*1\s*WILL\s*START", t_up, re.I) or t_up in (
                    "INTRODUCTION",
                    "1. INTRODUCTION",
                    "1.INTRODUCTION",
                    "CHAPTER 1",
                    "CHAPTER 1: INTRODUCTION",
                    "CHAPTER - 1",
                ):
                    body_anchor_idx = i
                    break

        if body_anchor_idx is None and last_prelim_idx >= 0:
            for i in range(last_prelim_idx, len(doc.paragraphs)):
                if doc.paragraphs[i]._p.xpath("./w:pPr/w:sectPr"):
                    body_anchor_idx = min(i + 1, len(doc.paragraphs) - 1)
                    break

        return (
            is_institutional,
            typography_rules,
            body_anchor_idx,
            has_embedded_rules,
            rule_categories,
            structural_rules,
        )

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
