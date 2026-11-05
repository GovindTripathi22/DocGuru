import asyncio
import re
import time

import anyio
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.errors import AppError, LLMRateLimited
from backend.app.jobs.manager import JobManager, JobProgress
from backend.app.main import app, make_error_response
from backend.app.routes.analyze import AnalyzeRequest, analyze_template
from backend.app.security import (
    assert_resource_owner,
    check_rate_limit,
    register_resource_owner,
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_template_ids_are_opaque_and_foreign_sessions_cannot_read(
    client, sample_docx_template, tmp_path, monkeypatch
):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    with sample_docx_template.open("rb") as source:
        response = client.post(
            "/api/upload",
            files={
                "file": (
                    "quarterly report.docx",
                    source,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"X-Session-Id": "owner-session"},
        )

    assert response.status_code == 200
    payload = response.json()
    template_id = payload["template_id"]
    assert re.fullmatch(r"[0-9a-f]{32}\.docx", template_id)
    assert payload["template_spec"]["filename"] == "quarterly report.docx"

    owner = client.get(f"/api/templates/{template_id}", headers={"X-Session-Id": "owner-session"})
    foreign = client.get(f"/api/templates/{template_id}", headers={"X-Session-Id": "other-session"})
    assert owner.status_code == 200
    assert foreign.status_code == 404


def test_configured_api_keys_and_session_headers_are_required(monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", "first-secret, second-secret")
    client = TestClient(app)

    missing_key = client.get("/api/templates/missing")
    missing_session = client.get("/api/templates/missing", headers={"X-API-Key": "second-secret"})
    authenticated = client.get(
        "/api/templates/missing",
        headers={"X-API-Key": "second-secret", "X-Session-Id": "session-22"},
    )

    assert missing_key.status_code == 401
    assert missing_key.json()["error"]["code"] == "UNAUTHORIZED"
    assert missing_session.status_code == 401
    assert missing_session.json()["error"]["code"] == "SESSION_REQUIRED"
    assert authenticated.status_code == 404
    assert "X-Request-ID" in authenticated.headers


def test_template_and_job_owners_are_checked_even_when_session_header_is_absent(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    register_resource_owner("template", "abc.docx", "owner")
    assert_resource_owner("template", "abc.docx", "owner")
    with pytest.raises(AppError) as error:
        assert_resource_owner("template", "abc.docx", None)
    assert error.value.http_status == 404

    manager = JobManager()
    owned_job = JobProgress(job_id="owned", session_id="owner")
    manager.jobs[owned_job.job_id] = owned_job
    with pytest.raises(AppError):
        manager.get_job("owned")
    assert manager.get_job("owned", session_id="owner") is owned_job


def test_rate_limit_returns_a_retry_after_value(monkeypatch):
    import backend.app.security as security

    monkeypatch.setattr(security, "monotonic", lambda: 100.0)
    security._RATE_WINDOWS.clear()
    check_rate_limit("generates", "session-a", 1)
    with pytest.raises(LLMRateLimited) as error:
        check_rate_limit("generates", "session-a", 1)
    assert error.value.details["retry_after"] == 60
    response = make_error_response(
        error.value.code,
        error.value.message,
        "request-id",
        error.value.http_status,
        error.value.details,
    )
    assert response.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_app_lifespan_applies_configured_worker_pool_limit(monkeypatch):
    monkeypatch.setattr(settings, "WORKER_THREADS", 2)
    async with app.router.lifespan_context(app):
        limiter = anyio.to_thread.current_default_thread_limiter()
        assert limiter.total_tokens == 2


@pytest.mark.asyncio
async def test_reanalysis_runs_off_event_loop(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    template_id = "a" * 32 + ".docx"
    (upload_dir / template_id).write_bytes(b"template")
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")

    def slow_failure(_path: str):
        time.sleep(0.15)
        raise ValueError("scripted parse error")

    monkeypatch.setattr("backend.app.routes.analyze.analyzer.analyze", slow_failure)
    finished = asyncio.Event()
    ticks: list[float] = []

    async def invoke_analysis():
        try:
            await analyze_template(AnalyzeRequest(template_id=template_id), "analysis-owner")
        except AppError:
            pass
        finally:
            finished.set()

    async def heartbeat():
        while not finished.is_set():
            ticks.append(asyncio.get_running_loop().time())
            await asyncio.sleep(0.01)

    async with asyncio.TaskGroup() as group:
        group.create_task(invoke_analysis())
        group.create_task(heartbeat())

    gaps = [right - left for left, right in zip(ticks, ticks[1:])]
    assert ticks
    assert max(gaps, default=0) < 0.1
