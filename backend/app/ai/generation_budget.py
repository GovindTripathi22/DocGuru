"""Deterministic page and detail targets for long-form document planning."""

import math
from dataclasses import dataclass
from typing import Literal

DetailLevel = Literal["low", "medium", "high"]
DETAIL_PAGE_EQUIVALENTS: dict[str, int] = {"low": 2, "medium": 5, "high": 10}
DETAIL_WORDS_PER_PAGE: dict[str, int] = {"low": 350, "medium": 450, "high": 550}
WORDS_PER_CUSTOM_PAGE = 450


@dataclass(frozen=True)
class DocumentBudget:
    target_pages: int
    target_words: int
    section_count: int
    words_per_section: int
    detail_level: DetailLevel | Literal["custom"]


def resolve_document_budget(
    *, target_pages: int | None, detail_level: DetailLevel | None, target_sections: int | None = None
) -> DocumentBudget:
    """Map user length choices to bounded content budgets, not a page guarantee."""
    if target_pages is not None and detail_level is not None:
        raise ValueError("Choose either target_pages or detail_level, not both.")
    if detail_level is not None and detail_level not in DETAIL_PAGE_EQUIVALENTS:
        raise ValueError("Document detail_level must be low, medium, or high.")
    if target_sections is not None and not 1 <= target_sections <= 50:
        raise ValueError("Document target_sections must be between 1 and 50.")
    level: DetailLevel = detail_level or "medium"
    pages = target_pages if target_pages is not None else DETAIL_PAGE_EQUIVALENTS[level]
    if pages < 1 or pages > 50:
        raise ValueError("Document page targets must be between 1 and 50.")

    words_per_page = WORDS_PER_CUSTOM_PAGE if target_pages is not None else DETAIL_WORDS_PER_PAGE[level]
    target_words = pages * words_per_page
    sections = target_sections or max(2, min(50, math.ceil(pages * 1.4)))
    sections = max(1, min(sections, 50))
    return DocumentBudget(
        target_pages=pages,
        target_words=target_words,
        section_count=sections,
        words_per_section=max(120, math.ceil(target_words / sections)),
        detail_level="custom" if target_pages is not None else level,
    )
