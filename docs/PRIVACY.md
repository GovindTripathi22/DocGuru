# DocGuru Privacy & Security Architecture

This document details DocGuru's data lifecycle, storage retention policies, prompt sanitization, log redaction, and path security mechanisms.

---

## 1. Data Retention & Lifecycle Management

DocGuru processes user templates and generated documents on a strict ephemeral model:

### Directory Storage
All runtime files reside under `backend/data/`:
- `backend/data/uploads/`: Original uploaded templates (`.docx`, `.pptx`, `.pdf`).
- `backend/data/jobs/{job_id}/`: Job metadata, request specs, and snapshot state.
- `backend/data/outputs/`: Final generated `.docx` and `.pptx` artifacts.

### Automated Retention Purge
- **Configurable Retention**: Governed by `RETENTION_HOURS` in `config.py` (default: `24` hours).
- **Background Purge**: On startup and periodically via `backend/app/jobs/manager.py`, files and job records older than `RETENTION_HOURS` are permanently deleted from disk.
- **Immediate Cleanup Endpoints**:
  - `DELETE /api/jobs/{job_id}`: Cancels running job (if active) and purges job directory.
  - `DELETE /api/templates/{template_id}`: Removes the uploaded template artifact immediately.
  - `DELETE /api/outputs/{output_id}`: Removes the generated document artifact immediately.

---

## 2. Prompt Handling & Injection Defense

### Normalization
- All incoming user prompts pass through `backend/app/planning/normalize.py`.
- Control characters, excessive repetition, and schema-breaking formatting are sanitized.

### Injection Quarantine
- Direct instruction overrides (e.g. attempting to override template margins, ignore formatting locks, or exfiltrate server environment) are detected.
- The document planning engine enforces structural invariants as system-level constraints: prompt instructions cannot alter XML styles, document schemas, or margin definitions.

---

## 3. Log Content Privacy (`LOG_CONTENT`)

By default, DocGuru operates with privacy-safe structured logging:
- **`LOG_CONTENT=false` (Default)**:
  - Prompts, raw document content, LLM completion tokens, and template text are strictly redacted from application logs.
  - Logs capture only metadata: `request_id`, HTTP method, route, response status, duration, and high-level error codes.
- **`LOG_CONTENT=true` (Explicit Debug Only)**:
  - Enables detailed payload logging for local development and debugging.
  - Must never be enabled in production environments handling sensitive user documents.

---

## 4. File Boundary & Path Traversal Protection

### Path Containment (`safe_path_join`)
- Implemented in `backend/app/security.py`.
- Resolves target paths using `os.path.abspath` and verifies they remain strictly within the designated parent folder (`backend/data/`).
- Prevents directory traversal attacks (`../`, `%2e%2e%2f`, null bytes).
- Attempted traversal requests result in an immediate `400 Bad Request` or `404 Not Found` without disclosing file system structure.

### Upload Limits
- **Max Upload Size**: Controlled by `MAX_UPLOAD_MB` (default: `25MB`). Excessively large files are rejected before processing.
- **Max PDF Pages**: Controlled by `MAX_PDF_PAGES` (default: `100` pages) to prevent PDF bomb memory exhaustion.
- **MIME & Extension Whitelisting**: Only valid `.docx`, `.pptx`, and `.pdf` packages are accepted.
