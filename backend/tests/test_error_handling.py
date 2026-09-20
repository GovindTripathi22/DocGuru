import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


def test_request_id_echoed_and_generated():
    client = TestClient(app)
    
    # 1. Provided X-Request-ID is echoed back
    resp = client.get("/health/live", headers={"X-Request-ID": "test-req-123"})
    assert resp.headers.get("X-Request-ID") == "test-req-123"

    # 2. When omitted, X-Request-ID is generated and returned
    resp2 = client.get("/health/live")
    assert resp2.headers.get("X-Request-ID") is not None
    assert len(resp2.headers.get("X-Request-ID")) > 0


def test_unknown_route_returns_error_envelope():
    client = TestClient(app)
    resp = client.get("/api/nonexistent-endpoint-12345")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "request_id" in data["error"]
    assert "message" in data["error"]


def test_no_paths_or_tracebacks_in_error_responses():
    client = TestClient(app)
    forbidden_tokens = ["Traceback", "File \"", "\\app\\", "/app/", "\\backend\\", "/backend/"]

    # Analyze failure
    r_analyze = client.post("/api/analyze", json={"template_id": "nonexistent_temp.docx"})
    assert r_analyze.status_code in (404, 422)
    body_analyze = r_analyze.text
    for token in forbidden_tokens:
        assert token not in body_analyze, f"Found '{token}' in analyze error: {body_analyze}"

    # Generate failure
    r_generate = client.post("/api/generate", json={"template_id": "nonexistent_temp.docx", "prompt": "test"})
    assert r_generate.status_code in (404, 422)
    body_generate = r_generate.text
    for token in forbidden_tokens:
        assert token not in body_generate, f"Found '{token}' in generate error: {body_generate}"

    # Validate failure
    r_validate = client.post("/api/validate", json={"template_id": "nonexistent.docx", "generated_filename": "nonexistent.docx"})
    assert r_validate.status_code in (404, 422)
    body_validate = r_validate.text
    for token in forbidden_tokens:
        assert token not in body_validate, f"Found '{token}' in validate error: {body_validate}"

    # Download failure
    r_download = client.get("/api/download/nonexistent_file_9999.docx")
    assert r_download.status_code == 404
    body_download = r_download.text
    for token in forbidden_tokens:
        assert token not in body_download, f"Found '{token}' in download error: {body_download}"

    # Upload invalid failure
    files = {"file": ("bad.exe", b"binary", "application/x-msdownload")}
    r_upload = client.post("/api/upload", files=files)
    assert r_upload.status_code == 400
    body_upload = r_upload.text
    for token in forbidden_tokens:
        assert token not in body_upload, f"Found '{token}' in upload error: {body_upload}"
