# DocGuru Fix Report

## Baseline (before)

- `npm run lint`: passed during the initial project audit.
- `npm run build`: passed during the initial project audit.
- `python -m pytest backend/tests -q`: initial baseline collected 89 tests passing with `ollama` installed, plus failures when `ollama` was absent.

## Phase 0

| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| P0 | FIXED | `backend/tests/regression` — 7 strict expected failures | cf5b6af | Regression fixtures created programmatically; no binary fixtures added. |

The expected failures cover CFG-01, LLM-01, DOCX-01, PPTX-02, VAL-01, IMG-01, and SEC-01.

## Phase 1

| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| CFG-01 | FIXED | `test_config_clean_install.py`, `test_r1_r2_resilience.py` | fa3c581 | Removed `import ollama`; implemented Ollama over native `httpx`; mocked with `respx`; pinned `requirements.txt` & `requirements-dev.txt`; AST scan verified. |
| CFG-02/03/04 | FIXED | `test_settings.py`, `scripts/check_env_consistency.py` | 984cf6b | Unified Settings with pydantic-settings; provider defaults; alias warning; consistency script validates `.env.example`, compose, README, and config. |
| SEC-06 | FIXED | `test_error_handling.py`, route modules | 4113127 | Typed `AppError` hierarchy; structured error envelope without path/traceback leakage; `X-Request-ID` echoed; fixed 400->500 masking. |
| SEC-06b | FIXED | `test_health.py`, `main.py` | 4113127 | `/health/live`, `/health/ready` (disk & dir checks), and `/api/health` with model info and capabilities. |
