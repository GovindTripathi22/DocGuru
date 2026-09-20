# DocGuru Fix Report

## Baseline (before)

- `npm run lint`: passed during the initial project audit.
- `npm run build`: passed during the initial project audit.
- `python -m pytest backend/tests -q`: the full suite exceeds this host's
  single-command execution window; earlier audit runs reached the end-to-end
  workflow tests without a failure. It will be rerun in the final gate.

## Phase 0

| ID | Status | Evidence | Commit | Notes |
| --- | --- | --- | --- | --- |
| P0 | FIXED | `backend/tests/regression` — 7 strict expected failures | Pending | Regression fixtures are created programmatically; no binary fixtures were added. |

The expected failures cover CFG-01, LLM-01, DOCX-01, PPTX-02, VAL-01,
IMG-01, and SEC-01. They document confirmed current behavior and will be
unmarked only as their corresponding implementation fixes land.
