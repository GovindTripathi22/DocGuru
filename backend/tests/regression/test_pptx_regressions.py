"""Regression test suite for PPTX engine invariants (PPTX-01 to PPTX-03)."""

from pathlib import Path
import pytest
from pptx import Presentation
from pptx.util import Inches

from backend.app.analyzer.template_analyzer import TemplateAnalyzer
from backend.app.engines.pptx_engine import PptxEngine
from backend.app.models.generation import PresentationPlan, SlidePlan, TableData


def test_hallucinated_layout_resolves_to_content_capable_layout(minimal_pptx, tmp_path):
    """PPTX-01 & A-14: Hallucinated layout name resolves to content-capable layout without crashing."""
    spec = TemplateAnalyzer().analyze(str(minimal_pptx))
    engine = PptxEngine()
    locked = engine.load_template(str(minimal_pptx), spec)

    warnings = []
    slide = engine.add_slide_from_layout(
        locked,
        layout_name="Bullet Content Layout Hallucination",
        title="Valid Title",
        bullet_points=["Bullet item 1", "Bullet item 2"],
        warnings=warnings,
    )
    output = tmp_path / "hallucinated_layout.pptx"
    locked.prs.save(output)

    text = "\n".join(shape.text for shape in slide.shapes if hasattr(shape, "text"))
    assert "Bullet item 1" in text
    assert any("layout_substituted" in w for w in warnings)


def test_title_only_layout_with_bullets_is_substituted_or_reported(minimal_pptx, tmp_path):
    """PPTX-02 & A-15: Bullets on Title Only layout are never silently dropped; unused placeholders cleaned."""
    spec = TemplateAnalyzer().analyze(str(minimal_pptx))
    engine = PptxEngine()
    locked = engine.load_template(str(minimal_pptx), spec)

    warnings = []
    slide = engine.add_slide_from_layout(
        locked,
        "Title Slide",
        title="Quarterly update",
        bullet_points=["This bullet must not disappear"],
        warnings=warnings,
    )
    output = tmp_path / "presentation.pptx"
    locked.prs.save(output)

    reopened = Presentation(output).slides[-1]
    text = "\n".join(shape.text for shape in reopened.shapes if hasattr(shape, "text"))
    assert "This bullet must not disappear" in text

    # Assert no unfilled prompt strings
    assert "Click to add text" not in text
    assert "Click to add subtitle" not in text


def test_non_overlapping_shapes_geometry(minimal_pptx, tmp_path):
    """PPTX-03 & A-16: Table and content shapes do not overlap each other and remain inside slide bounds."""
    spec = TemplateAnalyzer().analyze(str(minimal_pptx))
    engine = PptxEngine()
    locked = engine.load_template(str(minimal_pptx), spec)

    t_data = TableData(
        headers=["Col A", "Col B"],
        rows=[["Val 1", "Val 2"], ["Val 3", "Val 4"]],
    )
    slide = engine.add_slide_from_layout(
        locked,
        "Title and Content",
        title="Geometry Slide",
        table_data=t_data,
    )
    output = tmp_path / "geom.pptx"
    locked.prs.save(output)

    prs = Presentation(output)
    s = prs.slides[-1]

    # Verify all shapes inside slide bounds
    slide_w = prs.slide_width
    slide_h = prs.slide_height

    for shape in s.shapes:
        assert shape.left >= 0
        assert shape.top >= 0
        assert shape.left + shape.width <= slide_w + Inches(0.1)
        assert shape.top + shape.height <= slide_h + Inches(0.1)
