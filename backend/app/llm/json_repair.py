"""Robust JSON parser and repair engine for LLM outputs.

Handles:
- Markdown fences (```json ... ```, unclosed ```)
- Truncated streaming JSON responses (e.g. LLM hitting max_tokens mid-string)
- Trailing commas before closing brackets/braces
- Conversational preamble/postamble surrounding JSON
- Fallback semantic extraction for structured sections and outlines
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..errors import LLMInvalidResponse

logger = logging.getLogger(__name__)


def _clean_markdown_fences(text: str) -> str:
    """Strip markdown code fences and preamble/postamble."""
    text = text.strip()
    if "```" in text:
        # Match standard markdown fence block
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence_match:
            candidate = fence_match.group(1).strip()
            if candidate.startswith(("{", "[")):
                return candidate
        # Unclosed fence or split lines
        lines = text.splitlines()
        cleaned_lines: list[str] = []
        for line in lines:
            if line.strip().startswith("```"):
                continue
            cleaned_lines.append(line)
        text = "\n".join(cleaned_lines).strip()
    return text


def _locate_json_boundary(text: str) -> str:
    """Locate the starting boundary of JSON object or array."""
    start_brace = text.find("{")
    start_bracket = text.find("[")

    if start_brace == -1 and start_bracket == -1:
        return text

    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        start_idx = start_brace
    else:
        start_idx = start_bracket

    return text[start_idx:].strip()


def _balance_truncated_json(text: str) -> str:
    """Repair truncated JSON by closing unclosed strings, arrays, and objects."""
    in_string = False
    escape = False
    stack: list[str] = []
    reconstructed: list[str] = []

    for ch in text:
        if in_string:
            if escape:
                escape = False
                reconstructed.append(ch)
            elif ch == "\\":
                escape = True
                reconstructed.append(ch)
            elif ch == '"':
                in_string = False
                reconstructed.append(ch)
            else:
                reconstructed.append(ch)
        else:
            if ch == '"':
                in_string = True
                reconstructed.append(ch)
            elif ch == "{":
                stack.append("}")
                reconstructed.append(ch)
            elif ch == "[":
                stack.append("]")
                reconstructed.append(ch)
            elif ch in ("}", "]"):
                if stack and stack[-1] == ch:
                    stack.pop()
                reconstructed.append(ch)
            else:
                reconstructed.append(ch)

    # If stream cut off in the middle of a string:
    if in_string:
        if escape and reconstructed and reconstructed[-1] == "\\":
            reconstructed.pop()
        reconstructed.append('"')

    res = "".join(reconstructed).strip()

    # Remove dangling trailing comma at the end of the content before closing structures
    res = re.sub(r",\s*$", "", res)

    # Close any open arrays / objects in reverse order
    for closing_token in reversed(stack):
        res = re.sub(r",\s*$", "", res.strip())
        res += closing_token

    # Remove any trailing commas immediately preceding closing braces/brackets
    res = re.sub(r",\s*([}\]])", r"\1", res)
    return res


def _fallback_extract_section(text: str) -> dict[str, Any] | None:
    """Extract section data if JSON balancing is partially corrupted."""
    title_match = re.search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"?', text)
    title = title_match.group(1).strip() if title_match else "Section Content"

    paragraphs: list[str] = []
    para_idx = text.find('"paragraphs"')
    if para_idx != -1:
        para_sub = text[para_idx:]
        # Find all quoted strings within paragraphs
        quoted_strings = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', para_sub)
        for s in quoted_strings:
            s_clean = s.strip()
            if s_clean and s_clean != "paragraphs" and len(s_clean) > 5:
                paragraphs.append(s_clean)

        # If no complete quoted string found, check for open quote
        if not paragraphs:
            unclosed_match = re.search(
                r'"paragraphs"\s*:\s*\[\s*"([^"]*)',
                para_sub,
            )
            if unclosed_match and len(unclosed_match.group(1).strip()) > 5:
                paragraphs.append(unclosed_match.group(1).strip())

    if paragraphs or title_match:
        return {
            "title": title,
            "paragraphs": paragraphs or [title],
        }

    return None


def repair_and_parse_json(text: str, *, source_name: str = "LLM") -> dict[str, Any] | list[Any]:
    """Parse JSON with multi-layered auto-repair for truncated or malformed LLM outputs.

    Raises LLMInvalidResponse if no valid JSON or structured data could be extracted.
    """
    if not text or not text.strip():
        raise LLMInvalidResponse(f"{source_name} returned an empty response.")

    raw_text = text.strip()

    # 1. Direct parse attempt
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # 2. Markdown fence removal & leading character trimming
    cleaned = _clean_markdown_fences(raw_text)
    cleaned = _locate_json_boundary(cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # 3. Clean trailing commas
    no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        parsed = json.loads(no_trailing_commas)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # 4. Repair truncated streams by closing strings, arrays, objects
    balanced = _balance_truncated_json(cleaned)
    try:
        parsed = json.loads(balanced)
        if isinstance(parsed, (dict, list)):
            logger.info("Successfully repaired truncated %s JSON response", source_name)
            return parsed
    except Exception as exc:
        logger.debug("Balanced JSON parse failed for %s: %s", source_name, exc)

    # 5. Semantic fallback extraction for section generation
    section_fallback = _fallback_extract_section(raw_text)
    if section_fallback:
        logger.warning(
            "Recovered structured section from partially malformed %s response", source_name
        )
        return section_fallback

    # 6. Raise typed LLMInvalidResponse if all recovery paths failed
    preview = raw_text[:200]
    raise LLMInvalidResponse(f"{source_name} returned non-JSON response: {preview}")
