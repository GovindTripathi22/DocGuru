"""Deterministic list style resolution conforming to DOCX-02."""

import logging
from typing import Dict, List, Optional, Tuple
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)


class ListStyleResolver:
    def __init__(self, doc: Document):
        self.doc = doc
        self.available_styles = {s.name.lower(): s.name for s in doc.styles}
        self.sorted_style_names = sorted(s.name for s in doc.styles)
        self.bullet_num_id, self.number_num_id = self._inspect_numbering_part()

    def _inspect_numbering_part(self) -> Tuple[Optional[str], Optional[str]]:
        """Scans numbering.xml if present to identify real bullet and decimal numIds."""
        bullet_id = None
        decimal_id = None
        try:
            num_part = self.doc.part.numbering_part
            if not num_part:
                return None, None
            tree = num_part._element
            # Find num elements and their abstractNumId references
            for num in tree.xpath(".//w:num"):
                n_id = num.get(qn("w:numId"))
                abs_id_elem = num.find(qn("w:abstractNumId"))
                if abs_id_elem is None:
                    continue
                abs_id = abs_id_elem.get(qn("w:val"))
                # Check abstractNum definition
                abs_num = tree.xpath(f".//w:abstractNum[@w:abstractNumId='{abs_id}']")
                if abs_num:
                    num_fmt = abs_num[0].xpath(".//w:numFmt")
                    if num_fmt:
                        val = num_fmt[0].get(qn("w:val"))
                        if val == "bullet" and bullet_id is None:
                            bullet_id = n_id
                        elif val in ("decimal", "upperRoman", "lowerRoman") and decimal_id is None:
                            decimal_id = n_id
        except Exception:
            pass
        return bullet_id, decimal_id

    def resolve_bullet_style(self, level: int = 0) -> Tuple[Optional[str], bool]:
        """
        Resolves bullet candidate in strict priority:
        1. List Bullet / List Bullet 2 / List Bullet 3 by level
        2. Any paragraph style in template matching 'bullet'
        3. List Paragraph (with direct numPr)
        4. Fallback (hanging-indent) -> returns (None, True)
        """
        # 1. Exact candidate by level
        level_suffix = f" {level + 1}" if level > 0 else ""
        candidates = [
            f"List Bullet{level_suffix}",
            f"ListBullet{level_suffix}",
            "List Bullet",
            "ListBullet",
        ]
        for c in candidates:
            if c.lower() in self.available_styles:
                return self.available_styles[c.lower()], False

        # 2. Any style containing 'bullet' in name (sorted for determinism)
        for s_name in self.sorted_style_names:
            if "bullet" in s_name.lower():
                return s_name, False

        # 3. List Paragraph
        if "list paragraph" in self.available_styles:
            return self.available_styles["list paragraph"], False

        # 4. Fallback
        return None, True

    def apply_bullet(
        self,
        paragraph: Paragraph,
        text: str,
        level: int = 0,
        warnings: Optional[List[str]] = None,
    ) -> None:
        style_name, is_fallback = self.resolve_bullet_style(level)

        if style_name and not is_fallback:
            try:
                paragraph.style = self.doc.styles[style_name]
                paragraph.text = text
                if level > 0 and hasattr(paragraph.paragraph_format, "left_indent"):
                    # Add subtle indentation per level if not defined by style
                    pass
                return
            except Exception:
                pass

        if self.bullet_num_id:
            # Apply direct numPr referencing verified bullet numId
            try:
                pPr = paragraph._p.get_or_add_pPr()
                numPr = OxmlElement("w:numPr")
                ilvl = OxmlElement("w:ilvl")
                ilvl.set(qn("w:val"), str(level))
                numId = OxmlElement("w:numId")
                numId.set(qn("w:val"), str(self.bullet_num_id))
                numPr.append(ilvl)
                numPr.append(numId)
                pPr.append(numPr)
                paragraph.text = text
                return
            except Exception:
                pass

        # Last resort: hanging-indent paragraph with bullet character
        if warnings is not None:
            warnings.append("list_style_fallback")
        indent_spaces = "  " * level
        paragraph.text = f"{indent_spaces}• {text}"
