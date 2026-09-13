# Project: Exact Template Inheritance System Overhaul

## Architecture
- **Backend Architecture**: FastAPI application (`backend/app/main.py`) with native asynchronous AI client (`backend/app/ai/gemma_client.py`), tailored token caps in `prompt_enhancer.py` and `planner.py`, and offline-resilient visual asset generation in `image_service.py`.
- **Template Inheritance Engine**:
  - `DocxEngine` (`backend/app/engines/docx_engine.py`): OpenXML AST manipulator preserving page margins (`w:sectPr`), cloning `w:tbl` XML tables, and safely mapping headings.
  - `PptxEngine` (`backend/app/engines/pptx_engine.py`): PPTX slide generator preserving slide masters, layouts, themes, and dynamic shape/table positioning.
  - `PdfAnalyzer` & `PdfExtractor` (`backend/app/analyzer/pdf_analyzer.py`, `backend/app/engines/pdf_extractor.py`): Visual reference mode extracting geometry and fonts.
- **Invariant & Style Lock Engine**:
  - `StyleLock` (`backend/app/engines/style_lock.py`): `assert_content_only()` guards against formatting overrides.
  - `DiffValidator` (`backend/app/validation/diff_validator.py`) & `StyleHasher`: SHA-256 structural hash comparison (`Original == Output`).
- **Frontend Architecture**:
  - Next.js 16.2.12 App Router (`src/app/`), React 19, Tailwind CSS v4 with custom `@variant dark`.
  - Components: `Header.tsx` (live `/api/health` polling), `FileUpload.tsx` (responsive wrapping), `GenerationPreview.tsx` (asymptotic progress algorithm), `DiffViewer.tsx` (PDF synthesis contextualization).

## Feature Inventory
| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|--------|
| 1 | Async Ollama Client Migration | Native `ollama.AsyncClient` with `timeout=80.0`, direct `await client.chat(...)`, shielded teardown `await asyncio.shield(client.close())` on cancel/timeout | M1 | Survey | VERIFIED |
| 2 | Tailored Token Caps | Explicit generation token caps: 350 for prompt enhancement, 1500 for DOCX planning, 1000 for PPTX planning | M1 | Survey | VERIFIED |
| 3 | Image Service Timeout & Offline Resilience | Unsplash network timeout <= 2.0s, `OFFLINE_MODE` flag in Settings/env, immediate offline SVG & matching raster JPG generation | M1 | Survey | VERIFIED |
| 4 | Dedicated Backend Resilience Tests | Unit test suite `backend/tests/test_r1_r2_resilience.py` verifying R1 and R2 socket teardown, token caps, and offline behavior | M1 | Survey | VERIFIED |
| 5 | Tailwind v4 Class-Based Dark Mode | `@variant dark (&:where(.dark, .dark *));` in `src/app/globals.css` immediately after `@import "tailwindcss";` | M2 | Survey | VERIFIED |
| 6 | Responsive Format Badge Wrapping | `flex-wrap` and `justify-center` in `src/app/components/FileUpload.tsx` for viewports < 380px | M2 | Survey | VERIFIED |
| 7 | Asymptotic Generation Progress Algorithm | Smooth continuous progress curve advancing to ~30% in 1.5s, asymptotically approaching ~90%, and snapping to 100% on response completion; clean ESLint state | M2 | Survey | VERIFIED |
| 8 | Dynamic Model Display in Header | Live query to `/api/health` in `src/app/components/Header.tsx` with unmount cleanup | M2 | Survey | VERIFIED |
| 9 | PDF Synthesis Contextualization in DiffViewer | Contextual download button ("Download Generated Document (DOCX)") and explanatory layout synthesis badge for PDF inputs | M2 | Survey | VERIFIED |
| 10 | Pytest 85-Test Invariant Suite | All 85 backend tests pass with 0 failures and 0 thread warnings (`python -m pytest backend/tests -v`) | M3 | Survey | VERIFIED |
| 11 | Empirical Adversarial Invariant Suite | All 5 empirical challenges in `scripts/verify_empirical_adversarial.py` pass with 0 failures | M3 | Survey | VERIFIED |
| 12 | TypeScript Compilation Cleanliness | `npx tsc --noEmit` exits with code 0 and 0 errors | M3 | Survey | VERIFIED |
| 13 | ESLint Zero-Warning Cleanliness | `npm run lint` exits with 0 errors and 0 warnings | M3 | Survey | VERIFIED |
| 14 | Next.js 16 Turbopack Production Build | `npm run build` succeeds cleanly with all routes compiled | M3 | Survey | VERIFIED |
| 15 | Forensic Integrity Attestation | Zero cheating, genuine implementations, zero dummy/facade code, complete invariant preservation verified by Auditor (Verdict: CLEAN) | M3 | Survey | VERIFIED |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Performance & Offline Resilience | Implement and verify R1 and R2: `gemma_client.py` hardening (timeout=80.0, shield close), `config.py` (`OFFLINE_MODE`), `image_service.py`, and `backend/tests/test_r1_r2_resilience.py`. Run backend test suites. | none | DONE |
| M2 | Frontend Tailwind v4 & Dynamic UI/UX | Implement and verify R3 and R4: `globals.css`, `FileUpload.tsx`, `GenerationPreview.tsx` (ESLint fix), `Header.tsx` (ESLint cleanup), `DiffViewer.tsx`. Run `npm run lint`, `npx tsc --noEmit`, and `npm run build`. | none | DONE |
| M3 | Comprehensive Quality Gates & Forensic Audit | Run all 5 quality gates (Pytest 85 tests, 5 Empirical Challenges, tsc, lint, build), dispatch Challenger for stress validation, and Forensic Auditor for integrity attestation. | M1, M2 | DONE |

## Code Layout
- `backend/app/main.py`: FastAPI app root, health check router
- `backend/app/config.py`: Application settings (`OFFLINE_MODE`, `MAX_TOKENS`)
- `backend/app/ai/gemma_client.py`: Async Ollama client with `AsyncClient`, 80s timeout, socket teardown
- `backend/app/ai/prompt_enhancer.py`: Neural prompt enhancement with `max_tokens=350`
- `backend/app/ai/planner.py`: Document planner with `max_tokens=1500` (DOCX) and `max_tokens=1000` (PPTX)
- `backend/app/ai/image_service.py`: Visual asset service with 2.0s timeout and SVG/JPG offline fallback
- `backend/app/engines/`: Document mutation engines (`docx_engine.py`, `pptx_engine.py`, `pdf_extractor.py`, `style_lock.py`)
- `backend/app/validation/`: `diff_validator.py`, `regression.py`
- `backend/tests/`: Pytest test suite (`test_r1_r2_resilience.py`, `test_docx_engine.py`, etc.)
- `scripts/verify_empirical_adversarial.py`: 5 empirical adversarial challenges
- `src/app/globals.css`: Tailwind CSS v4 dark mode variant
- `src/app/components/FileUpload.tsx`: Format badge flex-wrap layout
- `src/app/components/GenerationPreview.tsx`: Asymptotic generation progress bar
- `src/app/components/Header.tsx`: Dynamic health model query
- `src/app/components/DiffViewer.tsx`: PDF synthesis download label & badge
