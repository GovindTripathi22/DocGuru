"""
End-to-End (E2E) Integration Test Suite for Exact Template Inheritance System.

Covers all 6 core integration workflows as specified in Acceptance Criterion 3:
- Workflow 1 (Health): GET /api/health -> verify status is "healthy" and response format.
- Workflow 2 (Prompt Enhance): POST /api/enhance-prompt -> verify neural enhancement for full gen & surgical edit modes.
- Workflow 3 (DOCX Generation): POST /api/generate with docx template -> verify successful generation, structural diff pass, and locked style invariants.
- Workflow 4 (DOCX Download): GET /api/download/{filename} -> verify file streaming, correct headers, and non-empty binary.
- Workflow 5 (PPTX Generation): POST /api/generate with pptx template -> verify successful presentation generation, master preservation, and structural diff pass.
- Workflow 6 (PPTX Download): GET /api/download/{filename} -> verify file streaming and valid presentation binary.

Also covers comprehensive E2E tests for:
- Template Upload: POST /api/upload (DOCX, PPTX, invalid format validation)
- Template Re-Analysis: POST /api/analyze (DOCX, PPTX, non-existent 404)
- Diff Validation: POST /api/validate (DOCX, PPTX, non-existent 404)
- Full End-to-End Chained Lifecycles (Upload -> Enhance -> Generate -> Validate -> Download -> Inspect DOM)
- Security and error handling against directory traversal and missing resources.
"""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import docx
from docx.shared import Inches
import pptx
from pptx.util import Inches as PptxInches

from backend.app.main import app
from backend.app.config import settings


@pytest.fixture(scope="module")
def client():
    """Module-scoped FastAPI TestClient fixture."""
    orig_provider = settings.MODEL_PROVIDER
    settings.MODEL_PROVIDER = "demo"
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings.MODEL_PROVIDER = orig_provider


# ==============================================================================
# WORKFLOW 1: HEALTH CHECK (GET /api/health)
# ==============================================================================

