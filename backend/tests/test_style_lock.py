import pytest
from backend.app.engines.style_lock import StyleLock, StyleLockViolationError

def test_style_lock_blocks_arbitrary_formatting():
    # Attempting to specify font size should be blocked
    with pytest.raises(StyleLockViolationError):
        StyleLock.assert_content_only({
            "content": "Sample text",
            "font_size": 14
        })

    # Attempting to specify custom color should be blocked
    with pytest.raises(StyleLockViolationError):
        StyleLock.assert_content_only({
            "content": "Sample text",
            "font_color": "#FF0000"
        })

    # Attempting to override margins should be blocked
    with pytest.raises(StyleLockViolationError):
        StyleLock.assert_content_only({
            "content": "Sample text",
            "margin_top": 2.0
        })

def test_style_lock_permits_content_operations():
    # Pure content operations must pass cleanly
    StyleLock.assert_content_only({
        "style": "Heading 1",
        "content": "Valid Section Title"
    })

    StyleLock.assert_content_only({
        "layout_name": "Title and Content",
        "title": "Valid Presentation Slide Title",
        "bullet_points": ["Point 1", "Point 2"]
    })
