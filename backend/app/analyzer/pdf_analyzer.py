from typing import Dict, List, Any, Optional
import hashlib
import json
from pathlib import Path

from ..engines.pdf_extractor import PdfExtractor
from ..models.template_spec import (
    TemplateSpecification,
    PageSpec,
    MarginSpec,
    FontSpec,
    TableRuleSpec,
    LockStatus,
)

class PdfAnalyzer:
    """
    Template analyzer for PDF files (Visual Reference Mode).
    """

    def __init__(self):
        self.extractor = PdfExtractor()

    def analyze(self, file_path: str) -> TemplateSpecification:
        filename = Path(file_path).name
        extracted = self.extractor.extract_structure(file_path)

        # Build PageSpec from first page dimensions
        first_page = extracted["page_dimensions"][0] if extracted["page_dimensions"] else {"width": 612.0, "height": 792.0, "orientation": "portrait"}
        page_spec = PageSpec(
            width_pt=first_page["width"],
            height_pt=first_page["height"],
            orientation=first_page["orientation"],
            margins=MarginSpec()
        )

        font_spec = FontSpec(
            default="Arial",
            body="Arial",
            all_detected_fonts=extracted["detected_fonts"]
        )

        table_rules = [
            TableRuleSpec(
                table_index=idx,
                rows=t["rows"],
                cols=t["cols"],
                alignment="center"
            )
            for idx, t in enumerate(extracted["tables"])
        ]

        style_hash = hashlib.sha256(
            json.dumps({
                "page": page_spec.model_dump(),
                "fonts": font_spec.model_dump(),
                "total_pages": extracted["total_pages"]
            }, sort_keys=True).encode('utf-8')
        ).hexdigest()[:16]

        return TemplateSpecification(
            filename=filename,
            document_type="pdf",
            total_pages_or_slides=extracted["total_pages"],
            page=page_spec,
            fonts=font_spec,
            table_rules=table_rules,
            style_hash=style_hash,
            lock_status=LockStatus()
        )
