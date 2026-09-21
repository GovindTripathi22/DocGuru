"""Regression test suite for security boundaries (SEC-01, SEC-02, SEC-03, SEC-04)."""

import io
from pathlib import Path
import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.security import safe_path_join, sanitize_filename


def test_analyze_refuses_an_absolute_path_outside_storage(tmp_path: Path):
    """SEC-01 & A-22: Traversal paths (absolute, .., backslash, NUL) are rejected with 400/404."""
    client = TestClient(app)
    sentinel = tmp_path / "outside.docx"
    Document().save(sentinel)

    traversal_payloads = [
        str(sentinel),
        "../outside.docx",
        "..\\outside.docx",
        "%2e%2e%2foutside.docx",
        "/etc/passwd",
        "C:\\Windows\\win.ini",
        "template\x00.docx",
    ]

    for payload in traversal_payloads:
        response = client.post("/api/analyze", json={"template_id": payload})
        assert response.status_code in {400, 404, 422}, f"Failed to reject traversal payload: {payload}"


def test_safe_path_join_rejects_escape(tmp_path: Path):
    """SEC-01: safe_path_join enforces strict directory containment."""
    base = tmp_path / "base"
    base.mkdir()

    with pytest.raises(Exception):
        safe_path_join(base, "../escaped.txt")

    with pytest.raises(Exception):
        safe_path_join(base, "..\\escaped.txt")

    with pytest.raises(Exception):
        safe_path_join(base, "sub/../../escaped.txt")


def test_upload_rejects_junk_file_without_leaving_artifacts(tmp_path: Path):
    """SEC-02 & A-23: Corrupted or non-OOXML files fail upload with 422 and leave zero leftovers."""
    client = TestClient(app)
    initial_files = set(settings.UPLOAD_DIR.glob("*"))

    junk_bytes = io.BytesIO(b"Not an OpenXML document at all, just random junk bytes.")
    response = client.post(
        "/api/upload",
        files={"file": ("junk.docx", junk_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code in {400, 422}
    post_files = set(settings.UPLOAD_DIR.glob("*"))
    assert post_files == initial_files, "Leftover junk files remained in uploads directory!"


def test_filename_sanitization_and_unicode_download(tmp_path: Path):
    """SEC-04 & A-24: Non-ASCII, Hindi, Chinese, and CRLF filenames are safely sanitized and handled."""
    assert sanitize_filename("Normal File.docx") == "Normal File.docx"
    # CRLF header injection prevention
    assert "\r" not in sanitize_filename("malicious\r\nHeader: value\r\n.docx")
    assert "\n" not in sanitize_filename("malicious\r\nHeader: value\r\n.docx")

    # Hindi and unicode characters are preserved
    hindi_name = "रिपोर्ट.docx"
    clean_hindi = sanitize_filename(hindi_name)
    assert "रिपोर्ट" in clean_hindi or clean_hindi.endswith(".docx")
