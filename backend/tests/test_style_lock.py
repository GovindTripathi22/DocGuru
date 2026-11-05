import pytest

from backend.app.engines.style_lock import StyleLock, StyleLockViolationError


def test_style_lock_blocks_arbitrary_formatting():
    # Attempting to specify font size should be blocked
    with pytest.raises(StyleLockViolationError):
        StyleLock.assert_content_only({"content": "Sample text", "font_size": 14})

    # Attempting to specify custom color should be blocked
    with pytest.raises(StyleLockViolationError):
        StyleLock.assert_content_only({"content": "Sample text", "font_color": "#FF0000"})

    # Attempting to override margins should be blocked
    with pytest.raises(StyleLockViolationError):
        StyleLock.assert_content_only({"content": "Sample text", "margin_top": 2.0})


def test_style_lock_permits_content_operations():
    # Pure content operations must pass cleanly
    StyleLock.assert_content_only({"style": "Heading 1", "content": "Valid Section Title"})

    StyleLock.assert_content_only(
        {
            "layout_name": "Title and Content",
            "title": "Valid Presentation Slide Title",
            "bullet_points": ["Point 1", "Point 2"],
        }
    )


def test_style_lock_recursively_rejects_model_formatting_fields():
    with pytest.raises(StyleLockViolationError, match="theme_overrides"):
        StyleLock.assert_plan_content_only(
            {"sections": [{"title": "Safe content", "theme_overrides": [{"color": "teal"}]}]}
        )


def test_style_lock_detects_injected_direct_run_font_size_mutation():
    """Verify that newly generated elements are checked and direct font-size mutation is detected."""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    p = doc.add_paragraph("Clean paragraph inherited from template.")
    run = p.add_run(" Injected rogue run with direct font override.")
    run.font.size = Pt(28)

    with pytest.raises(StyleLockViolationError, match="Direct formatting mutation detected.*font size"):
        StyleLock.assert_no_direct_formatting(p)


def test_style_lock_detects_injected_direct_paragraph_format_mutation():
    """Verify that an injected direct paragraph-format mutation is detected."""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    p = doc.add_paragraph("Custom spacing paragraph.")
    p.paragraph_format.space_before = Pt(72)

    with pytest.raises(StyleLockViolationError, match="Direct formatting mutation detected.*space_before"):
        StyleLock.assert_no_direct_formatting(p)


def test_style_lock_allows_unmodified_direct_elements():
    """Verify that clean elements without direct overrides pass validation."""
    from docx import Document

    doc = Document()
    p = doc.add_paragraph("Standard paragraph using template style.")
    p.add_run(" Regular run content.")

    # Should pass without raising
    StyleLock.assert_no_direct_formatting(p)

