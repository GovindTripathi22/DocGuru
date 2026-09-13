# Original User Request

## Initial Request â€” 2026-08-23T10:52:28Z

You are the Project Orchestrator (teamwork_preview_orchestrator).

Working directory: C:/Users/USER/.gemini/antigravity/worktrees/exact_template_inheritance_system/.agents/teamwork_preview_orchestrator_1
Workspace root: C:/Users/USER/.gemini/antigravity/worktrees/exact_template_inheritance_system
Original request: C:/Users/USER/.gemini/antigravity/worktrees/exact_template_inheritance_system/.agents/ORIGINAL_REQUEST.md

Execute full-stack autonomous multi-agent verification, performance optimization, and comprehensive stress testing of the Exact Template Inheritance System across all DOCX, PPTX, and PDF rendering workflows.

Requirements:
- R1: Exact Template Preservation & Invariant Enforcement (preserve 100% formatting, borders, margins, fonts, master slide structures; zero theme drift).
- R2: End-to-End Pipeline & Feature Verification (Neural Prompt Enhancer Studio, Visual Asset Director, Live Pipeline Execution Console, Dynamic Artifact Downloads).
- R3: Autonomous Multi-Agent Stress Testing & Edge-Case Resilience (minimal templates without heading styles, 16:9 vs 4:3 slide dimensions, paragraph auto-fitting, multi-row table cloning, rapid consecutive API calls).

Acceptance Criteria:
1. Pytest test suite (`python -m pytest backend/tests -v`) executes with 100% pass rate.
2. Next.js 16 production build (`npm run build`) finishes with 0 TypeScript and 0 lint errors.
3. All 6 end-to-end integration workflows (Health, Prompt Enhance, DOCX Generation, DOCX Download, PPTX Generation, PPTX Download) complete successfully.
4. Structural hash diff comparison (`Original == Output`) confirms zero unintended style regressions.

Maintain your BRIEFING.md, plan.md, and progress.md in your working directory. Coordinate your swarm and report completion when all work and verifications are complete.


## 2026-09-13T18:31:23Z

Execute a comprehensive performance, reliability, and UI/UX overhaul of the Exact Template Inheritance System — a full-stack production application (FastAPI + Next.js 16 + Ollama) that generates AI-powered documents (DOCX, PPTX) while preserving exact template formatting via OpenXML DOM mutation and SHA-256 style hash validation. This is a production deployment targeting real users.

Working directory: d:/exact_template_inheritance_system
Integrity mode: development

## Requirements

### R1. Async Ollama Client Migration (Backend Performance)
Replace the synchronous ollama.Client.chat() wrapped in syncio.to_thread() in ackend/app/ai/gemma_client.py with native ollama.AsyncClient. This eliminates thread pool starvation where orphaned OS threads block Python's ThreadPoolExecutor, starving downstream file I/O (Starlette FileResponse) and causing cascading stalls under concurrent requests. The timeout should be ~80 seconds, and cancelled/timed-out requests must cleanly drop the socket.

### R2. Tailored Token Caps & Offline Resilience (Backend Speed)
- Cap max_tokens per generation task type: 350 for prompt enhancement (ackend/app/ai/prompt_enhancer.py), 1500 for DOCX planning, 1000 for PPTX planning (ackend/app/ai/planner.py). The existing default of 8192 causes 90–150 second generation times on consumer GPUs.
- Reduce Unsplash image service timeout from 10s to 2s in ackend/app/ai/image_service.py and add an OFFLINE_MODE environment variable flag (default: false). When true or when network fails, immediately use an offline SVG geometric placeholder without delay.

### R3. Tailwind CSS v4 Dark Mode & Responsive Layout Fixes (Frontend Design)
- Add @variant dark (&:where(.dark, .dark *)); to src/app/globals.css so class-based dark mode (<html className="dark">) works regardless of OS theme preference. Currently, Tailwind v4 defaults dark: to @media (prefers-color-scheme: dark), causing white card flashes against the dark #0a0a0c background when the OS is in light mode.
- Add lex-wrap and justify-center to the file format badge container in src/app/components/FileUpload.tsx to prevent horizontal overflow on mobile viewports (<380px).

### R4. Dynamic UI Feedback & Accurate Status Display (Frontend UX)
- Replace the hardcoded 12-second fake progress bar in src/app/components/GenerationPreview.tsx with an asymptotic progress algorithm: rapidly advance to ~30% during template analysis, asymptotically approach ~90% during LLM generation, and snap to 100% upon API response completion. Remove the fixed 3-second setInterval advancement.
- Replace the hardcoded "Gemma 4 (RTX 3050 CUDA)" string in src/app/components/Header.tsx with a live query to GET /api/health that displays the actual running model name dynamically.
- Fix the PDF download label in src/app/components/DiffViewer.tsx: when the uploaded template was a PDF, show "Download Generated Document (DOCX)" with an explanatory badge noting the PDF layout was synthesized into an editable Word document.

### R5. Zero Regressions (Invariant Enforcement)
All changes must preserve the existing 74-test suite pass rate, TypeScript type safety (0 errors), ESLint cleanliness (0 warnings), Next.js 16 Turbopack production build success, and SHA-256 style hash validation. No OpenXML style properties, margins (1.0" locks), font tables, or slide master geometries may be altered. The DiffValidator hash comparison must continue to pass.

## Acceptance Criteria

### Backend Performance
- [ ] ackend/app/ai/gemma_client.py uses ollama.AsyncClient with direct wait client.chat(...) — no syncio.to_thread wrapping for Ollama calls
- [ ] No RuntimeWarning: The executor did not finish joining its threads emitted during test execution
- [ ] Prompt enhancement calls use max_tokens=350; DOCX planning uses max_tokens=1500; PPTX planning uses max_tokens=1000
- [ ] Image service network timeout is ≤ 2.0 seconds with graceful offline/SVG fallback

### Frontend Design & UX
- [ ] src/app/globals.css contains @variant dark (&:where(.dark, .dark *)); immediately after @import "tailwindcss";
- [ ] Header component displays live model name fetched from /api/health instead of a hardcoded string
- [ ] Generation progress bar uses asymptotic advancement algorithm (not fixed 3-second intervals)
- [ ] File format badges in FileUpload wrap cleanly on viewports < 380px wide (flex-wrap applied)
- [ ] PDF uploads show contextual download label ("Download Generated Document (DOCX)") with an explanatory badge

### Quality Gates (all must pass with 0 failures)
- [ ] python -m pytest backend/tests -v — 74/74 tests pass
- [ ] python scripts/verify_empirical_adversarial.py — all 5 empirical challenges pass
- [ ] 
px tsc --noEmit — 0 TypeScript errors
- [ ] 
pm run lint — 0 ESLint errors, 0 warnings
- [ ] 
pm run build — Next.js 16 Turbopack production build succeeds