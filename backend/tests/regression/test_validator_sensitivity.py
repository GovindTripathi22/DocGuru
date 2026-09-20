from docx import Document
from docx.shared import Pt, RGBColor
import pytest

from backend.app.analyzer.template_analyzer import TemplateAnalyzer
from backend.app.validation.diff_validator import DiffValidator


def test_heading_style_mutation_fails_validation(minimal_docx, tmp_path):
    original = TemplateAnalyzer().analyze(str(minimal_docx))
    mutated = tmp_path / "mutated.docx"
    document = Document(minimal_docx)
    style = document.styles["Title"]
    style.font.size = Pt(48)
    style.font.bold = True
    style.font.color.rgb = RGBColor(255, 0, 0)
    document.save(mutated)

    report = DiffValidator().validate(original, str(mutated))
    assert report.passed is False
