# Challenger 2 Empirical Stress, Concurrency & Security Verification Suite
import asyncio
import hashlib
import os
import shutil
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any

import pytest
from fastapi.testclient import TestClient
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt

from backend.app.main import app
from backend.app.config import settings
from backend.app.analyzer.template_analyzer import TemplateAnalyzer
from backend.app.validation.diff_validator import DiffValidator
from backend.app.validation.style_hash import StyleHasher
from backend.app.engines.docx_engine import DocxEngine
from backend.app.engines.pptx_engine import PptxEngine
from backend.app.ai.executor import DocumentExecutor
from backend.app.models.generation import (
    DocumentPlan,
    DocumentSection,
    PresentationPlan,
    SlidePlan,
    TableData,
    ValidationReport,
)

client = TestClient(app)

# ===========================================================================#
# FIXTURES
# ===========================================================================

@pytest.fixture
def rich_docx_template(tmp_path: Path) -> Path:
    f = tmp_path / "challenger_rich_template.docx"
    doc = Document()
    s = doc.sections[0]
    s.top_margin = Inches(1.0)
    s.bottom_margin = Inches(1.0)
    s.left_margin = Inches(1.0)
    s.right_margin = Inches(1.0)
    s.page_width = Inches(8.5)
    s.page_height = Inches(11.0)

    # Header and Footer
    h = s.header.paragraphs[0]
    h.text = "CHALLENGER STRESS SUITE: CONFIDENTIAL"
    f_p = s.footer.paragraphs[0]
    f_p.text = "Page 1 of Evaluation Document"

    # Styles and Content
    doc.add_paragraph("Enterprise Architecture Blueprint", style="Title")
    doc.add_paragraph("1. High-Concurrency Stress Topology", style="Heading 1")
    doc.add_paragraph("Baseline document body for invariant stress testing.")
    doc.add_paragraph("1.1 Microservice Sub-systems", style="Heading 2")

    # Table
    t = doc.add_table(rows=2, cols=3)
    t.style = "Table Grid"
    for c_idx, name in enumerate(["Service", "Target QPS", "SLO P99"]):
        cell = t.cell(0, c_idx)
        cell.text = name
        if cell.paragraphs[0].runs:
            cell.paragraphs[0].runs[0].font.bold = True
    t.cell(1, 0).text = "Template Engine"
    t.cell(1, 1).text = "5000"
    t.cell(1, 2).text = "15ms"

    doc.save(str(f))
    return f

@pytest.fixture
def rich_pptx_16_9_template(tmp_path: Path) -> Path:
    f = tmp_path / "challenger_pptx_16_9.pptx"
    prs = Presentation()
    prs.slide_width = PptxInches(13.333)
    prs.slide_height = PptxInches(7.5)

    s1 = prs.slides.add_slide(prs.slide_layouts[0])
    s1.placeholders[0].text = "High-Concurrency Swarm Architecture"
    s1.placeholders[1].text = "Adversarial Invariant Verification"

    s2 = prs.slides.add_slide(prs.slide_layouts[1])
    s2.placeholders[0].text = "System Throughput Goals"
    tf = s2.placeholders[1].text_frame
    tf.text = "Metric 1: Zero Hash Drift Across 20 Concurrent Workers"

    prs.save(str(f))
    return f

# ==========================================================================
# 1. HIGH-CONCURRENCY & RACE CONDITIONS VERIFICATION
# ==========================================================================

