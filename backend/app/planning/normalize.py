"""Plan normalization, sanitization, and rich-text span parsing (LLM-04, LLM-05, LLM-06)."""

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

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


def deduplicate_repetitive_text(text: str) -> str:
    """
    Detects and collapses consecutive identical lines, phrases, or clauses caused by LLM repetition loops.
    """
    if not text or len(text) < 15:
        return text

    # 1. Deduplicate consecutive repetitive lines
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    last_line = None
    for line in lines:
        trimmed = line.strip()
        if trimmed and trimmed == last_line:
            continue
        last_line = trimmed if trimmed else None
        cleaned_lines.append(line)
    res = "\n".join(cleaned_lines)

    # 2. Collapse repeated sentences or clauses of 8+ chars repeating 2+ times
    res = re.sub(r"(.{8,}?)(?:\s*\1){2,}", r"\1", res)
    return res


DISALLOWED_PARAGRAPH_SNIPPETS = {
    "bullet_points",
    "bullet_point",
    "bullets",
    "paragraphs",
    "table_data",
    "[seminar topic]",
    "[title]",
    ": lowercase",
    ": uppercase",
    ": uppercase tent",
    ": uppercase act paragraph",
    "none",
    "null",
}


def is_stray_placeholder_or_schema_key(text: str) -> bool:
    t_clean = text.strip().lower()
    if t_clean in DISALLOWED_PARAGRAPH_SNIPPETS:
        return True
    if re.match(r"^:\s*(?:lower|upper)case", t_clean):
        return True
    if re.match(r"^\[(?:seminar topic|title|topic)\]$", t_clean):
        return True
    return False


