"""Visual and Structural Diff Validation using package XML fingerprints (VAL-01, VAL-02)."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import docx
from pptx import Presentation

from ..analyzer.template_analyzer import TemplateAnalyzer
from ..models.generation import ComponentResult, ValidationReport
from ..models.template_spec import TemplateSpecification
from .fingerprint import fingerprint_package

logger = logging.getLogger(__name__)


class DiffValidator:
    def __init__(self):
        self.analyzer = TemplateAnalyzer()

    def validate(
        self,
        original_spec: TemplateSpecification,
        generated_file_path: str,
        intentional_overrides: Optional[List[str]] = None,
        original_file_path: Optional[str] = None,
    ) -> ValidationReport:
        gen_path = Path(generated_file_path)
        if not gen_path.exists():
            return ValidationReport(
                status="failed",
                passed=False,
                issues=["Generated file does not exist on disk."],
            )

        if original_spec.document_type == "pdf":
            return ValidationReport(
                status="not_applicable",
                passed=True,
                issues=[],
                warnings=["PDF template used: layout is approximate reference mode."],
            )

        # 1. Compute fingerprints
        orig_fp = None
        if original_file_path and Path(original_file_path).exists():
            orig_fp = fingerprint_package(original_file_path)
        else:
            # Check if template file exists in default uploads or temp
            cand = Path(original_spec.filename)
            if cand.exists():
                orig_fp = fingerprint_package(cand)

        gen_fp = fingerprint_package(gen_path)
        overrides_set = set(intentional_overrides or [])

        components: List[ComponentResult] = []
        issues: List[str] = []
        font_drift = False
        border_drift = False
        margin_drift = False
        layout_drift = False
        hf_preserved = True
        tbl_preserved = True

        if orig_fp and orig_fp.components:
            all_comp_names = sorted(set(orig_fp.components.keys()) | set(gen_fp.components.keys()))
            for name in all_comp_names:
                orig_h = orig_fp.components.get(name)
                gen_h = gen_fp.components.get(name)

                if orig_h == gen_h:
                    components.append(ComponentResult(name=name, status="identical"))
                elif name in overrides_set:
                    components.append(
                        ComponentResult(
                            name=name,
                            status="intentional_override",
                            detail=f"Component '{name}' changed due to explicit user override.",
                        )
                    )
                else:
                    components.append(
                        ComponentResult(
                            name=name,
                            status="changed",
                            detail=f"Component '{name}' drift detected: original={orig_h[:12]} vs generated={gen_h[:12]}",
                        )
                    )
                    issues.append(f"Template component '{name}' was modified during generation.")
                    if name in ("styles", "theme", "font_table", "doc_defaults"):
                        font_drift = True
                    elif name in ("page_setup", "slide_size"):
                        margin_drift = True
                    elif name in ("layouts", "masters"):
                        layout_drift = True
                    elif name == "headers_footers":
                        hf_preserved = False

        # 2. Re-extract spec from generated file for page/margin/header invariants
        gen_spec = self.analyzer.analyze(generated_file_path)

        # Check page setup & margin drift
        if original_spec.page and gen_spec.page:
            if original_spec.page.model_dump() != gen_spec.page.model_dump():
                margin_drift = True
                issues.append(f"Page setup or margin drift detected: original={original_spec.page.model_dump()} vs generated={gen_spec.page.model_dump()}")

        # Check slide dimensions & layout drift
        if original_spec.slide_dimensions and gen_spec.slide_dimensions:
            if original_spec.slide_dimensions.model_dump() != gen_spec.slide_dimensions.model_dump():
                layout_drift = True
                issues.append(f"Slide dimension drift detected: original={original_spec.slide_dimensions.model_dump()} vs generated={gen_spec.slide_dimensions.model_dump()}")

        if original_spec.available_layout_names and gen_spec.available_layout_names:
            if set(original_spec.available_layout_names) != set(gen_spec.available_layout_names):
                layout_drift = True
                issues.append("Slide layout drift detected: layout names mismatch")

        # Check headers & footers preservation
        if original_spec.header and gen_spec.header:
            if original_spec.header.has_content and not gen_spec.header.has_content:
                hf_preserved = False
                issues.append("Header content was lost during generation.")
        if original_spec.footer and gen_spec.footer:
            if original_spec.footer.has_content and not gen_spec.footer.has_content:
                hf_preserved = False
                issues.append("Footer content was lost during generation.")

        # Compute style hashes and match status
        orig_style_h = original_spec.style_hash or (orig_fp.style_hash if orig_fp else "")
        gen_style_h = gen_spec.style_hash or (gen_fp.style_hash if gen_fp else "")
        hash_match = (orig_style_h == gen_style_h) if (orig_style_h and gen_style_h) else True
        if orig_fp and gen_fp and orig_fp.style_hash and gen_fp.style_hash:
            if orig_fp.style_hash != gen_fp.style_hash:
                hash_match = False

        if not hash_match:
            if not any("style_hash" in i for i in issues):
                issues.append(f"Style hash mismatch: original='{orig_style_h}' != generated='{gen_style_h}'")
            if not margin_drift and not layout_drift:
                font_drift = True

        # 3. Content checks
        content_checks: Dict[str, bool] = {}
        try:
            if original_spec.document_type == "docx":
                doc = docx.Document(generated_file_path)
                content_checks["reopens_cleanly"] = True
                content_checks["has_content"] = len(doc.paragraphs) > 0 or len(doc.tables) > 0
                full_text = " ".join(p.text for p in doc.paragraphs)
                content_checks["no_unfilled_placeholders"] = not any(
                    token in full_text for token in ("{{title}}", "{{abstract}}", "{{author}}")
                )
            elif original_spec.document_type == "pptx":
                prs = Presentation(generated_file_path)
                content_checks["reopens_cleanly"] = True
                content_checks["has_content"] = len(prs.slides) > 0
                all_text = " ".join(
                    shape.text
                    for slide in prs.slides
                    for shape in slide.shapes
                    if hasattr(shape, "text")
                )
                content_checks["no_unfilled_placeholders"] = "Click to add text" not in all_text
        except Exception as e:
            content_checks["reopens_cleanly"] = False
            issues.append(f"Generated file corrupted or could not be reopened: {e}")

        # Derive final status
        has_critical_drift = any(c.status == "changed" for c in components) or not content_checks.get("reopens_cleanly", True)
        status = "failed" if (has_critical_drift or len(issues) > 0) else "passed"
        passed = (status != "failed")

        return ValidationReport(
            status=status,
            passed=passed,
            components=components,
            original_style_hash=orig_style_h,
            generated_style_hash=gen_style_h,
            hash_match=hash_match,
            font_drift_detected=font_drift,
            border_drift_detected=border_drift,
            margin_drift_detected=margin_drift,
            layout_drift_detected=layout_drift,
            header_footer_preserved=hf_preserved,
            table_formatting_preserved=tbl_preserved,
            issues=issues,

            differences={},
            intentional_overrides=list(overrides_set),
            content_checks=content_checks,
            original_fingerprint=orig_fp.components if orig_fp else None,
            generated_fingerprint=gen_fp.components if gen_fp else None,
        )
