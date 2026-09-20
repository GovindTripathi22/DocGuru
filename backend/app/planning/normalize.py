"""Plan normalization, sanitization, and rich-text span parsing (LLM-04, LLM-05, LLM-06)."""

from dataclasses import dataclass
import logging
import re
import unicodedata
from typing import Any, Optional

from ..errors import LLMInvalidResponse

logger = logging.getLogger(__name__)

# XML 1.0 illegal characters regex
XML_ILLEGAL_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")

# Markdown heading and bullet markers at start of text
LEADING_MARKDOWN_HEADING_REGEX = re.compile(r"^\s*#{1,6}\s*")
LEADING_MARKDOWN_BULLET_REGEX = re.compile(r"^\s*[-*•]\s+")


@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False


RichText = list[Span]


def parse_inline_emphasis(text: str) -> RichText:
    """
    Parses inline markdown tokens (**bold**, *italic*, _italic_, `code`)
    into a sequence of Span objects with formatting flags.
    No raw markdown delimiters remain in span texts.
    """
    if not text:
        return []

    # Combined regex to match bold (**...**), code (`...`), italic (*...* or _..._)
    pattern = re.compile(
        r"(?P<bold>\*\*(?P<bold_text>.+?)\*\*)"
        r"|(?P<code>`(?P<code_text>.+?)`)"
        r"|(?P<italic_star>\*(?P<italic_star_text>[^*]+?)\*)"
        r"|(?P<italic_under>_(?P<italic_under_text>[^_]+?)_)"
    )

    spans: RichText = []
    last_idx = 0

    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            spans.append(Span(text=text[last_idx:start]))

        if match.group("bold"):
            spans.append(Span(text=match.group("bold_text"), bold=True))
        elif match.group("code"):
            spans.append(Span(text=match.group("code_text"), code=True))
        elif match.group("italic_star"):
            spans.append(Span(text=match.group("italic_star_text"), italic=True))
        elif match.group("italic_under"):
            spans.append(Span(text=match.group("italic_under_text"), italic=True))

        last_idx = end

    if last_idx < len(text):
        spans.append(Span(text=text[last_idx:]))

    return spans


def strip_markdown_delimiters(text: str) -> str:
    """Removes inline markdown delimiters without span breakdown."""
    spans = parse_inline_emphasis(text)
    return "".join(s.text for s in spans)


def sanitize_text(text: Any, max_len: Optional[int] = None, field_name: str = "field") -> str:
    """
    Sanitizes arbitrary scalar values into clean, XML-legal, normalized unicode strings.
    Strips XML illegal control characters, collapses excessive whitespace,
    removes leading markdown heading/bullet syntax, and enforces length caps.
    """
    if text is None:
        return ""
    if isinstance(text, float):
        # Avoid trailing .0 noise for whole numbers (e.g. 2020.0 -> "2020")
        if text.is_integer():
            text = int(text)
    text_str = str(text)

    # 1. Normalize unicode (NFC)
    text_str = unicodedata.normalize("NFC", text_str)

    # 2. Strip XML-illegal control characters
    text_str = XML_ILLEGAL_REGEX.sub("", text_str)

    # 3. Strip leading markdown headings and list markers
    text_str = LEADING_MARKDOWN_HEADING_REGEX.sub("", text_str)
    text_str = LEADING_MARKDOWN_BULLET_REGEX.sub("", text_str)

    # 4. Collapse excessive whitespace
    text_str = re.sub(r"[ \t]+", " ", text_str)
    text_str = re.sub(r"\n{3,}", "\n\n", text_str)
    text_str = text_str.strip()

    # 5. Cap length if requested
    if max_len is not None and len(text_str) > max_len:
        logger.warning("Field '%s' length %d exceeded max %d; truncating", field_name, len(text_str), max_len)
        text_str = text_str[:max_len].rstrip()

    return text_str


def normalize_plan(raw_plan: dict[str, Any], doc_type: str = "docx") -> dict[str, Any]:
    """
    Normalizes and sanitizes raw model output dictionary into schema-tolerant plan.
    Ensures empty plans are rejected with LLMInvalidResponse.
    """
    if not isinstance(raw_plan, dict) or not raw_plan:
        raise LLMInvalidResponse("The model returned an empty or non-dictionary response.")

    is_presentation = doc_type == "pptx" or "slides" in raw_plan or "presentation_title" in raw_plan

    if is_presentation:
        return _normalize_presentation_plan(raw_plan)
    else:
        return _normalize_document_plan(raw_plan)


