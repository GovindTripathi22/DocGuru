import pytest
from pptx import Presentation

from backend.app.analyzer.template_analyzer import TemplateAnalyzer
from backend.app.engines.pptx_engine import PptxEngine


def test_title_only_layout_with_bullets_is_substituted_or_reported(minimal_pptx, tmp_path):
    spec = TemplateAnalyzer().analyze(str(minimal_pptx))
    engine = PptxEngine()
    locked = engine.load_template(str(minimal_pptx), spec)

    engine.add_slide_from_layout(
        locked,
        "Title Slide",
        title="Quarterly update",
        bullet_points=["This bullet must not disappear"],
    )
    output = tmp_path / "presentation.pptx"
    locked.prs.save(output)

    slide = Presentation(output).slides[-1]
    text = "\n".join(shape.text for shape in slide.shapes if hasattr(shape, "text"))
    assert "This bullet must not disappear" in text
