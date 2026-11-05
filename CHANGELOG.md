# Changelog

## Unreleased

- Added DOCX/PDF-reference length selection by approximate page count or Low, Medium, and High detail; presentations retain slide-count selection.
- Reworked document planning into outline, bounded section writing, quality review, and one targeted repair per failing section.
- Added opt-in Tavily research with citations tied to returned source metadata and explicit failures when requested research cannot complete.
- Added bounded upload handling, stronger file validation, owner-scoped artifacts, and truthful validation/reporting paths.
- Added frontend unit, accessibility, and browser workflow coverage, plus a standalone asset preparation step required by Next.js output mode.

## Compatibility notes

- The legacy `target_pages_or_slides` request field remains accepted. New clients should send `target_pages`, `detail_level`, or `target_slides` according to the document type.
- Page targets are approximate content targets; the rendered page count is not guaranteed.
- Research remains off by default and requires `TAVILY_API_KEY` on the backend.
