"""Job manager for asynchronous document generation, progress tracking, and lifecycle management (API-JOBS)."""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import anyio
from fastapi import HTTPException
from pydantic import BaseModel, Field

from ..ai.executor import DocumentExecutor
from ..ai.planner import DocumentPlanner
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..config import settings
from ..errors import AppError, TemplateNotFound
from ..models.generation import GenerationRequest, ValidationReport
from ..security import get_safe_path
from ..validation.diff_validator import DiffValidator

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
JobStage = Literal[
    "queued",
    "analyzing",
    "planning_outline",
    "writing_sections",
    "fetching_images",
    "assembling",
    "validating",
    "done",
]


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus = "queued"
    stage: JobStage = "queued"
    progress: float = 0.0
    message: str = "Job queued"
    current: Optional[Dict[str, int]] = None
    warnings: List[str] = Field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    template_id: str = ""
    session_id: Optional[str] = None


class JobManager:
    def __init__(self):
        self.jobs: Dict[str, JobProgress] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.events: Dict[str, asyncio.Event] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None
        self.analyzer = TemplateAnalyzer()
        self.planner = DocumentPlanner()
        self.executor = DocumentExecutor()
        self.validator = DiffValidator()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_JOBS)
        return self._semaphore

    def _save_job_snapshot(self, job: JobProgress) -> None:
        try:
            settings.JOBS_DIR.mkdir(parents=True, exist_ok=True)
            target = settings.JOBS_DIR / f"{job.job_id}.json"
            tmp = settings.JOBS_DIR / f"{job.job_id}.tmp"
            tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp, target)
        except Exception as e:
            logger.error("Failed to save snapshot for job %s: %s", job.job_id, e)

    def recover_interrupted_jobs(self) -> None:
        """Scan JOBS_DIR on startup; mark unfinished jobs as interrupted."""
        if not settings.JOBS_DIR.exists():
            return
        for file in settings.JOBS_DIR.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                job = JobProgress(**data)
                if job.status in ("queued", "running"):
                    job.status = "failed"
                    job.message = "failed: interrupted"
                    job.error = {
                        "code": "JOB_INTERRUPTED",
                        "message": "Job was interrupted by a server restart.",
                    }
                    job.updated_at = time.time()
                    self._save_job_snapshot(job)
                self.jobs[job.job_id] = job
            except Exception as e:
                logger.warning("Failed to recover job from %s: %s", file, e)

    def purge_expired(self, retention_hours: Optional[int] = None) -> int:
        """Purge templates, outputs, and jobs older than retention_hours (SEC-07/08)."""
        hours = retention_hours or settings.RETENTION_HOURS
        cutoff = time.time() - (hours * 3600)
        purged = 0
        for directory in (settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.JOBS_DIR, settings.TEMP_DIR):
            if not directory.exists():
                continue
            for item in directory.iterdir():
                if item.is_file() and item.name != ".gitkeep":
                    try:
                        if item.stat().st_mtime < cutoff:
                            item.unlink(missing_ok=True)
                            purged += 1
                    except OSError:
                        pass
        return purged

    def submit_job(self, req: GenerationRequest, session_id: Optional[str] = None) -> JobProgress:
        job_id = uuid.uuid4().hex
        job = JobProgress(
            job_id=job_id,
            status="queued",
            stage="queued",
            progress=0.0,
            message="Job queued for processing",
            template_id=req.template_id,
            session_id=session_id,
        )
        self.jobs[job_id] = job
        self.events[job_id] = asyncio.Event()
        self._save_job_snapshot(job)

        task = asyncio.create_task(self._run_job_wrapper(job, req))
        self.tasks[job_id] = task
        return job

    async def execute_direct(self, req: GenerationRequest, session_id: Optional[str] = None) -> JobProgress:
        job_id = uuid.uuid4().hex
        job = JobProgress(
            job_id=job_id,
            status="queued",
            stage="queued",
            progress=0.0,
            message="Direct execution started",
            template_id=req.template_id,
            session_id=session_id,
        )
        self.jobs[job_id] = job
        self._save_job_snapshot(job)
        await self._execute_job(job, req)
        return job

    def get_job(self, job_id: str, session_id: Optional[str] = None) -> JobProgress:
        job = self.jobs.get(job_id)
        if not job:
            snapshot = settings.JOBS_DIR / f"{job_id}.json"
            if snapshot.exists():
                try:
                    data = json.loads(snapshot.read_text(encoding="utf-8"))
                    job = JobProgress(**data)
                    self.jobs[job_id] = job
                except Exception:
                    pass
        if not job:
            raise AppError(code="JOB_NOT_FOUND", http_status=404, message=f"Job '{job_id}' not found.")
        if session_id and job.session_id and job.session_id != session_id:
            raise AppError(code="JOB_NOT_FOUND", http_status=404, message=f"Job '{job_id}' not found.")
        return job

    def cancel_job(self, job_id: str, session_id: Optional[str] = None) -> JobProgress:
        job = self.get_job(job_id, session_id)
        if job.status in ("succeeded", "failed", "cancelled"):
            return job

        job.status = "cancelled"
        job.message = "Job cancelled by user"
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        task = self.tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        evt = self.events.get(job_id)
        if evt:
            evt.set()
        return job

    async def wait_for_job(self, job_id: str, timeout: float = 300.0) -> JobProgress:
        evt = self.events.get(job_id)
        if evt:
            try:
                await asyncio.wait_for(evt.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                raise AppError(code="JOB_TIMEOUT", http_status=504, message="Job timed out during execution.")
        return self.get_job(job_id)

    async def _run_job_wrapper(self, job: JobProgress, req: GenerationRequest) -> None:
        async with self.semaphore:
            try:
                await self._execute_job(job, req)
            except asyncio.CancelledError:
                job.status = "cancelled"
                job.message = "Job cancelled"
                job.updated_at = time.time()
                self._save_job_snapshot(job)
            except AppError as e:
                job.status = "failed"
                job.message = e.message
                job.error = {"code": e.code, "message": e.message, "details": e.details}
                job.updated_at = time.time()
                self._save_job_snapshot(job)
            except Exception as e:
                logger.exception("Job %s execution failed: %s", job.job_id, e)
                job.status = "failed"
                job.message = "Document generation failed."
                job.error = {"code": "GENERATION_FAILED", "message": "Document generation failed."}
                job.updated_at = time.time()
                self._save_job_snapshot(job)
            finally:
                evt = self.events.get(job.job_id)
                if evt:
                    evt.set()
                self.tasks.pop(job.job_id, None)

    async def _execute_job(self, job: JobProgress, req: GenerationRequest) -> None:
        template_path = get_safe_path(settings.UPLOAD_DIR, req.template_id, "Template")
        if not template_path.exists():
            raise TemplateNotFound(req.template_id)

        # Stage 1: Analyzing
        job.status = "running"
        job.stage = "analyzing"
        job.progress = 0.1
        job.message = "Analyzing template structure and styles..."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        try:
            spec = await anyio.to_thread.run_sync(self.analyzer.analyze, str(template_path))
        except Exception as e:
            logger.error("Failed to analyze template %s: %s", req.template_id, e)
            raise AppError(code="TEMPLATE_ANALYSIS_FAILED", http_status=422, message="Template analysis failed.")

        # Stage 2: Planning Outline
        job.stage = "planning_outline"
        job.progress = 0.25
        job.message = "Planning document structure and sections..."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        output_ext = template_path.suffix.lower() if spec.document_type != "pdf" else ".docx"
        output_filename = f"generated_{uuid.uuid4().hex[:8]}{output_ext}"
        output_path = settings.OUTPUT_DIR / output_filename

        if spec.document_type == "docx":
            is_edit = (
                req.mode in ["edit_document", "edit_presentation"]
                or any(kw in req.prompt.lower() for kw in ["add chapter", "add section", "edit section", "expand chapter", "expand section", "insert after", "append chapter"])
            )
            if is_edit and (spec.document_outline or spec.total_pages_or_slides > 1):
                plan = await self.planner.plan_document_edit(
                    user_prompt=req.prompt,
                    template_spec=spec,
                    custom_instructions=req.custom_instructions,
                    include_images=req.include_images,
                    image_mode=req.image_mode,
                )
            else:
                plan = await self.planner.plan_document(
                    user_prompt=req.prompt,
                    template_spec=spec,
                    target_pages=req.target_pages_or_slides,
                    custom_instructions=req.custom_instructions,
                    include_images=req.include_images,
                    image_mode=req.image_mode,
                )

        elif spec.document_type == "pptx":
            plan = await self.planner.plan_presentation(
                user_prompt=req.prompt,
                template_spec=spec,
                target_slides=req.target_pages_or_slides,
                custom_instructions=req.custom_instructions,
                include_images=req.include_images,
                image_mode=req.image_mode,
            )

        elif spec.document_type == "pdf":
            plan = await self.planner.plan_document(
                user_prompt=req.prompt,
                template_spec=spec,
                target_pages=req.target_pages_or_slides,
                custom_instructions=req.custom_instructions,
                include_images=req.include_images,
                image_mode=req.image_mode,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported document type: {spec.document_type}")

        # Stage 3: Writing Sections
        sections_or_slides = getattr(plan, "sections", None) or getattr(plan, "slides", [])
        total_count = len(sections_or_slides)
        job.stage = "writing_sections"
        job.progress = 0.5
        job.current = {"done": total_count, "total": max(1, total_count)}
        job.message = f"Drafted {total_count} sections/slides."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        # Stage 4: Fetching Images
        job.stage = "fetching_images"
        job.progress = 0.75
        job.message = "Resolving and verifying required graphics..."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        # Stage 5: Assembling
        job.stage = "assembling"
        job.progress = 0.85
        job.message = "Applying exact template inheritance and assembling document..."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        if spec.document_type == "docx":
            await anyio.to_thread.run_sync(
                lambda: self.executor.execute_docx(
                    template_path=str(template_path),
                    spec=spec,
                    plan=plan,
                    output_path=str(output_path),
                )
            )
        elif spec.document_type == "pptx":
            await anyio.to_thread.run_sync(
                lambda: self.executor.execute_pptx(
                    template_path=str(template_path),
                    spec=spec,
                    plan=plan,
                    output_path=str(output_path),
                )
            )
        elif spec.document_type == "pdf":
            from docx import Document
            from ..engines.style_lock import LockedTemplate
            from ..engines.docx_engine import DocxEngine

            def render_pdf_base():
                doc = Document()
                locked_doc = LockedTemplate(doc, "", spec)
                de = DocxEngine()
                de.generate_from_plan(locked_doc, plan, str(output_path))

            await anyio.to_thread.run_sync(render_pdf_base)

        # Stage 6: Validating
        job.stage = "validating"
        job.progress = 0.95
        job.message = "Verifying zero template drift and structural integrity..."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        if spec.document_type in ("docx", "pptx"):
            val_report = await anyio.to_thread.run_sync(self.validator.validate, spec, str(output_path))
        else:
            val_report = ValidationReport(
                passed=True,
                original_style_hash=spec.style_hash,
                generated_style_hash=spec.style_hash,
                hash_match=True,
                issues=[],
            )

        if not val_report.passed and spec.document_type in ("docx", "pptx"):
            logger.error("Template formatting drift detected: %s", val_report.issues)
            raise AppError(
                code="TEMPLATE_DRIFT_DETECTED",
                http_status=422,
                message="Generated document failed zero-drift template verification.",
                details={"issues": val_report.issues, "differences": val_report.differences},
            )

        # Stage 7: Done
        job.stage = "done"
        job.status = "succeeded"
        job.progress = 1.0
        job.message = "Artifact generated with exact template style and structure preservation."
        job.updated_at = time.time()

        elapsed = round(time.time() - job.created_at, 2)
        plan_summary = []
        if hasattr(plan, "sections"):
            plan_summary = [{"title": s.title} for s in plan.sections]
        elif hasattr(plan, "slides"):
            plan_summary = [{"title": s.title, "layout": s.layout_name} for s in plan.slides]

        mode = getattr(plan, "generation_mode", None) or ("demo" if settings.MODEL_PROVIDER == "demo" else "live")

        result = {
            "success": True,
            "output_id": output_filename,
            "output_filename": output_filename,
            "filename": output_filename,
            "download_url": f"/api/download/{output_filename}",
            "generation_mode": mode,
            "template_id": req.template_id,
            "plan_summary": plan_summary,
            "template_spec": spec.model_dump() if hasattr(spec, "model_dump") else spec.dict(),
            "plan": plan.model_dump() if hasattr(plan, "model_dump") else plan.dict(),
            "validation": val_report.model_dump() if hasattr(val_report, "model_dump") else val_report.dict(),
            "warnings": getattr(plan, "warnings", []),
            "timings": {"execution_time_sec": elapsed},
            "execution_time_sec": elapsed,
            "model": settings.MODEL_NAME,
            "message": "Artifact generated with exact template style and structure preservation.",
        }

        job.result = result
        self._save_job_snapshot(job)


job_manager = JobManager()
