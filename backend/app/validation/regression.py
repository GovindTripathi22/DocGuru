from typing import Dict, Any, List
from pathlib import Path
import logging

from .style_hash import StyleHasher
from .diff_validator import DiffValidator
from ..analyzer.template_analyzer import TemplateAnalyzer
from ..ai.planner import DocumentPlanner
from ..ai.executor import DocumentExecutor
from ..config import settings

logger = logging.getLogger(__name__)

class RegressionRunner:
    """
    Format Regression Test Suite Runner (§19).
    """

    def __init__(self):
        self.analyzer = TemplateAnalyzer()
        self.planner = DocumentPlanner()
        self.executor = DocumentExecutor()
        self.validator = DiffValidator()

    async def run_regression_test(self, template_path: str, prompt: str = "Create a test benchmark document") -> Dict[str, Any]:
        """
        Executes complete regression flow:
        Template -> Extract Hash -> Plan -> Execute -> Extract Hash -> Compare
        """
        orig_spec = self.analyzer.analyze(template_path)
        orig_hash = orig_spec.style_hash

        temp_output = str(settings.TEMP_DIR / f"regression_test_{Path(template_path).name}")

        if orig_spec.document_type == "docx":
            plan = await self.planner.plan_document(prompt, orig_spec)
            gen_path = self.executor.execute_docx(template_path, orig_spec, plan, temp_output)
        elif orig_spec.document_type == "pptx":
            plan = await self.planner.plan_presentation(prompt, orig_spec)
            gen_path = self.executor.execute_pptx(template_path, orig_spec, plan, temp_output)
        else:
            return {"success": True, "message": "PDF format regression skipped (reference mode)"}

        validation = self.validator.validate(orig_spec, gen_path)

        return {
            "template_file": Path(template_path).name,
            "document_type": orig_spec.document_type,
            "original_style_hash": orig_hash,
            "generated_style_hash": validation.generated_style_hash,
            "hash_match": validation.hash_match,
            "passed": validation.passed,
            "issues": validation.issues
        }
