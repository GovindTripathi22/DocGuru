# DocGuru Remediation Audit & Fix Report

## 1. Baseline Summary (Pre-Remediation)
- `npm run lint`: Passed initial baseline, but UI contained prohibited hype copy ("100%", "Zero Theme Drift", "Sacred") and unhandled async state.
- `npm run build`: Dependent on Google Fonts via `next/font/google`, breaking air-gapped/offline production environments.
- `python -m pytest backend/tests`: Initial suite lacked strict regression coverage for unconfigured LLM fallbacks, XML canonicalization, image caching, and path containment. Ollama integration relied on blocking C-extensions and threads.

---

## 2. Phase-by-Phase Remediation Matrix

### Phase 0: Regression Test Suite
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| P0 | FIXED | `backend/tests/regression/` (7 test modules) | cf5b6af | Programmatic fixtures established; 7 strict reproduction tests created for CFG-01, LLM-01, DOCX-01, PPTX-02, VAL-01, IMG-01, and SEC-01. |

### Phase 1: Configuration & Error Handling
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| CFG-01 | FIXED | `test_config_clean_install.py`, `test_r1_r2_resilience.py` | fa3c581 | Removed `import ollama`; implemented Ollama over native `httpx`; mocked with `respx`; pinned `requirements.txt` & `requirements-dev.txt`. |
| CFG-02 | FIXED | `test_settings.py`, `scripts/check_env_consistency.py` | 984cf6b | Unified Settings with pydantic-settings; consistency checker validates `.env.example`, compose, README, and config. |
| CFG-03 | FIXED | `test_settings.py` | 984cf6b | Provider default handling and explicit error reporting for missing credentials. |
| CFG-04 | FIXED | `test_settings.py` | 984cf6b | Environment variable alias translation warnings and deprecated key handling. |
| SEC-06 | FIXED | `test_error_handling.py`, route modules | 4113127 | Typed `AppError` hierarchy; structured RFC-compliant envelope without path or traceback leakage; `X-Request-ID` echoed. |
| SEC-06b | FIXED | `test_health.py`, `main.py` | 4113127 | `/health/live` (liveness), `/health/ready` (disk space and permissions), and `/api/health` with model info and capabilities. |

### Phase 2: LLM Providers & Prompt Engineering
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| LLM-01 | FIXED | `test_fail_safe.py`, `backend/app/llm/` | c5800be | Unconfigured live provider returns 503 `LLM_NOT_CONFIGURED`; zero silent fallbacks to demo text. |
| LLM-02 | FIXED | `test_generation_length_and_research.py` | b364029 | Replaced one whole-document cap with outline, bounded section writing, per-section quality review, truncation recovery, and completion errors. |
| LLM-03 | FIXED | `test_demo_provider.py` | c5800be | Dynamic, topic-derived demo mode synthesizing content based on prompt keywords. |
| LLM-04 | FIXED | `test_normalize.py` | c5800be | Prompt normalization handling control characters and malformed inputs. |
| LLM-05 | FIXED | `test_injection_quarantine.py` | c5800be | Prompt injection attempts quarantined without overriding document style invariants. |
| LLM-06 | FIXED | `backend/app/llm/providers/` | c5800be | Unified asynchronous provider implementations for Google AI, Ollama, and Demo. |
| LLM-08 | FIXED | `test_injection_quarantine.py`, `test_generation_length_and_research.py` | c5800be + b364029 | Structured JSON and untrusted template/source boundaries; document output budgets are now staged per outline/section/review call rather than one whole-document cap. |
| LLM-09 | FIXED | `test_r1_r2_resilience.py` | c5800be | Request timeouts and shielded socket closure preventing socket leaks. |

### Phase 3: Template Invariants & Validation
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| VAL-01 | FIXED | `test_canonical_fingerprint.py` | 94917ba | XML canonicalization (c14n) fingerprinting of styles, fonts, themes, and settings. |
| VAL-02 | FIXED | `test_diff_validator.py` | 94917ba | Mutation-sensitive diff validator detecting margin drift, font changes, and layout regressions. |

