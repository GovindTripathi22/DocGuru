from typing import Dict, Any, Tuple
import hashlib
import json
from pathlib import Path
from ..analyzer.template_analyzer import TemplateAnalyzer

class StyleHasher:
    """
    Computes and compares deterministic style hashes across original templates
    and generated documents to guarantee zero formatting regression (§19).
    """

    def __init__(self):
        self.analyzer = TemplateAnalyzer()

    def compute_hash(self, file_path: str) -> str:
        """
        Extracts template specification from file and returns its deterministic style hash.
        """
        spec = self.analyzer.analyze(file_path)
        return spec.style_hash

    def compare_hashes(self, original_file_path: str, generated_file_path: str) -> Tuple[bool, str, str, Dict[str, Any]]:
        """
        Compares style hashes between original template and generated document.
        Returns: (is_match, original_hash, generated_hash, differences)
        """
        orig_spec = self.analyzer.analyze(original_file_path)
        gen_spec = self.analyzer.analyze(generated_file_path)

        orig_hash = orig_spec.style_hash
        gen_hash = gen_spec.style_hash
        is_match = (orig_hash == gen_hash)

        differences = {}
        if not is_match:
            # Inspect page specs
            if orig_spec.page and gen_spec.page:
                if orig_spec.page.model_dump() != gen_spec.page.model_dump():
                    differences["page"] = {
                        "original": orig_spec.page.model_dump(),
                        "generated": gen_spec.page.model_dump()
                    }
            # Inspect slide dimensions
            if orig_spec.slide_dimensions and gen_spec.slide_dimensions:
                if orig_spec.slide_dimensions.model_dump() != gen_spec.slide_dimensions.model_dump():
                    differences["slide_dimensions"] = {
                        "original": orig_spec.slide_dimensions.model_dump(),
                        "generated": gen_spec.slide_dimensions.model_dump()
                    }

        return is_match, orig_hash, gen_hash, differences
