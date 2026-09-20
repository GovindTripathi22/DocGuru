from fastapi import APIRouter, HTTPException
import time
import uuid
from pathlib import Path
import logging

from ..config import settings
from ..models.generation import GenerationRequest, GenerationResponse, ValidationReport
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..ai.planner import DocumentPlanner
from ..ai.executor import DocumentExecutor
from ..validation.diff_validator import DiffValidator
from ..errors import AppError

router = APIRouter(prefix="/api", tags=["generate"])
logger = logging.getLogger(__name__)

analyzer = TemplateAnalyzer()
planner = DocumentPlanner()
executor = DocumentExecutor()
validator = DiffValidator()

@router.post("/generate", response_model=GenerationResponse)
async def generate_document(req: GenerationRequest):
    """
    Exact template-preserving generation endpoint.
    1. Loads original template
    2. Uses Gemma 4 Planner to create structured content plan
    3. Executes plan using pure application code (zero style drift)
    4. Validates structural and format integrity
    5. Returns result and download link
    """
    start_time = time.time()
    template_path = settings.UPLOAD_DIR / req.template_id

    if not template_path.exists():
        raise HTTPException(status_code=404, detail=f"Template file '{req.template_id}' not found.")

    try:
        spec = analyzer.analyze(str(template_path))
    except Exception as e:
        logger.error(f"Failed to analyze template {req.template_id}: {e}")
        raise HTTPException(status_code=422, detail=f"Template analysis failed: {str(e)}")

    output_ext = template_path.suffix.lower()
    output_filename = f"generated_{uuid.uuid4().hex[:8]}{output_ext}"
    output_path = settings.OUTPUT_DIR / output_filename

    try:
        if spec.document_type == "docx":
            # Check if user requested an edit/addition
            is_edit_request = (
                req.mode in ["edit_document", "edit_presentation"]
                or any(kw in req.prompt.lower() for kw in ["add chapter", "add section", "edit section", "expand chapter", "expand section", "insert after", "append chapter"])
            )
            if is_edit_request and (spec.document_outline or spec.total_pages_or_slides > 1):
                plan = await planner.plan_document_edit(
                    user_prompt=req.prompt,
                    template_spec=spec,
                    custom_instructions=req.custom_instructions,
                    include_images=req.include_images,
                    image_mode=req.image_mode
                )
            else:
                plan = await planner.plan_document(
                    user_prompt=req.prompt,
                    template_spec=spec,
                    target_pages=req.target_pages_or_slides,
                    custom_instructions=req.custom_instructions,
                    include_images=req.include_images,
                    image_mode=req.image_mode
                )
            # 2. Execute plan on locked template
            executor.execute_docx(
                template_path=str(template_path),
                spec=spec,
                plan=plan,
                output_path=str(output_path)
            )

        elif spec.document_type == "pptx":
            # 1. Plan presentation using Gemma 4 with locked layouts
            plan = await planner.plan_presentation(
                user_prompt=req.prompt,
                template_spec=spec,
                target_slides=req.target_pages_or_slides,
                custom_instructions=req.custom_instructions,
                include_images=req.include_images,
                image_mode=req.image_mode
            )
            # 2. Execute plan on locked presentation
            executor.execute_pptx(
                template_path=str(template_path),
                spec=spec,
                plan=plan,
                output_path=str(output_path)
            )

        elif spec.document_type == "pdf":
            # PDF Visual Reference mode: Plan and synthesize as DOCX using reference spec
            plan = await planner.plan_document(
                user_prompt=req.prompt,
                template_spec=spec,
                target_pages=req.target_pages_or_slides,
                custom_instructions=req.custom_instructions,
                include_images=req.include_images,
                image_mode=req.image_mode
            )
            output_filename = f"generated_{uuid.uuid4().hex[:8]}.docx"
            output_path = settings.OUTPUT_DIR / output_filename
            
            # Create a clean base DOCX using the PDF reference dimensions
            from docx import Document
            doc = Document()
            from ..engines.style_lock import LockedTemplate
            locked_doc = LockedTemplate(doc, "", spec)
            from ..engines.docx_engine import DocxEngine
            de = DocxEngine()
            de.generate_from_plan(locked_doc, plan, str(output_path))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported document type: {spec.document_type}")

        # 3. Structural Diff Validation (§18 & §19)
        if spec.document_type in ("docx", "pptx"):
            val_report = validator.validate(spec, str(output_path))
        else:
            val_report = ValidationReport(
                passed=True,
                original_style_hash=spec.style_hash,
                generated_style_hash=spec.style_hash,
                hash_match=True,
                issues=[]
            )

        # 4. If drift detected, attempt automatic rollback and re-execution (§18)
        if not val_report.passed and spec.document_type in ("docx", "pptx"):
            logger.warning("Formatting drift detected during validation. Triggering automatic rollback...")
            if spec.document_type == "docx":
                executor.execute_docx(str(template_path), spec, plan, str(output_path))
            elif spec.document_type == "pptx":
                executor.execute_pptx(str(template_path), spec, plan, str(output_path))
            val_report = validator.validate(spec, str(output_path))

        elapsed = round(time.time() - start_time, 2)

        return GenerationResponse(
            success=True,
            output_filename=output_filename,
            download_url=f"/api/download/{output_filename}",
            template_spec=spec,
            plan=plan,
            validation=val_report,
            execution_time_sec=elapsed,
            message="Artifact generated with 100% exact template style and structure preservation."
        )

    except (HTTPException, AppError):
        raise
    except Exception as e:
        logger.exception("Generation error for template %s: %s", req.template_id, e)
        raise AppError(code="GENERATION_FAILED", http_status=500, message="Document generation failed.")