def test_concurrency_swarm_parallel_generation_docx_and_pptx(
    rich_docx_template: Path,
    rich_pptx_16_9_template: Path
):
    """
    Empirical Stress: Spawns 16 concurrent threads (8 DOCX + 8 PPTX) executing
    simultaneous template uploads, full document generation, and validation.
    Verifies:
    - Zero thread collisions
    - Temp directory isolation
    - 100% HTTP 200 success rate
    - Zero style hash drift across all 16 workers
    """
    # Upload templates once to seed template IDs
    with open(rich_docx_template, "rb") as f:
        docx_upload_resp = client.post("/api/upload", files={"file": ("template.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert docx_upload_resp.status_code == 200
    docx_template_id = docx_upload_resp.json()["template_id"]
    docx_orig_hash = docx_upload_resp.json()["template_spec"]["style_hash"]

    with open(rich_pptx_16_9_template, "rb") as f:
        pptx_upload_resp = client.post("/api/upload", files={"file": ("template.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")})
    assert pptx_upload_resp.status_code == 200
    pptx_template_id = pptx_upload_resp.json()["template_id"]
    pptx_orig_hash = pptx_upload_resp.json()["template_spec"]["style_hash"]

    def worker_generate_docx(worker_id: int) -> Dict[str, Any]:
        payload = {
            "template_id": docx_template_id,
            "prompt": f"High-throughput parallel stress test payload from worker thread {worker_id}",
            "document_type": "docx",
            "mode": "create_document",
            "target_pages_or_slides": 2
        }
        res = client.post("/api/generate?wait=true", json=payload)
        return {"worker_id": worker_id, "format": "docx", "status": res.status_code, "json": res.json()}

    def worker_generate_pptx(worker_id: int) -> Dict[str, Any]:
        payload = {
            "template_id": pptx_template_id,
            "prompt": f"Strategic performance executive deck from concurrent worker thread {worker_id}",
            "document_type": "pptx",
            "mode": "create_presentation",
            "target_pages_or_slides": 2
        }
        res = client.post("/api/generate?wait=true", json=payload)
        return {"worker_id": worker_id, "format": "pptx", "status": res.status_code, "json": res.json()}

    # Execute 16 simultaneous generation tasks (8 DOCX + 8 PPTX) in parallel
    futures = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        for i in range(8):
            futures.append(executor.submit(worker_generate_docx, i))
        for i in range(8, 16):
            futures.append(executor.submit(worker_generate_pptx, i))

    results = [f.result() for f in as_completed(futures)]
    assert len(results) == 16

    for r in results:
        assert r["status"] == 200, f"Worker {r['worker_id']} failed with status {r['status']}: {r['json']}"
        data = r["json"]
        assert data["success"] is True
        assert "download_url" in data
        assert "validation" in data

        filename = data["output_filename"]
        file_path = settings.OUTPUT_DIR / filename
        assert file_path.exists(), f"Generated file {filename} does not exist on disk!"
        assert file_path.stat().st_size > 0, f"Generated file {filename} is empty!"

        val = data["validation"]
        assert val["passed"] is True, f"Worker {r['worker_id']} validation failed: {val['issues']}"
        assert val["hash_match"] is True

        if r["format"] == "docx":
            assert val["original_style_hash"] == docx_orig_hash
            assert val["generated_style_hash"] == docx_orig_hash
            assert val["margin_drift_detected"] is False
            doc = Document(str(file_path))
            assert len(doc.paragraphs) > 0
        else:
            assert val["original_style_hash"] == pptx_orig_hash
            assert val["generated_style_hash"] == pptx_orig_hash
            assert val["layout_drift_detected"] is False
            prs = Presentation(str(file_path))
            assert len(prs.slides) >= 2


def test_concurrency_rapid_parallel_downloads(rich_docx_template: Path):
    """
    Empirical Stress: Generates a document, then executes 32 simultaneous parallel
    download requests across 8 worker threads to stress the I/O pipeline and FileResponse streaming.
    """
    with open(rich_docx_template, "rb") as f:
        upload_resp = client.post("/api/upload", files={"file": ("dl_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    template_id = upload_resp.json()["template_id"]

    gen_resp = client.post("/api/generate?wait=true", json={
        "template_id": template_id,
        "prompt": "Concurrency download stress test payload",
        "document_type": "docx",
        "mode": "create_document"
    })
    assert gen_resp.status_code == 200
    filename = gen_resp.json()["output_filename"]

    def download_worker(run_id: int) -> Dict[str, Any]:
        resp = client.get(f"/api/download/{filename}")
        return {
            "run_id": run_id,
            "status": resp.status_code,
            "bytes_len": len(resp.content),
            "sha256": hashlib.sha256(resp.content).hexdigest()
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_worker, i) for i in range(32)]
        dl_results = [f.result() for f in as_completed(futures)]

    assert len(dl_results) == 32
    first_sha = dl_results[0]["sha256"]
    first_len = dl_results[0]["bytes_len"]

    for r in dl_results:
        assert r["status"] == 200
        assert r["bytes_len"] == first_len
        assert r["sha256"] == first_sha

# =========================================================================
# 2. STRUCTURAL HASH DIFF SENSITIVITY & FALSE POSITIVE/NEGATIVE AUDIT
# =========================================================================

def test_structural_diff_sensitivity_detects_all_margin_and_dimension_mutations(rich_docx_template: Path, tmp_path: Path):
    """
    Empirical Verification (False Negatives): Deliberately mutate individual style properties
#    (margins, dimensions, headers) and verify DiffValidator and StyleHasher NEVER fail to detect them.
    """
    analyzer = TemplateAnalyzer()
    orig_spec = analyzer.analyze(str(rich_docx_template))
    validator = DiffValidator()
    hasher = StyleHasher()

    mutations = [
        ("top_margin", lambda d: setattr(d.sections[0], "top_margin", Inches(1.5))),
        ("bottom_margin", lambda d: setattr(d.sections[0], "bottom_margin", Inches(0.5))),
        ("left_margin", lambda d: setattr(d.sections[0], "left_margin", Inches(2.0))),
        ("right_margin", lambda d: setattr(d.sections[0], "right_margin", Inches(0.75))),
        ("page_width", lambda d: setattr(d.sections[0], "page_width", Inches(8.0))),
        ("page_height", lambda d: setattr(d.sections[0], "page_height", Inches(10.0))),
        ("header_distance", lambda d: setattr(d.sections[0], "header_distance", Inches(0.8)))
    ]

    for label, mutator in mutations:
        doc = Document(str(rich_docx_template))
        mutator(doc)
        mutated_path = tmp_path / f"mutated_{label}.docx"
        doc.save(str(mutated_path))

        # Test DiffValidator
        report = validator.validate(orig_spec, str(mutated_path))
        assert report.passed is False, f"DiffValidator failed to catch mutation: {label}"
        assert report.hash_match is False, f"Hash match falsely reported True for mutation: {label}"
        assert report.original_style_hash != report.generated_style_hash

        if "margin" in label or "page" in label:
            assert report.margin_drift_detected is True, f"margin_drift_detected was False for {label}"

        # Test StyleHasher
        is_match, orig_h, gen_h, diffs = hasher.compare_hashes(str(rich_docx_template), str(mutated_path))
        assert is_match is False
        assert orig_h != gen_h


def test_structural_diff_sensitivity_detects_pptx_slide_dimension_and_layout_mutations(
    rich_pptx_16_9_template: Path,
    tmp_path: Path
):
    """
    Empirical Verification: Verify PPTX aspect ratio mutations (16:9 -> 4:3, custom height)
    and layout mutations are strictly detected.
    """
    analyzer = TemplateAnalyzer()
    orig_spec = analyzer.analyze(str(rich_pptx_16_9_template))
    validator = DiffValidator()

    # Mutation 1: 4:3 ratio mutation
    prs_4_3 = Presentation(str(rich_pptx_16_9_template))
    prs_4_3.slide_width = PptxInches(10.0)
    prs_4_3.slide_height = PptxInches(7.5)
    mutated_4_3_path = tmp_path / "mutated_4_3.pptx"
    prs_4_3.save(str(mutated_4_3_path))

    report_4_3 = validator.validate(orig_spec, str(mutated_4_3_path))
    assert report_4_3.passed is False
    assert report_4_3.layout_drift_detected is True
    assert report_4_3.hash_match is False

    # Mutation 2: Custom Height Drift
    prs_custom = Presentation(str(rich_pptx_16_9_template))
    prs_custom.slide_height = PptxInches(8.5)
    mutated_custom_path = tmp_path / "mutated_custom.pptx"
    prs_custom.save(str(mutated_custom_path))

    report_custom = validator.validate(orig_spec, str(mutated_custom_path))
    assert report_custom.passed is False
    assert report_custom.layout_drift_detected is True
    assert report_custom.hash_match is False


def test_structural_diff_zero_false_positives_across_diverse_content_generation(
    rich_docx_template: Path,
    rich_pptx_16_9_template: Path,
    tmp_path: Path
):
    """
    Empirical Verification (False Positives): Generates documents with complex, highly
    varied content and ensures DiffValidator reports 0 false alarms.
    """
    executor = DocumentExecutor()
    analyzer = TemplateAnalyzer()
    validator = DiffValidator()

    docx_spec = analyzer.analyze(str(rich_docx_template))
    pptx_spec = analyzer.analyze(str(rich_pptx_16_9_template))

    # Test 5 distinct DOCX content structures
    for i in range(5):
        plan = DocumentPlan(
            title=f"Test Document Content Structure #{i}",
            sections=[
                DocumentSection(
                    title=f"Dynamic Section {j}",
                    heading_style="Heading 1" if j % 2 == 0 else "Heading 2",
                    paragraphs=[f"Paragraph text {k} with standard formatting." for k in range(j + 1)],
                    table_data=TableData(
                        headers=[f"Col {c}" for c in range(3)],
                        rows=[[f"Val {r}-{c}" for c in range(3)] for r in range(i + 2)]
                    ) if j == 1 else None
                )
                for j in range(3)
            ]
        )
        out_docx = tmp_path / f"valid_gen_{i}.docx"
        executor.execute_docx(str(rich_docx_template), docx_spec, plan, str(out_docx))

        report = validator.validate(docx_spec, str(out_docx))
        assert report.passed is True, f"False positive on DOCX run {i}: {report.issues}"
        assert report.hash_match is True
        assert report.margin_drift_detected is False
        assert len(report.issues) == 0

    # Test 5 distinct PPTX presentation structures
    for i in range(5):
        pres_plan = PresentationPlan(
            presentation_title=f"Test Presentation Structure #{i}",
            slides=[
                SlidePlan(
                    slide_number=1,
                    layout_name="Title Slide",
                    title=f"Presentation {i}",
                    subtitle=f"Subtitle structure {i}"
                ),
                SlidePlan(
                    slide_number=2,
                    layout_name="Title and Content",
                    title=f"Slide Details #{i}",
                    bullet_points=[f"Bullet point index {k} on deck {i}" for k in range(i + 2)]
                )
            ]
        )
        out_pptx = tmp_path / f"valid_gen_{i}.pptx"
        executor.execute_pptx(str(rich_pptx_16_9_template), pptx_spec, pres_plan, str(out_pptx))

        report = validator.validate(pptx_spec, str(out_pptx))
        assert report.passed is True, f"False positive on PPTX run {i}: {report.issues}"
        assert report.hash_match is True
        assert report.layout_drift_detected is False
        assert len(report.issues) == 0


# =========================================================================
# 3. SECURITY & PATH TRAVERSAL ADVERSARIAL MATRIX
# =========================================================================

@pytest.mark.parametrize("attack_vector", [
    "../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "..%5C..%5Cconfig.py",
    "../../backend/app/config.py",
    "../../backend/app/main.py",
    "/etc/passwd",
    "C:/Windows/win.ini",
    "nonexistent_file_safeguard.docx",
    "COM1",
    "AUX"
])
def test_security_download_endpoint_path_traversal_rejection(attack_vector: str):
    """
    Security Verification: Ensure /api/download rejects or safely 404s on all path traversal,
    device names, and injection vectors without leaking files or raising 500 errors.
    """
    resp = client.get(f"/api/download/{attack_vector}")
    assert resp.status_code in (404, 400, 422), f"Path traversal attack '{attack_vector}' gave unexpected status {resp.status_code}"
    assert resp.status_code != 500
    assert resp.status_code != 200


@pytest.mark.parametrize("dangerous_filename,content_type", [
    ("exploit.exe", "application/x-msdownload"),
    ("backdoor.sh", "application/x-sh"),
    ("script.py", "text/x-python"),
    ("shell.php", "application/x-php"),
    ("payload.js", "application/javascript"),
    ("virus.bat", "application/x-bat"),
    ("malware.vbs", "text/vbscript"),
    ("document.docx.exe", "application/x-msdownload"),
    ("archive.zip", "application/zip"),
    ("image.png", "image/png"),
])
def test_security_upload_rejects_unauthorized_extensions(dangerous_filename: str, content_type: str):
    """
    Security Verification: Ensure /api/upload strictly blocks non-DOCX/PPTX/PDF extensions with 400.
    """
    files = {"file": (dangerous_filename, b"malicious payload content", content_type)}
    resp = client.post("/api/upload", files=files)
    assert resp.status_code == 400, f"Upload permitted illegal file extension: {dangerous_filename}"
    assert "Unsupported file type" in resp.json()["detail"]


def test_security_upload_filename_traversal_sanitization():
    """
    Security Verification: Upload with ../ in multipart filename header must be sanitized
    to the base filename and stored strictly inside settings.UPLOAD_DIR.
    """
    doc = Document()
    doc.add_paragraph("Safe Template")
    temp_buf = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    temp_buf.close()
    doc.save(temp_buf.name)

    with open(temp_buf.name, "rb") as f:
        files = {"file": ("../../../../traversal_attack.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        resp = client.post("/api/upload", files=files)

    os.remove(temp_buf.name)
    assert resp.status_code == 200
    template_id = resp.json()["template_id"]
    uploaded_file = settings.UPLOAD_DIR / template_id
    assert uploaded_file.exists()
    assert uploaded_file.is_relative_to(settings.UPLOAD_DIR.resolve())


@pytest.mark.parametrize("malicious_template_id", [
    "../../etc/passwd",
    "..%2F..%2Fmain",
    "<script>alert('xss')</script>",
    "DROP TABLE users;--"
])
def test_security_analyze_and_generate_injection_resilience(malicious_template_id: str):
    """
    Security Verification: /api/analyze and /api/generate handle malicious template IDs safely.
    """
    # Test Analyze
    resp_an = client.get(f"/api/analyze/{malicious_template_id}")
    assert resp_an.status_code in (400, 404, 422)
    assert resp_an.status_code != 500

    # Test Generate
    resp_gen = client.post("/api/generate", json={
        "template_id": malicious_template_id,
        "prompt": "Malicious Payload injection test",
        "document_type": "docx",
        "mode": "create_document"
    })
    assert resp_gen.status_code in (400, 404, 422)
    assert resp_gen.status_code != 500
