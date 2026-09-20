# DocGuru — Exact Template Inheritance Engine

DocGuru is an exact template-preserving AI document and presentation generator. A user uploads a **DOCX**, **PPTX**, or **PDF** template and gives a prompt to receive a new document or deck that strictly preserves the original template's typography, styles, layout geometry, numbering, and headers/footers while incorporating newly synthesized content.

## Architecture

- **Backend**: FastAPI (Python 3.12) in `backend/`
- **Frontend**: Next.js 16 (App Router, React 19, Tailwind v4, TypeScript strict) in `src/`
- **Pipeline**: Upload -> Analyze (`TemplateSpecification`) -> Plan (`planner.py`) -> Content Fitting (`content_fitter.py`) -> Execute (`docx_engine.py` / `pptx_engine.py`) -> Validate (`diff_validator.py`) -> Download.

## Modes

1. **Live Mode** (`MODEL_PROVIDER=google_ai`): Real AI content powered by Gemini/Gemma models. Requires `GEMINI_API_KEY`. If misconfigured or unavailable, clear typed errors are returned; never silent fake content.
2. **Demo Mode** (`MODEL_PROVIDER=demo`): Deterministic, topic-agnostic offline generation for testing and demonstrations. Explicitly marked as demo content throughout UI and outputs.
3. **Local Mode** (`MODEL_PROVIDER=ollama`): Native async HTTP integration with local Ollama runtime.

## Configuration Table

The table below lists all supported configuration variables. All names and defaults match `.env.example`, `docker-compose.yml`, and `backend/app/config.py`.

| Variable | Default | Description |
| --- | --- | --- |
| `MODEL_PROVIDER` | `google_ai` | AI provider (`google_ai`, `ollama`, `openai_compat`, `demo`). |
| `MODEL_NAME` | `gemma-4-31b-it` | Model identifier to invoke. |
| `MODEL_ENDPOINT` | `https://generativelanguage.googleapis.com/v1beta` | Provider endpoint URL (auto-set per provider). |
| `GEMINI_API_KEY` | `""` | Google AI Studio API key for live generation. |
| `GEMMA_API_KEY` | `""` | Deprecated alias for `GEMINI_API_KEY`. |
| `TEMPERATURE` | `0.2` | Sampling temperature for LLM generation. |
| `LLM_TIMEOUT_SEC` | `90` | Request timeout for LLM provider calls in seconds. |
| `LLM_MAX_RETRIES` | `3` | Maximum number of retries for transient LLM errors. |
| `LLM_MAX_CONCURRENCY` | `3` | Maximum concurrent LLM requests. |
| `LLM_THINKING` | `default` | Reasoning mode (`off` or `default`). |
| `OUTLINE_MAX_TOKENS` | `1200` | Token limit for document outline generation. |
| `SECTION_MAX_TOKENS` | `1800` | Token limit for per-section generation. |
| `DEBUG` | `false` | Enable verbose debug logging. |
| `LOG_CONTENT` | `false` | Enable logging of prompt and document content (disabled by default for privacy). |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed CORS origins (wildcard `*` rejected). |
| `API_KEYS` | `""` | Comma-separated list of valid backend API keys. |
| `MAX_UPLOAD_MB` | `25` | Maximum upload size in megabytes. |
| `MAX_PDF_PAGES` | `100` | Maximum pages allowed for PDF templates. |
| `RETENTION_HOURS` | `24` | Storage retention TTL for templates and outputs in hours. |
| `WORKER_THREADS` | `4` | Concurrency limiter capacity for sync CPU workloads. |
| `MAX_CONCURRENT_JOBS` | `4` | Maximum concurrent document generation jobs. |
| `MIN_FREE_MB` | `512` | Minimum free disk space in megabytes for readiness checks. |
| `PREVIEW_ENABLED` | `false` | Enable headless LibreOffice PDF/PNG thumbnail previews. |
| `PAGE_BREAK_BETWEEN_SECTIONS` | `false` | Insert hard page breaks between sections. |
| `IMAGE_PLACEHOLDERS` | `false` | Render neutral placeholder cards when images are absent. |
| `IMAGE_CACHE_MAX_MB` | `500` | Maximum disk cache size for images in megabytes. |
| `IMAGE_TIMEOUT_SEC` | `8` | Timeout per image download in seconds. |
| `IMAGE_BUDGET_SEC` | `25` | Overall image retrieval budget per document in seconds. |
| `UNSPLASH_ACCESS_KEY` | `""` | API key for Unsplash image retrieval. |
| `PEXELS_API_KEY` | `""` | API key for Pexels image retrieval. |
| `BACKEND_URL` | `http://127.0.0.1:8000` | URL of the backend service used by Next.js API routes. |

## Quick Start

### Local Development

1. **Backend**:
   ```bash
   pip install -r backend/requirements.txt -r backend/requirements-dev.txt
   python -m uvicorn backend.app.main:app --port 8000 --reload
   ```

2. **Frontend**:
   ```bash
   npm install
   npm run dev
   ```

### Docker Deployment

```bash
# Production stack
docker compose up -d --build

# With local Ollama profile
docker compose --profile ollama up -d --build
```
