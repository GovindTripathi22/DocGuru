import zipfile

import pytest
from docx import Document
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter

from backend.app.config import settings
from backend.app.errors import UnsupportedFile
from backend.app.main import app
from backend.app.security import register_resource_owner
from backend.app.validation.upload_file import validate_uploaded_file


def _make_pdf(path, *, pages: int = 1, password: str | None = None) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if password:
        writer.encrypt(password)
    with path.open("wb") as target:
        writer.write(target)


def test_upload_rejects_junk_and_removes_partial_artifact(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    with TestClient(app) as client:
        response = client.post(
            "/api/upload",
            files={"file": ("junk.docx", b"not an office archive", "application/octet-stream")},
            headers={"X-Session-Id": "upload-owner"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_OR_PROTECTED_FILE"
    assert list(upload_dir.iterdir()) == []


def test_file_size_cap_rejects_oversized_file_and_removes_it(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    with TestClient(app) as client:
        response = client.post(
            "/api/upload",
            files={"file": ("large.docx", b"x" * (1024 * 1024 + 1), "application/octet-stream")},
            headers={"X-Session-Id": "upload-owner"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert list(upload_dir.iterdir()) == []


def test_request_size_limit_rejects_oversized_declared_body(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    request_id = "oversized-request-42"
    with TestClient(app) as client:
        response = client.post(
            "/api/upload",
            content=b"x" * (2 * 1024 * 1024 + 1),
            headers={
                "Content-Type": "multipart/form-data; boundary=x",
                "X-Request-ID": request_id,
            },
        )
    assert response.status_code == 413
    assert response.headers["X-Request-ID"] == request_id
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_request_size_limit_rejects_chunked_body_without_content_length(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

    async def request_body():
        yield (
            b'--x\r\nContent-Disposition: form-data; name="file"; '
            b'filename="large.docx"\r\nContent-Type: application/octet-stream\r\n\r\n'
        )
        yield b"x" * (2 * 1024 * 1024)
        yield b"\r\n--x--\r\n"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/upload",
            content=request_body(),
            headers={"Content-Type": "multipart/form-data; boundary=x"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_upload_validator_rejects_macro_enabled_ooxml(tmp_path):
    original_path = tmp_path / "source.docx"
    Document().save(original_path)
    macro_path = tmp_path / "macro.docx"
    with zipfile.ZipFile(original_path) as source, zipfile.ZipFile(macro_path, "w") as target:
        for item in source.infolist():
            target.writestr(item, source.read(item.filename))
        target.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(UnsupportedFile, match="Macro-enabled"):
        validate_uploaded_file(macro_path, ".docx")


def test_upload_validator_rejects_high_ratio_zip_bomb(tmp_path, monkeypatch):
    bomb_path = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types></Types>")
        archive.writestr("word/document.xml", b"A" * 100_000)
    monkeypatch.setattr("backend.app.validation.upload_file.MAX_COMPRESSION_RATIO", 10)
    with pytest.raises(UnsupportedFile, match="compression ratio"):
        validate_uploaded_file(bomb_path, ".docx")


def test_pdf_upload_validator_rejects_encrypted_malformed_and_over_page_limit(
    tmp_path, monkeypatch
):
    encrypted = tmp_path / "encrypted.pdf"
    _make_pdf(encrypted, password="secret")
    with pytest.raises(UnsupportedFile, match="Encrypted"):
        validate_uploaded_file(encrypted, ".pdf")

    malformed = tmp_path / "malformed.pdf"
    malformed.write_bytes(b"%PDF-1.7\nnot a valid PDF")
    with pytest.raises(UnsupportedFile, match="could not be read"):
        validate_uploaded_file(malformed, ".pdf")

    multi_page = tmp_path / "multi.pdf"
    _make_pdf(multi_page, pages=2)
    monkeypatch.setattr(settings, "MAX_PDF_PAGES", 1)
    with pytest.raises(UnsupportedFile, match="allowed 1 pages"):
        validate_uploaded_file(multi_page, ".pdf")


def test_download_supports_unicode_filename_without_header_injection(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    filename = "résumé 😀.docx"
    (output_dir / filename).write_bytes(b"document bytes")
    monkeypatch.setattr(settings, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    register_resource_owner("output", filename, "download-owner")
    with TestClient(app) as client:
        response = client.get(
            f"/api/download/{filename}", headers={"X-Session-Id": "download-owner"}
        )
    disposition = response.headers["content-disposition"].lower()
    assert response.status_code == 200
    assert "filename*=utf-8''" in disposition
    assert "%0d" not in disposition and "%0a" not in disposition
    assert response.headers["x-content-type-options"] == "nosniff"


def test_foreign_download_matches_missing_output_response(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    filename = "abcdef0123456789abcdef0123456789.docx"
    (output_dir / filename).write_bytes(b"document bytes")
    monkeypatch.setattr(settings, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    register_resource_owner("output", filename, "download-owner")
    with TestClient(app) as client:
        foreign = client.get(f"/api/download/{filename}", headers={"X-Session-Id": "other-session"})
        missing = client.get(
            "/api/download/11111111111111111111111111111111.docx",
            headers={"X-Session-Id": "other-session"},
        )
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["error"]["code"] == missing.json()["error"]["code"]
    assert foreign.json()["error"]["message"] == missing.json()["error"]["message"]
