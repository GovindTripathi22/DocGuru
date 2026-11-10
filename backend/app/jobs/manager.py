"""Job manager for asynchronous document generation, progress tracking, and lifecycle management (API-JOBS)."""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Literal

import anyio
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from ..ai.executor import DocumentExecutor
from ..ai.planner import DocumentPlanner
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..config import settings
from ..errors import AppError, LLMTimeout, TemplateNotFound
from ..models.generation import GenerationRequest, ValidationReport
from ..models.template_spec import TemplateSpecification
from ..security import get_safe_path, register_resource_owner
from ..validation.diff_validator import DiffValidator

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
JobStage = Literal[
    "queued",
    "analyzing",
    "planning_outline",
    "researching",
    "writing_sections",
    "fetching_images",
    "assembling",
    "validating",
    "done",
]


def select_enabled_template_rules(
    spec: TemplateSpecification, enabled_rule_indices: list[int] | None
) -> TemplateSpecification:
    """Return a planning copy with only user-selected extracted rules."""
    if enabled_rule_indices is None:
        return spec
    selected = set(enabled_rule_indices)
    planning_spec = spec.model_copy(deep=True)
    planning_spec.extracted_rules = [
        rule for index, rule in enumerate(spec.extracted_rules[:12]) if index in selected
    ]
    return planning_spec


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus = "queued"
    stage: JobStage = "queued"
    progress: float = 0.0
    message: str = "Job queued"
    current: dict[str, int] | None = None
    warnings: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    template_id: str = ""
    session_id: str | None = None