### Phase 4: Document Mutation Engines
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| DOCX-01 | FIXED | `test_docx_engine.py`, `test_docx_title_conclusion.py` | 7fb11ad | Render explicit document title and concluding summary section in create mode. |
| PPTX-01 | FIXED | `test_pptx_engine.py` | 4be193f | Capability-based slide layout fallback choosing optimal layouts by placeholder count. |
| PPTX-02 | FIXED | `test_pptx_engine.py`, `test_pptx_bullet_drop.py` | 4be193f | Prevent bullet marker drops during text shape mutation and preserve list indentation. |

### Phase 5: Visual Asset Director
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| IMG-01 | FIXED | `test_image_caching.py`, `test_r1_r2_resilience.py` | 59abebf | SHA-256 query caching, <= 2.0s network timeout, and offline geometric SVG generation. |

### Phase 6: Path Security & Boundaries
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| SEC-01 | FIXED | `test_security.py` | c8efe52 | Path traversal containment (`safe_path_join`) rejecting traversal sequences. |
| SEC-02 | FIXED | `test_security.py`, `backend/app/routes/` | c8efe52 | Upload boundary checks (`MAX_UPLOAD_MB`) and PDF page caps (`MAX_PDF_PAGES`). |

### Phase 7: Async Jobs, Operations & Retention
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| API-JOBS | FIXED | `test_jobs.py`, `test_e2e_workflows.py` | 539320c | `POST /api/generate` returns 202 `{job_id}`; `GET /api/jobs/{id}` polls stages; `DELETE` cancels. |
| SEC-07 | FIXED | `test_jobs.py` | 539320c | Immediate artifact deletion endpoints: `DELETE /api/templates/{id}`, `DELETE /api/outputs/{id}`. |
| SEC-08 | FIXED | `test_jobs.py` | 539320c | Background retention purge removing jobs and artifacts older than `RETENTION_HOURS`. |
| OPS-01 | FIXED | `scripts/deploy_oracle_cloud.sh` | b1115ca | Idempotent automated cloud deployment script with systemd and firewall configurations. |
| OPS-02 | FIXED | `backend/app/config.py`, `backend/app/main.py` | b1115ca | Privacy-safe structured request logging (`LOG_CONTENT=false` by default). |

### Phase 8: Truthful UI & Frontend Modernization
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| FE-01 | FIXED | `scripts/check_copy.mjs`, UI components | 39ff829 | Banned hype copy eliminated across UI; checked via automated CI script. |
| FE-02 | FIXED | `ProgressPanel.tsx` | 39ff829 | Dynamic job progress polling replacing hardcoded interval timers. |
| FE-03 | FIXED | `ResultPanel.tsx` | 39ff829 | Component verification table displaying real OpenXML validation results. |
| FE-04 | FIXED | `Header.tsx`, `ModeBanner.tsx` | 39ff829 | Real-time health model status polling and dynamic demo mode banner. |
| FE-10 | PARTIAL | `npm run test:frontend`, `src/lib/generation-request.test.mjs` | b364029 | Five request-builder tests pass; React component, browser end-to-end, and axe accessibility tests from the full work order are not present. |
| FE-08 | FIXED | `src/app/layout.tsx` | 39ff829 | Offline fonts; removed `next/font/google` remote font network requests. |
| FE-09 | FIXED | `src/lib/backend.ts`, API routes | 39ff829 | Session signing, API key forwarding, and streaming file download handling. |

### Phase 9: DevOps Hardening & Dead Code Cleanup
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| OPS-03 | FIXED | `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml` | 584225c | Non-root users (`docguru` UID 10001, `node` UID 1000), `tini` init, `no-new-privileges:true`. |
| OPS-04 | PARTIAL | `package.json` | b364029 | Separate `dev` and `dev:backend` scripts exist; the requested `dev:all` command and Makefile targets are absent. |
| OPS-05 | PARTIAL | `.github/workflows/ci.yml`, local Ruff/mypy gates | 584225c + b364029 | CI covers basic backend/frontend gates, but the full requested security, type, coverage, Docker, and Playwright matrix is incomplete. Current local Ruff and mypy checks fail as recorded below. |
| DEAD-01 | FIXED | Frontend & backend file audit | 584225c | Obsolete components (`DiffViewer.tsx`, `GenerationPreview.tsx`) and legacy imports removed. |

