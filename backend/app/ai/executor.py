from typing import Union, Dict, Any, Optional, List
from pathlib import Path
import logging

from ..engines.docx_engine import DocxEngine
from ..engines.pptx_engine import PptxEngine
from ..engines.style_lock import LockedTemplate, LockedPresentation
from ..models.generation import DocumentPlan, PresentationPlan, ThemeOverrideRequest
from ..models.template_spec import TemplateSpecification

logger = logging.getLogger(__name__)


class DocumentExecutor:
    """
    EXECUTOR mode (§24).
    Pure application code that applies structured plans to locked templates.
    Zero AI hallucination or style drift in this execution phase.
    """

    def __init__(self):
        self.docx_engine = DocxEngine()
        self.pptx_engine = PptxEngine()

    def execute_docx(
        self,
        template_path: str,
        spec: TemplateSpecification,
        plan: DocumentPlan,
        output_path: str,
        template_mode: str = "auto",
        body_anchor_index: Optional[int] = None,
        overrides: Optional[List[ThemeOverrideRequest]] = None,
        edit_action: Optional[str] = None,
        target_heading: Optional[str] = None,
        target_index: Optional[int] = None,
        warnings: Optional[List[str]] = None,
    ) -> str:
        """
        Executes a DocumentPlan against a locked DOCX template.
        """
        locked_doc = self.docx_engine.load_template(template_path, spec)
        output_file = self.docx_engine.generate_from_plan(
            locked_doc=locked_doc,
            plan=plan,
            output_path=output_path,
            template_mode=template_mode,
            body_anchor_index=body_anchor_index,
            overrides=overrides,
            edit_action=edit_action,
            target_heading=target_heading,
            target_index=target_index,
            warnings=warnings,
        )
        return output_file

    def execute_pptx(
        self,
        template_path: str,
        spec: TemplateSpecification,
        plan: PresentationPlan,
        output_path: str,
        keep_existing_slides: bool = False,
        warnings: Optional[List[str]] = None,
    ) -> str:
        """
        Executes a PresentationPlan against a locked PPTX template.
        """
        locked_prs = self.pptx_engine.load_template(template_path, spec)
        output_file = self.pptx_engine.generate_from_plan(
            locked_prs=locked_prs,
            plan=plan,
            output_path=output_path,
            keep_existing_slides=keep_existing_slides,
            warnings=warnings,
        )
        return output_file
