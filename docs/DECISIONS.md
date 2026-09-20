# DocGuru Architectural & Implementation Decisions

This document records the architectural decisions, trade-offs, and invariants established during the DocGuru remediation program.

---

## 1. Ground Rules & Principles
- **The Master Work Order is Law**: Requirements in the master plan supersede preliminary or legacy assumptions.
- **Fail Fast, Never Fake**: Unconfigured services must return clear, typed errors (e.g. 503 `LLM_NOT_CONFIGURED`) rather than falling back silently to canned demo outputs.
- **Truthful UI**: The user interface must never present misleading metrics or marketing superlatives ("100% preservation", "Zero Drift", "Sacred"). All reported metrics derive from real backend validation checks.
- **Offline Self-Sufficiency**: Builds and local operations must succeed without live external network dependencies (no Google Fonts download at build time, robust offline image fallbacks, offline demo provider).

---

## 2. Architecture & Subsystem Decisions

### CFG & Configuration
- **Native Async HTTP Over Library Wrapper**: Removed `ollama` Python client package in favor of `httpx` with `respx` mocking. This eliminated orphaned background threads and unhandled socket teardown in async event loops.
- **Unified Settings**: Standardized all configuration in `backend/app/config.py` using `pydantic-settings`. Guaranteed consistency across `.env.example`, `docker-compose.yml`, and `README.md` via `scripts/check_env_consistency.py`.

### Security & Error Handling
- **Typed Error Hierarchy**: Replaced raw exceptions and 500 error cascades with `AppError` and subclasses (`ValidationError`, `NotFoundError`, `SecurityError`, `LLMError`).
- **No Path or Traceback Disclosures**: Error responses present an RFC-compliant JSON envelope with an echoed `X-Request-ID` and redacted filesystem paths.
- **Containment via `safe_path_join`**: All file operations validate that resolved paths strictly reside under `backend/data/` before accessing files.
- **Privacy-Safe Structured Logging**: By default (`LOG_CONTENT=false`), user prompts, template text, and AI tokens are never printed to stdout/stderr.

### LLM Providers & Document Planning
- **Unified Provider Interface**: Standardized provider abstractions (`GoogleAIProvider`, `OllamaProvider`, `DemoProvider`) handling streaming, structured JSON schemas, and timeouts.
- **Dynamic Topic-Derived Demo Mode**: When `MODEL_PROVIDER=demo` is selected, content is synthesized from prompt keywords dynamically rather than displaying a static, canned paragraph.
- **Prompt Sanitization & Quarantine**: Prompts are normalized before schema generation; prompt injection attempts cannot alter document formatting invariants.

### Engines & Invariant Enforcement
- **Canonicalization Fingerprinting (`fingerprint.py`)**: Implemented XML c14n sorting and attribute normalization to verify style integrity without false positives from zip metadata.
- **DOCX Title & Conclusion (`DOCX-01`)**: Explicitly render document titles and concluding sections during new document creation.
- **PPTX Fallback & List Hierarchy (`PPTX-01`, `PPTX-02`)**: Added capability-matching fallback for slide layouts and safeguarded bullet marker preservation during shape cloning.
- **Cached Visual Assets (`IMG-01`)**: SHA-256 query caching with strict timeout budgets (<= 2s) and offline geometric SVG generation.

### Jobs & Asynchronous Processing
- **202 Accepted Async Pipeline**: `POST /api/generate` returns `202 Accepted` with a `job_id` and snapshot state in `backend/data/jobs/`. Clients poll `GET /api/jobs/{id}` and can cancel via `DELETE /api/jobs/{id}`.
- **Synchronous Override (`?wait=true`)**: Direct task execution bypasses background queues for automated integration testing and CLI scripting.
- **Retention Lifecycle**: Automatic startup and maintenance purging of jobs older than `RETENTION_HOURS` (default 24h).

### Frontend & DevOps
- **Offline Fonts**: Replaced `next/font/google` with system font stacks to ensure air-gapped production builds succeed.
- **Dynamic Progress & Component Verification**: Built `ProgressPanel` and `ResultPanel` to poll real backend job states and display actual verified OpenXML components.
- **Hardened Containers**: Implemented non-root multi-stage Docker builds (`docguru` UID 10001, `node` UID 1000), `tini` process management, and compose security options (`no-new-privileges:true`).
- **Automated CI**: Full-stack CI pipeline in `.github/workflows/ci.yml` covering consistency checks, pytest suite, TypeScript checking, ESLint, copy checks, and Next.js production builds.
