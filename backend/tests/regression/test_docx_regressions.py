from docx import Document
import pytest

from backend.app.analyzer.template_analyzer import TemplateAnalyzer
from backend.app.engines.docx_engine import DocxEngine
from backend.app.models.generation import DocumentPlan


def test_create_document_contains_the_requested_title_and_conclusion(minimal_docx, tmp_path):
    spec = TemplateAnalyzer().analyze(str(minimal_docx))
    output = tmp_path / "output.docx"
    plan = DocumentPlan(title="T1", sections=[], conclusion="C1")

    engine = DocxEngine()
    engine.generate_from_plan(engine.load_template(str(minimal_docx), spec), plan, str(output))

    text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
    assert "T1" in text
    assert "C1" in text