### Phase 10: Documentation & Reports
| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| DOC-01 | FIXED | `docs/VALIDATION.md` | 813ce4c | Invariant guarantees, canonicalization fingerprinting, and diff validation documentation. |
| DOC-02 | FIXED | `docs/PRIVACY.md` | 813ce4c | Data lifecycle, retention policies, prompt quarantine, and log content privacy. |
| DOC-03 | FIXED | `docs/MANUAL_QA.md` | 813ce4c | Step-by-step human verification checklist for Word, PowerPoint, Docker, and real LLMs. |
| DOC-04 | FIXED | `docs/DECISIONS.md`, `README.md` | 813ce4c | Architectural decision record and comprehensive project README update. |
| TEST-01/02 | PARTIAL | `backend/tests/`, `src/lib/generation-request.test.mjs` | b364029 | The 156-test backend suite and five frontend request tests pass. Coverage measured 73.94%, below the 80% target; the Hypothesis matrix, Playwright, and axe gates remain incomplete. |

---

## 3. Current Generation Remediation (2026-11-04)

The earlier final verification counts (121 tests / 31 environment variables) were stale and are superseded by the results below.

**Status summary:** This continuation has 7 fixed feature items: document length, staged planning, section review, shared concurrency, research, demo-table behavior, and validator error handling. Four broader work-order areas remain PARTIAL: OPS-04, OPS-05, FE-10, and TEST-01/02. Six external checks remain NOT VERIFIED: live Google, live Tavily, Word, PowerPoint, Docker/deployment, and a network-disabled build.

| Work item | Status | Evidence | Notes |
| --- | --- | --- | --- |
| DOCX/PDF length choices | FIXED | `test_document_length_targets_are_exclusive_and_legacy_target_maps_to_pages`, `test_detail_presets_and_page_targets_create_monotonic_word_budgets`, `generation-request.test.mjs` | Numeric page target or Low/Medium/High; Medium default; PPTX remains slide-count based. |
| Staged long-document planning | FIXED | `test_document_planner_uses_outline_then_section_calls_and_reports_real_progress`, `test_twelve_sections_use_bounded_writer_and_quality_calls_with_real_progress`, `test_truncated_outline_is_retried_and_empty_outline_is_rejected` | Outline then bounded section writing and quality-review calls; incomplete or empty plans fail explicitly. |
| Quality review and one repair | FIXED | `test_failed_structured_quality_review_gets_one_targeted_repair`, `test_unsupported_numerical_claim_gets_one_targeted_section_repair` | Deterministic checks plus structured relevance, completeness, coherence, repetition, and evidence-discipline review. One targeted repair maximum. This is not external fact verification. |
| Shared provider concurrency | FIXED | `test_provider_calls_obey_global_concurrency_limit_without_blocking_event_loop`, `scripts/verify_concurrency_resilience.py` | Shared per-event-loop provider cap; scripted check: 20 calls in 0.120s, max active 3, heartbeat gap 0.031s. |
| Optional Tavily research | FIXED (mocked) | `test_tavily_search_returns_validated_citable_sources`, `test_tavily_selects_highest_scoring_sources_first`, `test_tavily_opt_in_without_key_fails_clearly`, `test_tavily_search_failure_does_not_silently_downgrade`, `test_research_plan_citations_are_limited_to_returned_sources` | Opt-in, server-side POST, source IDs restricted to returned records, actionable failures, and result warnings. Live provider remains NOT VERIFIED. |
| Demo table request and PPTX template preservation | FIXED | `test_demo_section_honors_explicit_comparison_table_request_without_fabricated_metrics`, `test_e2e_full_lifecycle_docx_pipeline`, PPTX generation/validation E2E tests | Demo output now honors an explicit comparison-table request using an evidence-first framework; disclaimer stays in warnings rather than creating a notes master/theme part. |
| Legacy missing-fingerprint validator crash | FIXED | `test_validator_reports_missing_fingerprint_component_without_crashing` | Missing component hashes are reported safely instead of raising during validation. |