def _normalize_document_plan(raw: dict[str, Any]) -> dict[str, Any]:
    title = sanitize_text(raw.get("title") or raw.get("document_title") or "Document Report", max_len=200, field_name="title")
    target_audience = sanitize_text(raw.get("target_audience") or "General Audience", max_len=200, field_name="target_audience")
    conclusion = sanitize_text(raw.get("conclusion") or "", max_len=4000, field_name="conclusion")

    raw_sections = raw.get("sections")
    if not isinstance(raw_sections, list) or len(raw_sections) == 0:
        raise LLMInvalidResponse("Document plan contains no sections.")

    normalized_sections = []
    total_content_elements = 0

    for idx, sec in enumerate(raw_sections):
        if not isinstance(sec, dict):
            continue

        sec_title = sanitize_text(sec.get("title") or f"Section {idx + 1}", max_len=200, field_name="section_title")
        heading_level = sec.get("heading_level", 1)
        try:
            heading_level = int(heading_level)
        except (ValueError, TypeError):
            heading_level = 1

        # Paragraphs
        raw_paras = sec.get("paragraphs") or []
        if isinstance(raw_paras, str):
            raw_paras = [raw_paras]
        paragraphs = []
        for p in raw_paras:
            clean_p = sanitize_text(p, max_len=4000, field_name="paragraph")
            if clean_p:
                clean_p = strip_markdown_delimiters(clean_p)
                paragraphs.append(clean_p)
                total_content_elements += 1

        # Bullet points
        raw_bullets = sec.get("bullet_points") or []
        if isinstance(raw_bullets, str):
            raw_bullets = [raw_bullets]
        bullet_points = []
        for b in raw_bullets:
            clean_b = sanitize_text(b, max_len=500, field_name="bullet_point")
            if clean_b:
                clean_b = strip_markdown_delimiters(clean_b)
                bullet_points.append(clean_b)
                total_content_elements += 1

        # Table
        table_dict = None
        raw_table = sec.get("table")
        if isinstance(raw_table, dict):
            headers = [sanitize_text(h, max_len=300, field_name="table_header") for h in (raw_table.get("headers") or [])]
            raw_rows = raw_table.get("rows") or []
            # Cap table to 30 rows x 12 cols
            headers = headers[:12]
            clean_rows = []
            for r in raw_rows[:30]:
                if isinstance(r, list):
                    clean_row = [sanitize_text(c, max_len=300, field_name="table_cell") for c in r[:12]]
                    clean_rows.append(clean_row)
                    total_content_elements += 1
            if headers or clean_rows:
                caption = sanitize_text(raw_table.get("caption") or "Data Table", max_len=200, field_name="table_caption")
                table_dict = {"caption": caption, "headers": headers, "rows": clean_rows}

        if paragraphs or bullet_points or table_dict:
            normalized_sections.append({
                "section_number": idx + 1,
                "title": sec_title,
                "heading_level": heading_level,
                "paragraphs": paragraphs,
                "bullet_points": bullet_points,
                "table": table_dict,
                "applied_rules": sec.get("applied_rules") or [],
            })

    if not normalized_sections or total_content_elements == 0:
        raise LLMInvalidResponse("Document plan has no valid text content or sections.")

    return {
        "title": title,
        "document_type": "docx",
        "target_audience": target_audience,
        "sections": normalized_sections,
        "conclusion": conclusion,
    }


def _normalize_presentation_plan(raw: dict[str, Any]) -> dict[str, Any]:
    title = sanitize_text(raw.get("presentation_title") or raw.get("title") or "Presentation", max_len=200, field_name="presentation_title")
    audience = sanitize_text(raw.get("audience") or "General Audience", max_len=200, field_name="audience")

    raw_slides = raw.get("slides")
    if not isinstance(raw_slides, list) or len(raw_slides) == 0:
        raise LLMInvalidResponse("Presentation plan contains no slides.")

    normalized_slides = []
    total_content_elements = 0

    for idx, slide in enumerate(raw_slides):
        if not isinstance(slide, dict):
            continue

        slide_title = sanitize_text(slide.get("title") or f"Slide {idx + 1}", max_len=200, field_name="slide_title")
        layout_name = sanitize_text(slide.get("layout_name") or "Title and Content", max_len=100, field_name="layout_name")
        layout_role = sanitize_text(slide.get("layout_role") or "content", max_len=50, field_name="layout_role")

        # Body paragraphs
        raw_body = slide.get("body_paragraphs") or []
        if isinstance(raw_body, str):
            raw_body = [raw_body]
        body_paragraphs = []
        for p in raw_body:
            clean_p = sanitize_text(p, max_len=2000, field_name="slide_body")
            if clean_p:
                clean_p = strip_markdown_delimiters(clean_p)
                body_paragraphs.append(clean_p)
                total_content_elements += 1

        # Bullet points
        raw_bullets = slide.get("bullet_points") or []
        if isinstance(raw_bullets, str):
            raw_bullets = [raw_bullets]
        bullet_points = []
        for b in raw_bullets:
            clean_b = sanitize_text(b, max_len=500, field_name="slide_bullet")
            if clean_b:
                clean_b = strip_markdown_delimiters(clean_b)
                bullet_points.append(clean_b)
                total_content_elements += 1

        normalized_slides.append({
            "slide_number": idx + 1,
            "title": slide_title,
            "layout_name": layout_name,
            "layout_role": layout_role,
            "body_paragraphs": body_paragraphs,
            "bullet_points": bullet_points,
            "speaker_notes": sanitize_text(slide.get("speaker_notes") or "", max_len=2000, field_name="speaker_notes"),
        })

    if not normalized_slides or total_content_elements == 0:
        raise LLMInvalidResponse("Presentation plan has no valid slide content.")

    return {
        "presentation_title": title,
        "audience": audience,
        "slides": normalized_slides,
    }