def extract_markdown_table(text: str | list[str]) -> tuple[dict[str, Any] | None, Any]:
    """
    Parses pipe-delimited markdown tables from text or a list of paragraph strings,
    returning (table_dict, remaining_text_or_paragraphs).
    """
    if isinstance(text, list):
        table_dict = None
        remaining_paras = []
        for p in text:
            if not isinstance(p, str):
                remaining_paras.append(p)
                continue
            if "|" in p and table_dict is None:
                tbl, remaining = extract_markdown_table(p)
                if tbl is not None:
                    table_dict = tbl
                    if remaining.strip():
                        remaining_paras.append(remaining.strip())
                    continue
            remaining_paras.append(p)
        return table_dict, remaining_paras

    if not isinstance(text, str) or "|" not in text:
        return None, text

    lines = [l for l in text.split("\n")]
    table_lines: list[tuple[int, str]] = []
    caption = "Data Table"

    for idx, l in enumerate(lines):
        trimmed = l.strip()
        if trimmed.startswith("|") and trimmed.endswith("|") and trimmed.count("|") >= 2:
            table_lines.append((idx, trimmed))
        elif re.match(r"^Table\s*\d*:\s*(.+)", trimmed, re.I):
            caption = trimmed

    # Multi-line table
    if len(table_lines) >= 2:
        headers: list[str] = []
        rows: list[list[str]] = []
        for _, tl in table_lines:
            cells = [c.strip() for c in tl.strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not headers:
                headers = cells[:12]
            else:
                rows.append(cells[:12])
        if headers or rows:
            table_line_indices = {idx for idx, _ in table_lines}
            remaining = [
                l
                for i, l in enumerate(lines)
                if i not in table_line_indices
                and not (re.match(r"^Table\s*\d*:\s*", l.strip(), re.I) and l.strip() == caption)
            ]
            return {
                "caption": caption,
                "headers": headers,
                "rows": rows,
            }, "\n".join(remaining).strip()

    # Inline single-line pipe table
    if text.count("|") >= 6:
        m = re.match(r"^(Table\s*\d*:[^|]+)\|(.*)", text, re.IGNORECASE)
        if m:
            caption = m.group(1).strip()
            rest = "|" + m.group(2)
        else:
            caption = "Data Table"
            rest = text

        parts = re.split(r"\|\s*-+[\s\-\|]+", rest)
        if len(parts) >= 2:
            header_part = parts[0].strip().strip("|")
            headers = [c.strip() for c in header_part.split("|") if c.strip()][:12]
            body_part = parts[1].strip().strip("|")
            body_cells = [c.strip() for c in body_part.split("|") if c.strip()]
            col_count = len(headers)
            if col_count > 0:
                rows = []
                curr_row: list[str] = []
                for cell in body_cells:
                    if re.match(r"^\d+$", cell) and len(curr_row) == col_count:
                        rows.append(curr_row)
                        curr_row = []
                        continue
                    curr_row.append(cell)
                    if len(curr_row) == col_count:
                        rows.append(curr_row)
                        curr_row = []
                if curr_row:
                    rows.append(curr_row)
                if headers or rows:
                    return {"caption": caption, "headers": headers, "rows": rows}, ""

    return None, text


def sanitize_text(text: Any, max_len: int | None = None, field_name: str = "field") -> str:
    """
    Sanitizes arbitrary scalar values into clean, XML-legal, normalized unicode strings.
    Strips XML illegal control characters, collapses excessive whitespace,
    removes leading markdown heading/bullet syntax, and enforces length caps.
    """
    if text is None:
        return ""
    if isinstance(text, float) and text.is_integer():
        # Avoid trailing .0 noise for whole numbers (e.g. 2020.0 -> "2020")
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

    # 5. Deduplicate repetitive loops
    text_str = deduplicate_repetitive_text(text_str)

    # 6. Cap length if requested
    if max_len is not None and len(text_str) > max_len:
        logger.warning(
            "Field '%s' length %d exceeded max %d; truncating", field_name, len(text_str), max_len
        )
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
    title = sanitize_text(
        raw.get("title") or raw.get("document_title") or "Document Report",
        max_len=200,
        field_name="title",
    )
    target_audience = sanitize_text(
        raw.get("target_audience") or "General Audience", max_len=200, field_name="target_audience"
    )
    conclusion = sanitize_text(raw.get("conclusion") or "", max_len=4000, field_name="conclusion")

    raw_sections = raw.get("sections")
    if not isinstance(raw_sections, list) or len(raw_sections) == 0:
        raise LLMInvalidResponse("Document plan contains no sections.")

    normalized_sections = []
    total_content_elements = 0

    for idx, sec in enumerate(raw_sections):
        if not isinstance(sec, dict):
            continue

        sec_title = sanitize_text(
            sec.get("title") or f"Section {idx + 1}", max_len=200, field_name="section_title"
        )
        heading_level = sec.get("heading_level", 1)
        try:
            heading_level = int(heading_level)
        except (ValueError, TypeError):
            heading_level = 1

        # Paragraphs
        raw_paras = sec.get("paragraphs")
        if raw_paras is None:
            raw_paras = []
        elif not isinstance(raw_paras, (list, tuple)):
            raw_paras = [raw_paras]

        # Table (accept both 'table' and 'table_data')
        table_dict = None
        raw_table = sec.get("table") if sec.get("table") is not None else sec.get("table_data")
        if isinstance(raw_table, dict):
            raw_headers = raw_table.get("headers")
            if raw_headers is None:
                raw_headers = []
            elif not isinstance(raw_headers, (list, tuple)):
                raw_headers = [raw_headers]
            headers = [
                sanitize_text(h, max_len=300, field_name="table_header") for h in raw_headers
            ]
            raw_rows = raw_table.get("rows")
            if raw_rows is None:
                raw_rows = []
            elif not isinstance(raw_rows, (list, tuple)):
                raw_rows = [raw_rows]
            # Cap table to 30 rows x 12 cols
            headers = headers[:12]
            clean_rows = []
            for r in list(raw_rows)[:30]:
                if isinstance(r, (list, tuple)):
                    clean_row = [
                        sanitize_text(c, max_len=300, field_name="table_cell") for c in r[:12]
                    ]
                    clean_rows.append(clean_row)
                    total_content_elements += 1
                else:
                    clean_rows.append([sanitize_text(r, max_len=300, field_name="table_cell")])
                    total_content_elements += 1
            if headers or clean_rows:
                caption = sanitize_text(
                    raw_table.get("caption") or raw_table.get("title") or "Data Table",
                    max_len=200,
                    field_name="table_caption",
                )
                table_dict = {"caption": caption, "headers": headers, "rows": clean_rows}

        paragraphs = []
        for p in raw_paras:
            clean_p = sanitize_text(p, max_len=4000, field_name="paragraph")
            if not clean_p or is_stray_placeholder_or_schema_key(clean_p):
                continue
            clean_p = strip_markdown_delimiters(clean_p)
            if table_dict is None:
                extracted_tbl, remaining_text = extract_markdown_table(clean_p)
                if extracted_tbl is not None:
                    table_dict = extracted_tbl
                    clean_p = remaining_text
            if clean_p and not is_stray_placeholder_or_schema_key(clean_p):
                paragraphs.append(clean_p)
                total_content_elements += 1

        # Bullet points (accept both 'bullet_points' and 'bullets')
        raw_bullets = (
            sec.get("bullet_points") if sec.get("bullet_points") is not None else sec.get("bullets")
        )
        if raw_bullets is None:
            raw_bullets = []
        elif not isinstance(raw_bullets, (list, tuple)):
            raw_bullets = [raw_bullets]
        bullet_points = []
        for b in raw_bullets:
            clean_b = sanitize_text(b, max_len=500, field_name="bullet_point")
            if clean_b and not is_stray_placeholder_or_schema_key(clean_b):
                clean_b = strip_markdown_delimiters(clean_b)
                bullet_points.append(clean_b)
                total_content_elements += 1

        if paragraphs or bullet_points or table_dict:
            normalized_sections.append(
                {
                    "section_number": idx + 1,
                    "title": sec_title,
                    "heading_level": heading_level,
                    "heading_style": sec.get("heading_style"),
                    "action": sec.get("action"),
                    "target_heading": sec.get("target_heading"),
                    "image_query": sec.get("image_query"),
                    "paragraphs": paragraphs,
                    "bullet_points": bullet_points,
                    "table": table_dict,
                    "table_data": table_dict,
                    "applied_rules": sec.get("applied_rules") or [],
                }
            )

    if not normalized_sections or total_content_elements == 0:
        raise LLMInvalidResponse("Document plan has no valid text content or sections.")

    return {
        "title": title,
        "document_type": "docx",
        "target_audience": target_audience,
        "sections": normalized_sections,
        "conclusion": conclusion,
        "applied_rules": raw.get("applied_rules") or [],
    }


def _normalize_presentation_plan(raw: dict[str, Any]) -> dict[str, Any]:
    title = sanitize_text(
        raw.get("presentation_title") or raw.get("title") or "Presentation",
        max_len=200,
        field_name="presentation_title",
    )
    audience = sanitize_text(
        raw.get("audience") or "General Audience", max_len=200, field_name="audience"
    )

    raw_slides = raw.get("slides")
    if not isinstance(raw_slides, list) or len(raw_slides) == 0:
        raise LLMInvalidResponse("Presentation plan contains no slides.")

    normalized_slides = []
    total_content_elements = 0

    for idx, slide in enumerate(raw_slides):
        if not isinstance(slide, dict):
            continue

        slide_title = sanitize_text(
            slide.get("title") or f"Slide {idx + 1}", max_len=200, field_name="slide_title"
        )
        subtitle = (
            sanitize_text(slide.get("subtitle"), max_len=300, field_name="subtitle")
            if slide.get("subtitle")
            else None
        )
        layout_name = sanitize_text(
            slide.get("layout_name") or "Title and Content", max_len=100, field_name="layout_name"
        )
        layout_role = sanitize_text(
            slide.get("layout_role") or "content", max_len=50, field_name="layout_role"
        )

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

        # Bullet points (accept both 'bullet_points' and 'bullets')
        raw_bullets = (
            slide.get("bullet_points")
            if slide.get("bullet_points") is not None
            else (slide.get("bullets") or [])
        )
        if isinstance(raw_bullets, str):
            raw_bullets = [raw_bullets]
        bullet_points = []
        for b in raw_bullets:
            clean_b = sanitize_text(b, max_len=500, field_name="slide_bullet")
            if clean_b:
                clean_b = strip_markdown_delimiters(clean_b)
                bullet_points.append(clean_b)
                total_content_elements += 1

        raw_table = (
            slide.get("table_data") if slide.get("table_data") is not None else slide.get("table")
        )
        if isinstance(raw_table, dict) and (raw_table.get("headers") or raw_table.get("rows")):
            total_content_elements += 1

        if subtitle:
            total_content_elements += 1

        normalized_slides.append(
            {
                "slide_number": idx + 1,
                "title": slide_title,
                "subtitle": subtitle,
                "layout_name": layout_name,
                "layout_role": layout_role,
                "body_paragraphs": body_paragraphs,
                "bullet_points": bullet_points,
                "table_data": raw_table if isinstance(raw_table, dict) else None,
                "image_query": slide.get("image_query"),
                "columns": slide.get("columns") if isinstance(slide.get("columns"), list) else None,
                "speaker_notes": sanitize_text(
                    slide.get("speaker_notes") or "", max_len=2000, field_name="speaker_notes"
                ),
            }
        )

    if not normalized_slides or total_content_elements == 0:
        raise LLMInvalidResponse("Presentation plan has no valid slide content.")

    return {
        "presentation_title": title,
        "audience": audience,
        "slides": normalized_slides,
    }