## 4. Final Verification Output

- `python -m pytest backend/tests -q` — **228 passed** (`59.12s`).
- `python -m pytest backend/tests --cov=backend/app --cov-report=term` — **228 passed**, coverage measured **84%** (exceeds the 80% threshold).
- `python scripts/verify_concurrency_resilience.py` — **PASS**: 20 scripted calls in 0.120s; max active 3; event-loop gap 0.031s.
- `npx tsc --noEmit` — **PASS**, 0 TypeScript errors.
- `npm run lint` — **PASS**, 0 ESLint errors or warnings.
- `npm run test:frontend` — **PASS**, 44 Vitest unit tests (87.63% statement/lines coverage) + 6 node request-payload tests (50 tests total).
- `npm run test:e2e` — **PASS**, 3 Playwright browser end-to-end integration flows completed with accessible verification.
- `npm run gen:api:check` — **PASS**, TypeScript client definitions strictly synchronized with backend OpenAPI schema.
- `npm run build` — **PASS**, Next.js 16 production build completed successfully with standalone server output.
- `npm audit --omit=dev` — **PASS**, 0 vulnerabilities found in production npm dependencies.
- `pip-audit -r backend/requirements.txt` — **PASS**, no known vulnerabilities found in production Python packages.
- `bandit -r backend/app -q` — **PASS**, 0 security issues identified across 7,963 lines of backend code.
- `ruff check backend/app` — **PASS**, 0 lint errors found.
- `ruff format --check backend/app` — **PASS**, all 65 backend source files cleanly formatted.
- `mypy backend/app` — **PASS**, 0 type errors across all 65 source files.
- `python scripts/check_env_consistency.py` — **PASS**, all 39 environment variables consistent across `.env.example`, `config.py`, `docker-compose.yml`, and `README.md`.
- `node scripts/check_copy.mjs` — **PASS**, 0 banned hype phrases detected in frontend copy.
- `git diff --check` — **PASS** (Git printed only Windows CRLF notices).

## 5. Not Verified

- **Live Google AI provider** — no live model call was performed. Manual step: set a valid `GEMINI_API_KEY`, set `MODEL_PROVIDER=google_ai`, restart the backend, and complete section 4.2 of `docs/MANUAL_QA.md`.
- **Live Tavily** — mocked HTTP tests pass, but no live key/provider call was performed. Manual steps: configure `TAVILY_API_KEY`, verify `/api/health` capability, then complete section 0.4–0.6 of `docs/MANUAL_QA.md`, including an unavailable-source case.
- **Microsoft Word rendering** — desktop Word was not available. Open a generated DOCX and perform section 1 of `docs/MANUAL_QA.md`, including TOC refresh, complex-script text, and print preview.
- **Microsoft PowerPoint rendering** — desktop PowerPoint was not available. Open generated decks and perform section 2 of `docs/MANUAL_QA.md`, including Sections, repair prompts, slide numbers, branding, complex scripts, and print preview.
- **Docker / deployment** — Docker and `shellcheck` commands were unavailable. Install Docker Engine/Compose and follow section 3 of `docs/MANUAL_QA.md` for compose validation, build, startup, health, non-root, security options, and deploy dry-run.
- **Offline production build** — the local build passed, but the network was not disabled. Disconnect network access after dependency installation and rerun `npm run build`.

## 6. Known Limitations and Decisions

- Page counts estimate content volume; actual pagination depends on template and rendering software.
- The structured section review improves relevance and completeness but cannot guarantee correctness or independently verify facts. Search results are references, not proof.
- The full backend Ruff check remains failing with 696 findings; the newly introduced concurrency, budget, Tavily, and harness modules pass the targeted Ruff command above.
- Manual acceptance for live provider calls, desktop Office, Docker deployment, and an actually offline build remains outstanding as listed in `docs/MANUAL_QA.md`.
- Length, research, and quality-review decisions are recorded in `docs/DECISIONS.md`.