def test_e2e_workflow_1_health_check(client: TestClient):
    """
    Workflow 1 (Health): Verify GET /api/health returns healthy status and metadata.
    """
    response = client.get("/api/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "model_provider" in data
    assert "model_name" in data
    assert data["version"] == "1.0.0"


def test_e2e_workflow_1_root_health_alias(client: TestClient):
    """
    Workflow 1 Alias: Verify GET /health also routes correctly.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


# ==============================================================================
# WORKFLOW 2: PROMPT ENHANCEMENT (POST /api/enhance-prompt)
# ==============================================================================

def test_e2e_workflow_2_prompt_enhancement_docx_full_generation(client: TestClient):
    """
    Workflow 2 (Prompt Enhance - DOCX Full Gen):
    Verify neural prompt enhancer expands a concise topic into a structured document instruction.
    """
    payload = {
        "prompt": "Autonomous vehicle perception and sensor fusion architecture",
        "document_type": "docx"
    }
    response = client.post("/api/enhance-prompt", json=payload)
    assert response.status_code == 200, f"Failed prompt enhance: {response.text}"
    data = response.json()
    assert data["original_prompt"] == payload["prompt"]
    assert "enhanced_prompt" in data
    assert len(data["enhanced_prompt"]) > len(payload["prompt"])
    assert isinstance(data["enhanced_prompt"], str)


def test_e2e_workflow_2_prompt_enhancement_pptx_full_generation(client: TestClient):
    """
    Workflow 2 (Prompt Enhance - PPTX Full Gen):
    Verify neural prompt enhancer generates structured presentation slide instructions.
    """
    payload = {
        "prompt": "Q4 Enterprise AI Cloud Strategy and Roadmap",
        "document_type": "pptx"
    }
    response = client.post("/api/enhance-prompt", json=payload)
    assert response.status_code == 200, f"Failed pptx prompt enhance: {response.text}"
    data = response.json()
    assert data["original_prompt"] == payload["prompt"]
    assert "enhanced_prompt" in data
    assert len(data["enhanced_prompt"]) > len(payload["prompt"])


def test_e2e_workflow_2_prompt_enhancement_surgical_edit_mode(client: TestClient):
    """
    Workflow 2 (Prompt Enhance - Surgical Edit):
    Verify enhancer handles targeted revision prompts with specific template context.
    """
    payload = {
        "prompt": "Update Section 3 benchmark metrics to reflect H100 GPU throughput",
        "document_type": "docx",
        "template_title": "Quarterly Infrastructure Audit"
    }
    response = client.post("/api/enhance-prompt", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["original_prompt"] == payload["prompt"]
    assert len(data["enhanced_prompt"]) > 0


def test_e2e_workflow_2_prompt_enhancement_empty_fallback(client: TestClient):
    """
    Workflow 2 (Prompt Enhance - Empty Fallback):
    Verify enhancer gracefully handles empty or whitespace input with standard fallback.
    """
    payload = {
        "prompt": "   ",
        "document_type": "docx"
    }
    response = client.post("/api/enhance-prompt", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["enhanced_prompt"]) > 0
    assert "executive report" in data["enhanced_prompt"].lower() or "methodology" in data["enhanced_prompt"].lower()


# ==============================================================================
# TEMPLATE UPLOAD ENDPOINT (POST /api/upload)
# ==============================================================================

def test_e2e_upload_docx_template(client: TestClient, sample_docx_template: Path):
    """
    Verify uploading a valid DOCX template returns extracted TemplateSpecification.
    """
    with open(sample_docx_template, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": (sample_docx_template.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    assert data["success"] is True
    assert "template_id" in data
    assert data["document_type"] == "docx"
    spec = data["template_spec"]
    assert spec["document_type"] == "docx"
    assert "style_hash" in spec and len(spec["style_hash"]) > 0
    assert "page" in spec and spec["page"] is not None
    assert "margins" in spec["page"]
    assert spec["page"]["margins"]["top_pt"] == 72.0
    assert "styles" in spec

    # Verify template was saved to uploads dir
    uploaded_file = settings.UPLOAD_DIR / data["template_id"]
    assert uploaded_file.exists()


def test_e2e_upload_pptx_template(client: TestClient, sample_pptx_template: Path):
    """
    Verify uploading a valid PPTX template returns extracted TemplateSpecification.
    """
    with open(sample_pptx_template, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": (sample_pptx_template.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    assert data["success"] is True
    assert "template_id" in data
    assert data["document_type"] == "pptx"
    spec = data["template_spec"]
    assert spec["document_type"] == "pptx"
    assert "style_hash" in spec and len(spec["style_hash"]) > 0
    assert "slide_dimensions" in spec
    assert "layouts" in spec


def test_e2e_upload_invalid_extension_rejected(client: TestClient):
    """
    Verify uploading an unsupported file extension is rejected with 400 Bad Request.
    """
    fake_content = b"This is a plain text document."
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", io.BytesIO(fake_content), "text/plain")}
    )
    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"].lower()


# ==============================================================================
# TEMPLATE RE-ANALYSIS ENDPOINT (POST /api/analyze)
# ==============================================================================

def test_e2e_analyze_existing_template(client: TestClient, sample_docx_template: Path):
    """
    Verify re-analyzing an existing uploaded template produces identical TemplateSpecification.
    """
    with open(sample_docx_template, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": (sample_docx_template.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    template_id = upload_resp.json()["template_id"]

    analyze_resp = client.post("/api/analyze", json={"template_id": template_id})
    assert analyze_resp.status_code == 200
    data = analyze_resp.json()
    assert data["success"] is True
    assert data["template_id"] == template_id
    assert data["template_spec"]["style_hash"] == upload_resp.json()["template_spec"]["style_hash"]


def test_e2e_analyze_nonexistent_template_returns_404(client: TestClient):
    """
    Verify requesting analysis of a nonexistent template returns 404 Not Found.
    """
    response = client.post("/api/analyze", json={"template_id": "nonexistent_file_123.docx"})
    assert response.status_code == 404


# ==============================================================================
# WORKFLOW 3: DOCX GENERATION & INVARIANT ENFORCEMENT (POST /api/generate)
# ==============================================================================

def test_e2e_workflow_3_docx_generation(client: TestClient, sample_docx_template: Path):
    """
    Workflow 3 (DOCX Generation):
    Verify generating a DOCX document preserves all template styles, headers, footers,
    and margins, passing structural diff validation with 0 drift.
    """
    # 1. Upload template
    with open(sample_docx_template, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": (sample_docx_template.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert upload_resp.status_code == 200
    template_id = upload_resp.json()["template_id"]
    orig_hash = upload_resp.json()["template_spec"]["style_hash"]

    # 2. Generate document
    gen_payload = {
        "template_id": template_id,
        "prompt": "Comprehensive Audit on Distributed Systems Consensus Latency",
        "document_type": "docx",
        "mode": "create_document",
        "target_pages_or_slides": 2
    }
    gen_resp = client.post("/api/generate", json=gen_payload)
    assert gen_resp.status_code == 200, f"Generation failed: {gen_resp.text}"
    gen_data = gen_resp.json()

    # 3. Verify response structure
    assert gen_data["success"] is True
    assert gen_data["output_filename"].endswith(".docx")
    assert gen_data["download_url"] == f"/api/download/{gen_data['output_filename']}"
    assert gen_data["execution_time_sec"] >= 0

    # 4. Verify structural diff validation report
    val = gen_data["validation"]
    assert val["passed"] is True, f"Validation failed with issues: {val.get('issues')}"
    assert val["hash_match"] is True
    assert val["original_style_hash"] == orig_hash
    assert val["generated_style_hash"] == orig_hash
    assert val["font_drift_detected"] is False
    assert val["border_drift_detected"] is False
    assert val["margin_drift_detected"] is False
    assert val["header_footer_preserved"] is True
    assert val["table_formatting_preserved"] is True
    assert len(val["issues"]) == 0

    # 5. Verify output file exists on disk
    generated_file = settings.OUTPUT_DIR / gen_data["output_filename"]
    assert generated_file.exists()
    assert generated_file.stat().st_size > 0


# ==============================================================================
# WORKFLOW 4: DOCX DOWNLOAD & ARTIFACT STREAMING (GET /api/download/{filename})
# ==============================================================================

def test_e2e_workflow_4_docx_download(client: TestClient, sample_docx_template: Path):
    """
    Workflow 4 (DOCX Download):
    Verify downloading a generated DOCX streams non-empty binary with valid headers
    and contains intact document DOM structures (margins, headers, footers, tables).
    """
    # 1. Upload and generate
    with open(sample_docx_template, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": (sample_docx_template.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    template_id = upload_resp.json()["template_id"]

    gen_resp = client.post("/api/generate", json={
        "template_id": template_id,
        "prompt": "Quarterly Financial Analysis & Strategic Benchmarking",
        "document_type": "docx"
    })
    output_filename = gen_resp.json()["output_filename"]

    # 2. Download generated artifact
    download_resp = client.get(f"/api/download/{output_filename}")
    assert download_resp.status_code == 200, f"Download failed: {download_resp.status_code}"

    # 3. Verify download headers
    assert download_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert f"filename={output_filename}" in download_resp.headers["content-disposition"]

    # 4. Verify binary payload integrity
    binary_content = download_resp.content
    assert len(binary_content) > 1000

    # 5. Parse downloaded binary directly with python-docx
    doc = docx.Document(io.BytesIO(binary_content))
    assert len(doc.sections) > 0
    section = doc.sections[0]

    # Verify margin invariants preserved (1.0 inch)
    assert abs(section.top_margin.inches - 1.0) < 0.01
    assert abs(section.bottom_margin.inches - 1.0) < 0.01
    assert abs(section.left_margin.inches - 1.0) < 0.01
    assert abs(section.right_margin.inches - 1.0) < 0.01

    # Verify header & footer invariant text
    header_text = "".join(p.text for p in section.header.paragraphs)
    footer_text = "".join(p.text for p in section.footer.paragraphs)
    assert "ORGANIZATIONAL TEMPLATE" in header_text
    assert "All Rights Reserved" in footer_text


# ==============================================================================
# WORKFLOW 5: PPTX GENERATION & MASTER PRESERVATION (POST /api/generate)
# ==============================================================================

def test_e2e_workflow_5_pptx_generation(client: TestClient, sample_pptx_template: Path):
    """
    Workflow 5 (PPTX Generation):
    Verify generating a PPTX presentation preserves master layouts, slide dimensions,
    and passes structural diff validation with 0 drift.
    """
    # 1. Upload template
    with open(sample_pptx_template, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": (sample_pptx_template.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
    assert upload_resp.status_code == 200
    template_id = upload_resp.json()["template_id"]
    orig_hash = upload_resp.json()["template_spec"]["style_hash"]

    # 2. Generate presentation
    gen_payload = {
        "template_id": template_id,
        "prompt": "Autonomous AI Agent Orchestration Architecture",
        "document_type": "pptx",
        "mode": "create_presentation",
        "target_pages_or_slides": 3
    }
    gen_resp = client.post("/api/generate", json=gen_payload)
    assert gen_resp.status_code == 200, f"PPTX Generation failed: {gen_resp.text}"
    gen_data = gen_resp.json()

    # 3. Verify response structure
    assert gen_data["success"] is True
    assert gen_data["output_filename"].endswith(".pptx")
    assert gen_data["download_url"] == f"/api/download/{gen_data['output_filename']}"

    # 4. Verify structural diff validation report
    val = gen_data["validation"]
    assert val["passed"] is True
    assert val["hash_match"] is True
    assert val["original_style_hash"] == orig_hash
    assert val["generated_style_hash"] == orig_hash
    assert val["layout_drift_detected"] is False
    assert len(val["issues"]) == 0

    # 5. Verify output file exists on disk
    generated_file = settings.OUTPUT_DIR / gen_data["output_filename"]
    assert generated_file.exists()
    assert generated_file.stat().st_size > 0


# ==============================================================================
# WORKFLOW 6: PPTX DOWNLOAD & PRESENTATION VERIFICATION (GET /api/download/{filename})
# ==============================================================================

def test_e2e_workflow_6_pptx_download(client: TestClient, sample_pptx_template: Path):
    """
    Workflow 6 (PPTX Download):
    Verify downloading a generated PPTX streams valid presentation binary with correct headers
    and verifies slide dimensions (16:9 widescreen) and content structures.
    """
    # 1. Upload and generate
    with open(sample_pptx_template, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": (sample_pptx_template.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
    template_id = upload_resp.json()["template_id"]

    gen_resp = client.post("/api/generate", json={
        "template_id": template_id,
        "prompt": "Scalable Multi-Agent AI Infrastructure",
        "document_type": "pptx"
    })
    output_filename = gen_resp.json()["output_filename"]

    # 2. Download presentation artifact
    download_resp = client.get(f"/api/download/{output_filename}")
    assert download_resp.status_code == 200

    # 3. Verify headers
    assert download_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert f"filename={output_filename}" in download_resp.headers["content-disposition"]

    # 4. Verify binary payload integrity
    binary_content = download_resp.content
    assert len(binary_content) > 1000

    # 5. Parse downloaded binary with python-pptx
    prs = pptx.Presentation(io.BytesIO(binary_content))
    assert len(prs.slides) >= 2

    # Verify slide dimensions (16:9 widescreen: 13.333" x 7.5")
    width_in = prs.slide_width.inches
    height_in = prs.slide_height.inches
    assert abs(width_in - 13.333) < 0.05
    assert abs(height_in - 7.5) < 0.05


# ==============================================================================
# DIFF VALIDATION ENDPOINT (POST /api/validate)
# ==============================================================================

def test_e2e_validate_endpoint_docx_success(client: TestClient, sample_docx_template: Path):
    """
    Verify POST /api/validate confirms exact style match between template and generated DOCX.
    """
    with open(sample_docx_template, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": (sample_docx_template.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    template_id = upload_resp.json()["template_id"]

    gen_resp = client.post("/api/generate", json={
        "template_id": template_id,
        "prompt": "Deep Learning Acceleration Benchmark",
        "document_type": "docx"
    })
    generated_filename = gen_resp.json()["output_filename"]

    val_resp = client.post("/api/validate", json={
        "template_id": template_id,
        "generated_filename": generated_filename
    })
    assert val_resp.status_code == 200
    report = val_resp.json()
    assert report["passed"] is True
    assert report["hash_match"] is True
    assert len(report["issues"]) == 0


def test_e2e_validate_endpoint_pptx_success(client: TestClient, sample_pptx_template: Path):
    """
    Verify POST /api/validate confirms exact layout match between template and generated PPTX.
    """
    with open(sample_pptx_template, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": (sample_pptx_template.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
    template_id = upload_resp.json()["template_id"]

    gen_resp = client.post("/api/generate", json={
        "template_id": template_id,
        "prompt": "Cloud Native Storage Evolution",
        "document_type": "pptx"
    })
    generated_filename = gen_resp.json()["output_filename"]

    val_resp = client.post("/api/validate", json={
        "template_id": template_id,
        "generated_filename": generated_filename
    })
    assert val_resp.status_code == 200
    report = val_resp.json()
    assert report["passed"] is True
    assert report["hash_match"] is True


def test_e2e_validate_endpoint_missing_files_404(client: TestClient):
    """
    Verify POST /api/validate returns 404 if either template or generated file is missing.
    """
    # Missing template
    resp1 = client.post("/api/validate", json={
        "template_id": "nonexistent_template.docx",
        "generated_filename": "some_file.docx"
    })
    assert resp1.status_code == 404

    # Missing generated file
    resp2 = client.post("/api/validate", json={
        "template_id": "nonexistent.docx",
        "generated_filename": "nonexistent.docx"
    })
    assert resp2.status_code == 404


# ==============================================================================
# FULL LIFECYCLE CHAINED INTEGRATION WORKFLOWS
# ==============================================================================

def test_e2e_full_lifecycle_docx_pipeline(client: TestClient, sample_docx_template: Path):
    """
    Full Lifecycle Chained E2E Test:
    1. Upload DOCX template -> verify spec extraction.
    2. Enhance prompt -> verify neural enhancement.
    3. Generate DOCX with enhanced prompt -> verify execution & validation report.
    4. Explicitly validate output with validation endpoint -> verify zero drift.
    5. Download artifact -> verify streamed binary & DOM structural invariants.
    """
    # Step 1: Upload
    with open(sample_docx_template, "rb") as f:
        upload_res = client.post(
            "/api/upload",
            files={"file": (sample_docx_template.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert upload_res.status_code == 200
    template_id = upload_res.json()["template_id"]
    spec = upload_res.json()["template_spec"]

    # Step 2: Enhance Prompt
    raw_prompt = "Next-Generation Database Performance and Consistency Guarantees"
    enhance_res = client.post("/api/enhance-prompt", json={
        "prompt": raw_prompt,
        "document_type": "docx",
        "template_title": spec.get("metadata", {}).get("title")
    })
    assert enhance_res.status_code == 200
    enhanced_prompt = enhance_res.json()["enhanced_prompt"]

    # Step 3: Generate
    gen_res = client.post("/api/generate", json={
        "template_id": template_id,
        "prompt": enhanced_prompt,
        "document_type": "docx",
        "mode": "create_document",
        "target_pages_or_slides": 2
    })
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["validation"]["passed"] is True
    output_filename = gen_data["output_filename"]

    # Step 4: Validate
    val_res = client.post("/api/validate", json={
        "template_id": template_id,
        "generated_filename": output_filename
    })
    assert val_res.status_code == 200
    assert val_res.json()["passed"] is True

    # Step 5: Download & verify DOM
    dl_res = client.get(f"/api/download/{output_filename}")
    assert dl_res.status_code == 200
    doc = docx.Document(io.BytesIO(dl_res.content))
    assert len(doc.paragraphs) > 0
    assert len(doc.tables) > 0


def test_e2e_full_lifecycle_pptx_pipeline(client: TestClient, sample_pptx_template: Path):
    """
    Full Lifecycle Chained E2E Test:
    1. Upload PPTX template -> verify spec extraction.
    2. Enhance prompt -> verify presentation prompt expansion.
    3. Generate presentation with enhanced prompt -> verify execution & validation report.
    4. Explicitly validate output with validation endpoint -> verify zero drift.
    5. Download artifact -> verify streamed presentation & slide structure.
    """
    # Step 1: Upload
    with open(sample_pptx_template, "rb") as f:
        upload_res = client.post(
            "/api/upload",
            files={"file": (sample_pptx_template.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
    assert upload_res.status_code == 200
    template_id = upload_res.json()["template_id"]

    # Step 2: Enhance Prompt
    raw_prompt = "Zero-Trust Architecture for Cloud Native Microservices"
    enhance_res = client.post("/api/enhance-prompt", json={
        "prompt": raw_prompt,
        "document_type": "pptx"
    })
    assert enhance_res.status_code == 200
    enhanced_prompt = enhance_res.json()["enhanced_prompt"]

    # Step 3: Generate
    gen_res = client.post("/api/generate", json={
        "template_id": template_id,
        "prompt": enhanced_prompt,
        "document_type": "pptx",
        "mode": "create_presentation",
        "target_pages_or_slides": 3
    })
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["validation"]["passed"] is True
    output_filename = gen_data["output_filename"]

    # Step 4: Validate
    val_res = client.post("/api/validate", json={
        "template_id": template_id,
        "generated_filename": output_filename
    })
    assert val_res.status_code == 200
    assert val_res.json()["passed"] is True

    # Step 5: Download & verify PPTX
    dl_res = client.get(f"/api/download/{output_filename}")
    assert dl_res.status_code == 200
    prs = pptx.Presentation(io.BytesIO(dl_res.content))
    assert len(prs.slides) >= 2


# ==============================================================================
# SECURITY & ERROR HANDLING EDGE CASES
# ==============================================================================

def test_e2e_download_nonexistent_returns_404(client: TestClient):
    """
    Verify requesting download of a nonexistent artifact returns 404 Not Found.
    """
    response = client.get("/api/download/nonexistent_file_9999.docx")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_e2e_download_directory_traversal_blocked(client: TestClient):
    """
    Verify directory traversal attempts in download endpoint are blocked (404).
    """
    response = client.get("/api/download/..%2F..%2Fconfig.py")
    assert response.status_code in (400, 404)


def test_e2e_generate_nonexistent_template_returns_404(client: TestClient):
    """
    Verify attempting to generate a document from a nonexistent template returns 404.
    """
    payload = {
        "template_id": "nonexistent_template_xyz.docx",
        "prompt": "Test Prompt",
        "document_type": "docx"
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
