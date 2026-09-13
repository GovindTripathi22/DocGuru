from typing import Dict, List, Any, Optional
from pathlib import Path
import pdfplumber

class PdfExtractor:
    """
    Extracts structural information, visual layout, detectable fonts,
    margins, and tables from PDF documents for visual reference and template analysis.
    """

    def __init__(self):
        pass

    def extract_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Extracts pages, text blocks, fonts, tables, and dimensions from a PDF file.
        """
        result: Dict[str, Any] = {
            "total_pages": 0,
            "page_dimensions": [],
            "detected_fonts": set(),
            "font_sizes": set(),
            "tables": [],
            "text_blocks": [],
            "is_reference_only": True,
            "message": "PDF parsed in visual reference mode. For exact 100% editable template inheritance, DOCX/PPTX format is recommended."
        }

        with pdfplumber.open(file_path) as pdf:
            result["total_pages"] = len(pdf.pages)
            
            for page_idx, page in enumerate(pdf.pages):
                page_info = {
                    "page_number": page_idx + 1,
                    "width": float(page.width),
                    "height": float(page.height),
                    "orientation": "landscape" if page.width > page.height else "portrait"
                }
                result["page_dimensions"].append(page_info)

                # Extract words with font info
                try:
                    words = page.extract_words(extra_attrs=["fontname", "size"])
                    for w in words:
                        if "fontname" in w and w["fontname"]:
                            result["detected_fonts"].add(w["fontname"])
                        if "size" in w and w["size"]:
                            result["font_sizes"].add(round(float(w["size"]), 1))
                except Exception:
                    pass

                # Extract tables
                try:
                    tables = page.extract_tables()
                    for t in tables:
                        if t and len(t) > 0:
                            result["tables"].append({
                                "page": page_idx + 1,
                                "rows": len(t),
                                "cols": len(t[0]) if t[0] else 0,
                                "sample_data": t[:3]
                            })
                except Exception:
                    pass

                # Extract plain text
                page_text = page.extract_text()
                if page_text:
                    result["text_blocks"].append({
                        "page": page_idx + 1,
                        "text_sample": page_text[:500]
                    })

        result["detected_fonts"] = sorted(list(result["detected_fonts"]))
        result["font_sizes"] = sorted(list(result["font_sizes"]))
        return result