class JobManager:
    def __init__(self):
        self.jobs: dict[str, JobProgress] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.events: dict[str, asyncio.Event] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self.analyzer = TemplateAnalyzer()
        self.planner = DocumentPlanner()
        self.executor = DocumentExecutor()
        self.validator = DiffValidator()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_JOBS)
        return self._semaphore

    @staticmethod
    def _extract_author_and_guide(text: str) -> tuple[str | None, str | None]:
        author, guide = None, None
        m_author = re.search(
            r"\b(?:by|author|student):\s*([A-Za-z\s.]+?)(?:\s+guided|\s+guide|\s+under|\n|$)",
            text,
            re.I,
        )
        if not m_author:
            m_author = re.search(
                r"\b(?:submitted\s+by|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
                text,
            )
        if m_author:
            author = m_author.group(1).strip()

        m_guide = re.search(
            r"\b(?:guided\s+by|guide|advisor):\s*([A-Za-z\s.]+?)(?:\n|$)",
            text,
            re.I,
        )
        if not m_guide:
            m_guide = re.search(
                r"\b(?:guided\s+by|under\s+guidance\s+of)\s+((?:Dr\.|Prof\.)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
                text,
                re.I,
            )
        if m_guide:
            guide = m_guide.group(1).strip()

        return author, guide

    def _save_job_snapshot(self, job: JobProgress) -> None:
        try:
            settings.JOBS_DIR.mkdir(parents=True, exist_ok=True)
            target = settings.JOBS_DIR / f"{job.job_id}.json"
            tmp = settings.JOBS_DIR / f"{job.job_id}.tmp"
            tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp, target)
        except (OSError, TypeError, ValueError) as e:
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
            except (OSError, json.JSONDecodeError, TypeError, ValidationError, ValueError) as e:
                logger.warning("Failed to recover job from %s: %s", file, e)

    def purge_expired(self, retention_hours: int | None = None) -> int:
        """Purge templates, outputs, and jobs older than retention_hours (SEC-07/08)."""
        hours = retention_hours or settings.RETENTION_HOURS
        cutoff = time.time() - (hours * 3600)
        purged = 0
        for directory in (
            settings.UPLOAD_DIR,
            settings.OUTPUT_DIR,
            settings.JOBS_DIR,
            settings.TEMP_DIR,
            settings.DATA_DIR / "ownership",
        ):
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

    def submit_job(self, req: GenerationRequest, session_id: str | None = None) -> JobProgress:
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

    async def execute_direct(
        self, req: GenerationRequest, session_id: str | None = None
    ) -> JobProgress:
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

    def get_job(self, job_id: str, session_id: str | None = None) -> JobProgress:
        job = self.jobs.get(job_id)
        if not job:
            snapshot = settings.JOBS_DIR / f"{job_id}.json"
            if snapshot.exists():
                try:
                    data = json.loads(snapshot.read_text(encoding="utf-8"))
                    job = JobProgress(**data)
                    self.jobs[job_id] = job
                except (
                    OSError,
                    json.JSONDecodeError,
                    TypeError,
                    ValidationError,
                    ValueError,
                ) as exc:
                    logger.warning("Could not load job snapshot %s: %s", snapshot.name, exc)
        if not job:
            raise AppError(
                code="JOB_NOT_FOUND", http_status=404, message=f"Job '{job_id}' not found."
            )
        if job.session_id is not None and job.session_id != session_id:
            raise AppError(
                code="JOB_NOT_FOUND", http_status=404, message=f"Job '{job_id}' not found."
            )
        return job

    def cancel_job(self, job_id: str, session_id: str | None = None) -> JobProgress:
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
                raise AppError(
                    code="JOB_TIMEOUT", http_status=504, message="Job timed out during execution."
                )
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
            except Exception:  # noqa: BLE001 - convert unhandled job failures into a failed job snapshot
                logger.exception("Job %s execution failed", job.job_id)
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
        try:
            async with asyncio.timeout(settings.GENERATION_DEADLINE_SEC):
                await self._execute_job_inner(job, req)
        except TimeoutError as exc:
            raise LLMTimeout(
                f"Generation exceeded its {settings.GENERATION_DEADLINE_SEC}-second deadline."
            ) from exc

    async def _execute_job_inner(self, job: JobProgress, req: GenerationRequest) -> None:
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
        except Exception as e:  # noqa: BLE001 - analyzer exceptions are translated to a stable API error
            logger.error("Failed to analyze template %s: %s", req.template_id, e)
            raise AppError(
                code="TEMPLATE_ANALYSIS_FAILED",
                http_status=422,
                message="Template analysis failed.",
            )

        planning_spec = select_enabled_template_rules(spec, req.enabled_rule_indices)

        # Stage 2: Planning Outline
        job.stage = "planning_outline"
        job.progress = 0.25
        job.message = "Planning document structure and sections..."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        output_ext = template_path.suffix.lower() if spec.document_type != "pdf" else ".docx"
        output_filename = f"{uuid.uuid4().hex}{output_ext}"
        output_path = settings.OUTPUT_DIR / output_filename

        async def report_planning_progress(stage: str, done: int, total: int) -> None:
            total = max(1, total)
            job.stage = stage  # type: ignore[assignment]
            job.current = {"done": done, "total": total}
            if stage == "researching":
                job.progress = 0.27
                job.message = "Finding and checking source metadata for the requested topic..."
            else:
                job.progress = 0.30 + (0.36 * done / total)
                job.message = f"Writing section {done} of {total}..."
            job.updated_at = time.time()
            self._save_job_snapshot(job)

        if spec.document_type == "docx":
            is_edit = (
                req.mode in ["edit_document", "edit_presentation"] or req.edit_action is not None
            )
            if is_edit and (spec.document_outline or spec.total_pages_or_slides > 1):
                plan = await self.planner.plan_document_edit(
                    user_prompt=req.prompt,
                    template_spec=planning_spec,
                    custom_instructions=req.custom_instructions,
                    include_images=req.include_images,
                    image_mode=req.image_mode,
                )
            else:
                plan = await self.planner.plan_document(
                    user_prompt=req.prompt,
                    template_spec=planning_spec,
                    target_pages=req.target_pages,
                    detail_level=req.detail_level,
                    target_sections=req.target_sections,
                    custom_instructions=req.custom_instructions,
                    include_images=req.include_images,
                    image_mode=req.image_mode,
                    research_enabled=req.research_enabled,
                    on_progress=report_planning_progress,
                )

        elif spec.document_type == "pptx":
            plan = await self.planner.plan_presentation(
                user_prompt=req.prompt,
                template_spec=planning_spec,
                target_slides=req.target_slides,
                custom_instructions=req.custom_instructions,
                include_images=req.include_images,
                image_mode=req.image_mode,
                append_to_existing=req.mode == "edit_presentation",
            )

        elif spec.document_type == "pdf":
            plan = await self.planner.plan_document(
                user_prompt=req.prompt,
                template_spec=planning_spec,
                target_pages=req.target_pages,
                detail_level=req.detail_level,
                target_sections=req.target_sections,
                custom_instructions=req.custom_instructions,
                include_images=req.include_images,
                image_mode=req.image_mode,
                research_enabled=req.research_enabled,
                on_progress=report_planning_progress,
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported document type: {spec.document_type}"
            )

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
            if hasattr(plan, "author"):
                detected_author, detected_guide = self._extract_author_and_guide(
                    f"{req.prompt} {req.custom_instructions or ''}"
                )
                if not plan.author:
                    plan.author = req.author or detected_author or "Student Name"
                if not plan.guide:
                    plan.guide = req.guide or detected_guide or "Faculty Guide"

            await anyio.to_thread.run_sync(
                lambda: self.executor.execute_docx(
                    template_path=str(template_path),
                    spec=spec,
                    plan=plan,
                    output_path=str(output_path),
                    template_mode=req.template_mode,
                    body_anchor_index=req.body_anchor_index,
                    overrides=req.overrides,
                    edit_action=req.edit_action,
                    target_heading=req.edit_target_heading,
                    target_index=req.edit_target_index,
                    warnings=job.warnings,
                )
            )
        elif spec.document_type == "pptx":
            await anyio.to_thread.run_sync(
                lambda: self.executor.execute_pptx(
                    template_path=str(template_path),
                    spec=spec,
                    plan=plan,
                    output_path=str(output_path),
                    keep_existing_slides=req.mode == "edit_presentation",
                    warnings=job.warnings,
                )
            )
        elif spec.document_type == "pdf":
            from ..engines.docx_engine import DocxEngine
            from ..engines.pdf_reference import PdfReferenceBuilder
            from ..engines.style_lock import LockedTemplate

            def render_pdf_base():
                builder = PdfReferenceBuilder()
                doc = builder.build_docx_base(spec, output_path)
                locked_doc = LockedTemplate(doc, str(output_path), spec)
                de = DocxEngine()
                de.generate_from_plan(locked_doc, plan, str(output_path), warnings=job.warnings)

            await anyio.to_thread.run_sync(render_pdf_base)

        # Stage 6: Validating
        job.stage = "validating"
        job.progress = 0.95
        job.message = "Comparing supported template properties with the generated file..."
        job.updated_at = time.time()
        self._save_job_snapshot(job)

        if spec.document_type in ("docx", "pptx"):
            intentional_overrides = [ov.target for ov in req.overrides]
            val_report = await anyio.to_thread.run_sync(
                lambda: self.validator.validate(
                    spec,
                    str(output_path),
                    intentional_overrides=intentional_overrides,
                    original_file_path=str(template_path),
                )
            )
        else:
            val_report = ValidationReport(
                status="not_applicable",
                passed=True,
                original_style_hash=spec.style_hash,
                generated_style_hash=spec.style_hash,
                hash_match=True,
                issues=[],
                warnings=["PDF reference mode: layout is approximate."],
            )

        if not val_report.passed and spec.document_type in ("docx", "pptx"):
            logger.error("Template formatting drift detected: %s", val_report.issues)
            raise AppError(
                code="TEMPLATE_DRIFT_DETECTED",
                http_status=422,
                message="Generated document differs from one or more checked template properties.",
                details={"issues": val_report.issues, "differences": val_report.differences},
            )

        # Stage 7: Done
        job.stage = "done"
        job.status = "succeeded"
        job.progress = 1.0
        if val_report.status == "not_applicable":
            job.message = "Document generated in PDF reference mode (approximate layout)."
        else:
            job.message = "Document generated; review the validation results and warnings."
        job.updated_at = time.time()

        elapsed = round(time.time() - job.created_at, 2)
        plan_summary = []
        if hasattr(plan, "sections"):
            plan_summary = [{"title": s.title} for s in plan.sections]
        elif hasattr(plan, "slides"):
            plan_summary = [{"title": s.title, "layout": s.layout_name} for s in plan.slides]

        mode = getattr(plan, "generation_mode", None) or (
            "demo" if settings.MODEL_PROVIDER == "demo" else "live"
        )
        result_warnings = list(
            dict.fromkeys(
                [
                    *getattr(plan, "warnings", []),
                    *job.warnings,
                    *getattr(val_report, "warnings", []),
                ]
            )
        )

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
            "validation": val_report.model_dump()
            if hasattr(val_report, "model_dump")
            else val_report.dict(),
            "warnings": result_warnings,
            "research_sources": [
                source.model_dump() for source in getattr(plan, "research_sources", [])
            ],
            "timings": {"execution_time_sec": elapsed},
            "execution_time_sec": elapsed,
            "model": settings.MODEL_NAME,
            "message": "Document generated. Review the validation results and any warnings.",
        }

        register_resource_owner("output", output_filename, job.session_id)
        job.result = result
        self._save_job_snapshot(job)


job_manager = JobManager()
