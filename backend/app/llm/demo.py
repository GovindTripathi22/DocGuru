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
        if "DOCGURU_TASK: DOCUMENT_OUTLINE" in system:
            user_request = self._field_value(user, "User request:", "\nLength detail:")
            title = self._extract_title(user_request)
            count_match = re.search(r"Return exactly\s+(\d+)\s+ordered sections", system)
            count = int(count_match.group(1)) if count_match else 3
            titles = [
                "Purpose and Scope",
                "Context and Key Concepts",
                "Current Landscape",
                "Options and Tradeoffs",
                "Implementation Considerations",
                "Risks and Mitigations",
                "Evaluation Approach",
                "Recommendations",
                "Operational Planning",
                "Governance and Review",
                "Dependencies and Constraints",
                "Long-Term Considerations",
            ]
            sections = []
            for index in range(count):
                section_title = titles[index] if index < len(titles) else f"Additional Consideration {index + 1}"
                sections.append({
                    "title": section_title,
                    "goal": f"Frame {section_title.lower()} in relation to {title}, without assuming facts absent from the prompt.",
                    "target_words": 300,
                })
            data = {
                "title": title,
                "target_audience": "General audience; adapt the final document to the user's stated context.",
                "sections": sections,
                "conclusion_goal": f"Summarize the requested scope of {title} and practical next steps.",
            }
            return self._result(data, user)

        if "DOCGURU_TASK: DOCUMENT_SECTION_QUALITY" in system:
            try:
                review_input = json.loads(user)
                section = review_input.get("draft", {})
                content = " ".join(
                    [
                        *section.get("paragraphs", []),
                        *section.get("bullet_points", []),
                        *section.get("citations", []),
                    ]
                )
                table = section.get("table") or {}
                if isinstance(table, dict):
                    content += " " + " ".join(table.get("headers", []))
                    content += " " + " ".join(cell for row in table.get("rows", []) for cell in row)
                words = content.split()
                target_words = int(review_input.get("target_words", 0))
                issues = []
                if len(words) < max(100, int(target_words * 0.75)):
                    issues.append("Expand the section to cover its goal at the requested level of detail.")
                paragraph_text = " ".join(section.get("paragraphs", []))
                sentences = [sentence.strip().lower() for sentence in re.split(r"(?<=[.!?])\s+", paragraph_text)]
                nonempty_sentences = [sentence for sentence in sentences if sentence]
                if len(nonempty_sentences) != len(set(nonempty_sentences)):
                    issues.append("Remove repeated sentences and improve the section's logical flow.")
                request_terms = {
                    token.lower()
                    for token in re.findall(r"[A-Za-z0-9]{5,}", review_input.get("user_request", ""))
                    if token.lower() not in {"about", "which", "their", "there", "would", "could", "should", "create", "write", "report", "document"}
                }
                if request_terms and not (request_terms & {token.lower() for token in re.findall(r"[A-Za-z0-9]{4,}", content)}):
                    issues.append("Tie the section explicitly to the requested topic.")
                review_data = {"passed": not issues, "issues": issues}
            except (ValueError, TypeError, AttributeError):
                review_data = {"passed": False, "issues": ["Repair the section so its structure can be reviewed."]}
            return self._result(review_data, user)

        if "DOCGURU_TASK: DOCUMENT_SECTION" in system:
            user_request = self._field_value(user, "User request:", "\nSection title:")
            section_title = self._field_value(user, "Section title:", "\nGoal:")
            topic = self._extract_title(user_request)
            goal = self._field_value(user, "Goal:", "\nTarget words:")
            target_match = re.search(r"approximately\s+(\d+)\s+words", system)
            target_words = int(target_match.group(1)) if target_match else 250
            is_final = "For the final section" in system
            paragraphs = self._demo_section_paragraphs(topic, section_title, goal, target_words)
            section = {
                "title": section_title,
                "paragraphs": paragraphs,
                "bullets": [],
                "citations": [],
            }
            if re.search(r"\b(?:table|compare|comparison|benchmark)\b", user_request, re.IGNORECASE) and re.search(
                r"\b(?:purpose and scope|requested scope|executive summary|overview|analysis|options|tradeoffs?)\b",
                section_title,
                re.IGNORECASE,
            ):
                section["table"] = {
                    "caption": "Comparison framework — populate with project-specific evidence",
                    "headers": ["Evaluation dimension", "What to compare", "Evidence to confirm"],
                    "rows": [
                        ["Objectives", "Fit with the requested outcome", "User-approved goals and constraints"],
                        ["Implementation", "Dependencies, effort, and operational impact", "Validated requirements and resource estimates"],
                        ["Risk", "Tradeoffs and conditions that could change the choice", "Documented risks and review criteria"],
                    ],
                }
            if is_final:
                section["conclusion"] = (
                    f"This demonstration has framed {topic} through the scope and considerations in this document. "
                    "Use the outline as a starting point, then validate details against authoritative material relevant to the intended audience."
                )
            return self._result({"section": section}, user)

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
                "target_audience": "General audience; adapt to the context in the user's request.",
                "sections": [
                    {
                        "section_number": 1,
                        "title": "Requested Scope",
                        "heading_level": 1,
                        "paragraphs": [
                            f"This demonstration provides a planning scaffold for {title}. Confirm the intended audience, scope, and decisions before using it.",
                            "Separate information supplied in the request from assumptions that still need authoritative evidence."
                        ],
                        "bullet_points": [
                            "State the objective and the boundaries of the requested work",
                            "Identify decisions, responsibilities, and information gaps",
                            "Validate factual details against appropriate sources before use",
                        ],
                    },
                    {
                        "section_number": 2,
                        "title": "Considerations",
                        "heading_level": 1,
                        "paragraphs": [
                            f"Review {title} through the goals, constraints, and tradeoffs described by the user.",
                            "Where key context is missing, request clarification or state the uncertainty instead of supplying an invented fact."
                        ],
                        "bullet_points": [
                            "Compare options using criteria relevant to the requested outcome",
                            "Record dependencies and risks that need further investigation",
                            "Define how evidence and results will be reviewed",
                        ],
                    },
                    {
                        "section_number": 3,
                        "title": "Next Steps",
                        "heading_level": 1,
                        "paragraphs": [
                            "Translate the confirmed scope into practical tasks and assign responsibility using the user's organizational context.",
                            "Review the completed work with relevant stakeholders and update it when better evidence becomes available."
                        ],
                        "bullet_points": [
                            "Confirm required inputs and decision owners",
                            "Document evidence and unresolved questions",
                            "Set a review approach that fits the intended use",
                        ],
                    },
                ],
                "conclusion": f"This demo scaffold outlines considerations for {title}. Validate every factual detail and adapt recommendations to the supplied context.",
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

    @staticmethod
    def _field_value(text: str, start: str, end: str) -> str:
        if start not in text:
            return ""
        value = text.split(start, 1)[1]
        if end in value:
            value = value.split(end, 1)[0]
        return value.strip()

    @staticmethod
    def _demo_section_paragraphs(topic: str, section_title: str, goal: str, target_words: int) -> list[str]:
        """Build a clearly labeled, non-factual scaffold for offline demo mode."""
        aspects = [
            "define the decision or question the section is meant to address",
            "identify the audience, context, and constraints that shape the discussion",
            "separate established information from assumptions that still need checking",
            "compare plausible approaches using criteria that matter to the intended outcome",
            "consider dependencies, tradeoffs, and operational consequences",
            "describe what evidence would support or challenge each conclusion",
            "make responsibilities and decision points explicit",
            "outline how progress and results could be reviewed",
            "identify uncertainty and explain what additional information would reduce it",
            "connect the analysis to a practical next step",
        ]
        sentences = [
            f"For {topic}, this section focuses on {section_title.lower()} and aims to {goal.rstrip('.').lower()}"
        ]
        for aspect in aspects:
            sentences.append(f"A useful treatment should {aspect} in the context of {topic}")
        sentences.extend([
            f"The discussion should distinguish a recommendation about {topic} from the evidence available to support it",
            "Where the prompt leaves a detail open, the final document should state the uncertainty or request clarification instead of filling the gap with an invented fact",
        ])
        text = ". ".join(sentences) + "."
        while len(text.split()) < max(80, target_words):
            for aspect in aspects:
                addition = f"For this part of {topic}, the author can {aspect} before drawing a conclusion"
                text += " " + addition + "."
                if len(text.split()) >= max(80, target_words):
                    break
        return [text]

    def _result(self, data: dict[str, Any], user: str) -> LLMResult:
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
