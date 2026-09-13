from pathlib import Path
from typing import Optional

from .docx_analyzer import DocxAnalyzer
from .pptx_analyzer import PptxAnalyzer
from .pdf_analyzer import PdfAnalyzer
from ..models.template_spec import TemplateSpecification

class TemplateAnalyzer:
    """
    Unified deterministic Template Analyzer.
    Analyzes DOCX, PPTX, and PDF templates and extracts the authoritative TemplateSpecification.
    """

    def __init__(self):
        self.docx_analyzer = DocxAnalyzer()
        self.pptx_analyzer = PptxAnalyzer()
        self.pdf_analyzer = PdfAnalyzer()

    def analyze(self, file_path: str) -> TemplateSpecification:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Template file not found at: {file_path}")

        ext = path.suffix.lower()
        if ext == ".docx":
            return self.docx_analyzer.analyze(file_path)
        elif ext == ".pptx":
            return self.pptx_analyzer.analyze(file_path)
        elif ext == ".pdf":
            return self.pdf_analyzer.analyze(file_path)
        else:
            raise ValueError(f"Unsupported file format '{ext}'. Must be .docx, .pptx, or .pdf")
