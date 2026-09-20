"""Tests for API-JOBS asynchronous job management, polling, cancellation, and retention."""

import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.jobs import JobProgress, job_manager
from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    orig_provider = settings.MODEL_PROVIDER
    settings.MODEL_PROVIDER = "demo"
    with TestClient(app) as test_client:
        yield test_client
    settings.MODEL_PROVIDER = orig_provider


def test_generate_returns_202_and_polls_to_success(client, sample_docx_template):
    # 1. Upload template
    with open(sample_docx_template, "rb") as f:
        up_resp = client.post("/api/upload", files={"file": ("test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert up_resp.status_code == 200
    template_id = up_resp.json()["template_id"]

    # 2. POST /api/generate returns 202 with job_id
    gen_resp = client.post("/api/generate", json={"template_id": template_id, "prompt": "Quarterly overview"})
    assert gen_resp.status_code == 202
    data = gen_resp.json()
    assert "job_id" in data
    job_id = data["job_id"]

    # 3. Poll /api/jobs/{id} until done
    max_wait = 30
    start = time.time()
    last_progress = -1.0
    seen_stages = set()

    while time.time() - start < max_wait:
        poll_resp = client.get(f"/api/jobs/{job_id}")
        assert poll_resp.status_code == 200
        job_data = poll_resp.json()

        seen_stages.add(job_data["stage"])
        assert job_data["progress"] >= last_progress, "Progress must be monotonic"
        last_progress = job_data["progress"]

        if job_data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert job_data["status"] == "succeeded"
    assert job_data["stage"] == "done"
    assert job_data["progress"] == 1.0
    assert job_data["result"] is not None
    assert job_data["result"]["success"] is True
    assert "analyzing" in seen_stages or "planning_outline" in seen_stages


def test_generate_sync_wait_mode(client, sample_docx_template):
    # Test ?wait=true synchronous mode for tests/CLI
    with open(sample_docx_template, "rb") as f:
        up_resp = client.post("/api/upload", files={"file": ("sync_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    template_id = up_resp.json()["template_id"]

    gen_resp = client.post("/api/generate?wait=true", json={"template_id": template_id, "prompt": "Summary report"})
    assert gen_resp.status_code == 200
    data = gen_resp.json()
    assert data["success"] is True
    assert data["download_url"].startswith("/api/download/")


def test_job_cancellation(client, sample_docx_template):
    with open(sample_docx_template, "rb") as f:
        up_resp = client.post("/api/upload", files={"file": ("cancel_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    template_id = up_resp.json()["template_id"]

    gen_resp = client.post("/api/generate", json={"template_id": template_id, "prompt": "Cancelled test"})
    assert gen_resp.status_code == 202
    job_id = gen_resp.json()["job_id"]

    del_resp = client.delete(f"/api/jobs/{job_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "cancelled"

    poll_resp = client.get(f"/api/jobs/{job_id}")
    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "cancelled"


def test_interrupted_job_recovery_on_startup(tmp_path):
    # Create a simulated interrupted snapshot
    stale_job_id = "test_interrupted_job_123"
    snapshot_path = settings.JOBS_DIR / f"{stale_job_id}.json"
    snapshot_data = {
        "job_id": stale_job_id,
        "status": "running",
        "stage": "writing_sections",
        "progress": 0.5,
        "message": "Writing in progress...",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    snapshot_path.write_text(json.dumps(snapshot_data), encoding="utf-8")

    # Call recovery
    job_manager.recover_interrupted_jobs()

    recovered = job_manager.get_job(stale_job_id)
    assert recovered.status == "failed"
    assert "interrupted" in recovered.message


def test_template_and_output_delete_endpoints(client, sample_docx_template):
    with open(sample_docx_template, "rb") as f:
        up_resp = client.post("/api/upload", files={"file": ("del_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    template_id = up_resp.json()["template_id"]

    # Verify template get endpoint
    get_resp = client.get(f"/api/templates/{template_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["template_id"] == template_id

    # Delete template
    del_resp = client.delete(f"/api/templates/{template_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # After deletion, getting should fail with 404
    get_after = client.get(f"/api/templates/{template_id}")
    assert get_after.status_code == 404
