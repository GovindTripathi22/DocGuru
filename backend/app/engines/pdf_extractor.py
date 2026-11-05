import logging
from collections import Counter
from typing import Any

import pdfplumber

logger = logging.getLogger(__name__)


class PdfExtractor:
    """
    Extracts structural information, visual layout, detectable fonts,
    margins, and tables from PDF documents for visual reference and template analysis.
    """

    def __init__(self):
        pass

    def extract_structure(self, file_path: str) -> dict[str, Any]:
        """
        Extracts pages, text blocks, fonts, tables, and dimensions from a PDF file.
        """
        result: dict[str, Any] = {
            "total_pages": 0,
            "page_dimensions": [],
            "detected_fonts": set(),
            "font_counts": Counter(),
            "font_sizes": set(),
            "tables": [],
            "text_blocks": [],
            "is_reference_only": True,
            "message": "PDF parsed in visual reference mode. For exact 100% editable template inheritance, DOCX/PPTX format is recommended.",
        }

        with pdfplumber.open(file_path) as pdf:
            result["total_pages"] = len(pdf.pages)

            for page_idx, page in enumerate(pdf.pages):
                page_info = {
                    "page_number": page_idx + 1,
                    "width": float(page.width),
                    "height": float(page.height),
                    "orientation": "landscape" if page.width > page.height else "portrait",
                }
                result["page_dimensions"].append(page_info)

                # Extract words with font info
                try:
                    words = page.extract_words(extra_attrs=["fontname", "size"])
                    for w in words:
                        if w.get("fontname"):
                            result["detected_fonts"].add(w["fontname"])
                            result["font_counts"][w["fontname"]] += 1
                        if w.get("size"):
                            result["font_sizes"].add(round(float(w["size"]), 1))
                except (KeyError, TypeError, ValueError) as exc:
                    logger.warning(
                        "Could not read PDF word font metadata on page %s: %s", page_idx + 1, exc
                    )

                # Extract tables
                try:
                    tables = page.extract_tables()
                    for t in tables:
                        if t and len(t) > 0:
                            result["tables"].append(
                                {
                                    "page": page_idx + 1,
                                    "rows": len(t),
                                    "cols": len(t[0]) if t[0] else 0,
                                    "sample_data": t[:3],
                                }
                            )
                except (IndexError, TypeError, ValueError) as exc:
                    logger.warning("Could not extract PDF tables on page %s: %s", page_idx + 1, exc)

                # Extract plain text
                page_text = page.extract_text()
                if page_text:
                    result["text_blocks"].append(
                        {"page": page_idx + 1, "text_sample": page_text[:500]}
                    )

        result["detected_fonts"] = sorted(result["detected_fonts"])
        result["font_sizes"] = sorted(result["font_sizes"])
        result["dominant_font"] = (
            result["font_counts"].most_common(1)[0][0] if result["font_counts"] else None
        )
        result["font_counts"] = dict(result["font_counts"])
        return result
