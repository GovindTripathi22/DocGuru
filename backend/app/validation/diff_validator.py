from typing import Dict, Any, List, Optional
import logging
from pathlib import Path

from ..models.template_spec import TemplateSpecification
from ..models.generation import ValidationReport, DocumentPlan, PresentationPlan
from ..analyzer.template_analyzer import TemplateAnalyzer

logger = logging.getLogger(__name__)

class DiffValidator:
    """
    Visual and Structural Diff Validation (§18).
    Compares original template structural properties against generated document.
    """

    def __init__(self):
        self.analyzer = TemplateAnalyzer()

    def validate(
        self,
        original_spec: TemplateSpecification,
        generated_file_path: str
    ) -> ValidationReport:
        """
        Extracts spec from generated document and compares all structural properties
        against the original template specification.
        """
        gen_spec = self.analyzer.analyze(generated_file_path)

        report = ValidationReport(
            original_style_hash=original_spec.style_hash,
            generated_style_hash=gen_spec.style_hash,
            hash_match=(original_spec.style_hash == gen_spec.style_hash),
            passed=True,
            issues=[]
        )

        differences = {}

        # 1. Check Page Dimensions & Margins (DOCX)
        if original_spec.page and gen_spec.page:
            orig_p = original_spec.page
            gen_p = gen_spec.page
            if abs(orig_p.width_pt - gen_p.width_pt) > 1.0 or abs(orig_p.height_pt - gen_p.height_pt) > 1.0:
                report.passed = False
                report.margin_drift_detected = True
                report.issues.append(f"Page dimension drift: {orig_p.width_pt}x{orig_p.height_pt}pt -> {gen_p.width_pt}x{gen_p.height_pt}pt")

            if orig_p.margins.model_dump() != gen_p.margins.model_dump():
                report.passed = False
                report.margin_drift_detected = True
                report.issues.append("Margin drift detected in generated document.")
                differences["margins"] = {
                    "original": orig_p.margins.model_dump(),
                    "generated": gen_p.margins.model_dump()
                }

        # 2. Check Slide Dimensions (PPTX)
        if original_spec.slide_dimensions and gen_spec.slide_dimensions:
            orig_sd = original_spec.slide_dimensions
            gen_sd = gen_spec.slide_dimensions
            if abs(orig_sd.width_inches - gen_sd.width_inches) > 0.01 or abs(orig_sd.height_inches - gen_sd.height_inches) > 0.01:
                report.passed = False
                report.layout_drift_detected = True
                report.issues.append(f"Slide dimension drift: {orig_sd.width_inches}x{orig_sd.height_inches} -> {gen_sd.width_inches}x{gen_sd.height_inches}")

        # 3. Check Slide Masters and Layouts (PPTX)
        if original_spec.layouts and gen_spec.layouts:
            if len(gen_spec.layouts) < len(original_spec.layouts):
                report.layout_drift_detected = True
                report.issues.append("Slide layout count mismatch between template and generated presentation.")

        # 4. Check Headers & Footers (DOCX)
        if original_spec.header and gen_spec.header:
            if original_spec.header.has_content and not gen_spec.header.has_content:
                report.header_footer_preserved = False
                report.issues.append("Header content was missing in generated document.")

        if original_spec.footer and gen_spec.footer:
            if original_spec.footer.has_page_number and not gen_spec.footer.has_page_number:
                report.header_footer_preserved = False
                report.issues.append("Page number in footer was lost in generated document.")

        report.differences = differences
        return report
