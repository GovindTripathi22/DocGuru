"""Deterministic Demo Provider for offline testing and evaluation (Decision D4)."""

import json
import re
from typing import Any, Optional
from pydantic import BaseModel

from .base import LLMResult


class DemoProvider:
    """
    Deterministic, topic-agnostic provider.
    Never produces canned domain-specific texts (no AlphaGo/MCTS/ResNet).
    Labels output visibly with generation_mode='demo'.
    """

    def __init__(self, model_name: str = "demo-generator"):
        self.model_name = model_name

    def _extract_title(self, prompt: str) -> str:
        # If there are quotes like '...' or "...", extract the content inside quotes
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", prompt)
        if quoted:
            candidate = quoted[-1].strip()
            if candidate:
                cleaned = re.sub(r"[^\w\s-]", " ", candidate).strip()
                words = cleaned.split()
                if words:
                    return " ".join(words[:8]).title()

        # Strip common instruction prefixes
        clean_text = re.sub(
            r"^(enhance\s+this\s+prompt\s+for\s+[a-z0-9]+\s*:\s*|user\s+topic\s*/\s*request\s*:\s*)",
            "",
            prompt,
            flags=re.IGNORECASE,
        ).strip()
        cleaned = re.sub(r"[^\w\s-]", " ", clean_text).strip()
        words = cleaned.split()
        if not words:
            return "Document Report"
        return " ".join(words[:8]).title()

    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        schema: Optional[dict[str, Any] | type[BaseModel]] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResult:
        # Dispatch based on system prompt contract, never raw user message
        if "enhanced_prompt" in system.lower():
            title = self._extract_title(user)
            if "pptx" in system.lower() or "presentation" in user.lower() or "slide" in user.lower():
                enhanced = f"Create an executive presentation on '{title}'. Structure into cohesive slides with strategic vision, technical architecture, and implementation roadmap."
            else:
                enhanced = f"Generate a publication-grade executive report on '{title}'. Include executive summary, methodology, structured comparison table, and strategic recommendations."
            data = {"enhanced_prompt": enhanced}
            content_str = json.dumps(data)
            return LLMResult(
                content=content_str,
                parsed=data,
                finish_reason="stop",
                prompt_tokens=len(user.split()),
                completion_tokens=len(content_str.split()),
                model=self.model_name,
                generation_mode="demo",
            )

        is_presentation = "presentation" in system.lower() or "slide deck" in system.lower()
        title = self._extract_title(user)

        if is_presentation:
            data = {
                "presentation_title": title,
                "audience": "General Audience",
                "slides": [
                    {
                        "slide_number": 1,
                        "title": title,
                        "layout_name": "Title Slide",
                        "layout_role": "title",
                        "body_paragraphs": [
                            f"Overview of {title} prepared in demo mode.",
                        ],
                        "bullet_points": [],
                    },
                    {
                        "slide_number": 2,
                        "title": "Executive Summary",
                        "layout_name": "Title and Content",
                        "layout_role": "content",
                        "body_paragraphs": [
                            f"This executive summary outlines the primary objectives and key drivers for {title}."
                        ],
                        "bullet_points": [
                            "Comprehensive analysis of core project objectives",
                            "Strategic evaluation of existing benchmarks and metrics",
                            "Implementation milestones and organizational timeline",
                        ],
                    },
                    {
                        "slide_number": 3,
                        "title": "Key Findings & Analysis",
                        "layout_name": "Title and Content",
                        "layout_role": "content",
                        "body_paragraphs": [
                            "Operational metrics and baseline data gathered across key performance categories."
                        ],
                        "bullet_points": [
                            "Established reliable performance baselines across critical indicators",
                            "Identified high-impact areas for optimization and efficiency gains",
                            "Synthesized multi-source requirements into an actionable framework",
                        ],
                    },
                    {
                        "slide_number": 4,
                        "title": "Strategic Recommendations",
                        "layout_name": "Title and Content",
                        "layout_role": "content",
                        "body_paragraphs": [
                            "Recommended actions to achieve target performance standards."
                        ],
                        "bullet_points": [
                            "Deploy verified procedures with continuous monitoring",
                            "Align organizational resources with high-priority deliverables",
                            "Conduct periodic review cycles to measure incremental progress",
                        ],
                    },
                ],
            }
        else:
            data = {
                "title": title,
                "document_type": "docx",
                "target_audience": "Stakeholders & Management",
                "sections": [
                    {
                        "section_number": 1,
                        "title": "Executive Summary",
                        "heading_level": 1,
                        "paragraphs": [
                            f"This document provides a structured analysis of {title}. The objectives are formulated to ensure consistency, transparency, and operational rigor throughout implementation.",
                            "All operational indicators and recommendations detailed in this report reflect baseline measurements and structured analysis."
                        ],
                        "bullet_points": [
                            "Strategic alignment with core organizational objectives",
                            "Systematic tracking of milestones and target benchmarks",
                            "Risk evaluation and mitigation protocols",
                        ],
                        "table": {
                            "caption": "Project Performance Indicators",
                            "headers": ["Metric", "Baseline", "Target", "Status"],
                            "rows": [
                                ["Implementation Efficiency", "78%", "95%", "On Track"],
                                ["Quality Assurance Index", "84%", "98%", "In Progress"],
                                ["Resource Utilization", "72%", "90%", "Target Met"],
                            ]
                        }
                    },
                    {
                        "section_number": 2,
                        "title": "Detailed Findings & Analysis",
                        "heading_level": 1,
                        "paragraphs": [
                            "A thorough evaluation of operational performance highlights critical areas of progress and key opportunities for improvement.",
                            "Systematic data collection across operational units confirms that target benchmarks are achievable with focused intervention."
                        ],
                        "bullet_points": [
                            "Identified primary drivers of variance and performance trends",
                            "Validated core operating assumptions against field observations",
                            "Established structured metrics to quantify outcome improvements",
                        ],
                    },
                    {
                        "section_number": 3,
                        "title": "Strategic Next Steps",
                        "heading_level": 1,
                        "paragraphs": [
                            "Building on the findings presented, prioritized initiatives should focus on continuous improvement and milestone adherence.",
                            "Regular review sessions will ensure alignment across teams and allow timely adjustments to shifting operational requirements."
                        ],
                        "bullet_points": [
                            "Initiate execution of priority workstreams",
                            "Establish automated monitoring dashboards",
                            "Conduct quarterly performance reviews",
                        ],
                    },
                ],
                "conclusion": f"In conclusion, {title} establishes a reliable foundation for achieving strategic and operational goals. Continued adherence to structured execution will ensure sustained success.",
            }

        content_str = json.dumps(data)
        return LLMResult(
            content=content_str,
            parsed=data,
            finish_reason="stop",
            prompt_tokens=len(user.split()),
            completion_tokens=len(content_str.split()),
            model=self.model_name,
            generation_mode="demo",
        )
