# DocGuru Manual QA Verification Guide

This guide provides step-by-step instructions for human QA testing across Microsoft Word, Microsoft PowerPoint, Docker containers, and live LLM integrations.

---

## 1. Microsoft Word (.docx) Verification

1. **Setup**:
   - Upload a custom branded Word template containing custom fonts, headers, footers, and a 2x2 table.
   - Generate a document with prompt: *"Quarterly Business Review for Project Atlas"*.
   - Download the generated `.docx` file.

2. **Visual & Layout Inspection in Microsoft Word**:
   - **Margins & Page Setup**: Open `Layout -> Margins`. Confirm top, bottom, left, and right margins exactly match the source template (e.g. 1.0" or custom values).
   - **Document Title (DOCX-01)**: Confirm the document title is clearly rendered at the top of the body before the first section.
   - **Conclusion Section (DOCX-01)**: Scroll to the end of the document. Confirm a dedicated conclusion/summary section is present.
   - **Table Inheritance**: Locate generated tables. Confirm that column styles, header row shading, cell borders, and padding replicate the template's table styles.
   - **Header & Footer Continuity**: Verify that page numbers, header logos, and footer text from the template persist across all pages.
   - **Style Inspector**: Select generated headings and body paragraphs. Verify they use the template's named styles (e.g. `Heading 1`, `Heading 2`, `Normal`) without inline font overrides.

---

## 2. Microsoft PowerPoint (.pptx) Verification

1. **Setup**:
   - Upload a branded `.pptx` template (test both 16:9 widescreen and 4:3 standard templates).
   - Generate a presentation with prompt: *"AI Adoption Strategy for Financial Services"*.
   - Download the generated `.pptx` file.

2. **Visual & Layout Inspection in Microsoft PowerPoint**:
   - **Slide Master Geometries**: Open `View -> Slide Master`. Confirm the master layout hierarchy and color schemes remain unaltered.
   - **Slide Dimensions (PPTX-01)**: Confirm presentation retains its original aspect ratio (16:9 widescreen 13.33"x7.5" or 4:3 10"x7.5") without stretching or black bars.
   - **Bullet Point Structures (PPTX-02)**: Inspect multi-point slides. Verify that bullet markers (`•`, dashes, or numbered lists) remain intact and are not flattened into raw unformatted text blocks.
   - **Card & Container Bounds**: Verify that generated cards, stat callouts, and text containers do not overflow the slide boundaries or collide with footer logos.

---

## 3. Docker Container & Security Verification

1. **Build & Start Services**:
   ```bash
   docker compose build
   docker compose up -d
   ```

2. **Verify Container Health**:
   ```bash
   docker compose ps
   ```
   *Expected*: Both `backend` and `frontend` display `(healthy)`.

3. **Verify Non-Root Process Execution (OPS-03)**:
   ```bash
   docker compose exec backend whoami
   # Expected: docguru (UID 10001)

   docker compose exec frontend whoami
   # Expected: node (UID 1000)
   ```

4. **Verify Health Endpoints**:
   ```bash
   curl -i http://localhost:8000/health/live
   # Expected: HTTP 200 {"status":"live"}

   curl -i http://localhost:8000/health/ready
   # Expected: HTTP 200 {"status":"ready", ...}

   curl -i http://localhost:3000
   # Expected: HTTP 200
   ```

5. **Verify Security Options**:
   ```bash
   docker inspect --format '{{.HostConfig.SecurityOpt}}' $(docker compose ps -q backend)
   # Expected: [no-new-privileges:true]
   ```

---

## 4. LLM Provider & Fail-Safe Verification

1. **Unconfigured Live Provider (Fail-Safe Invariant)**:
   - In `.env`, set:
     ```env
     MODEL_PROVIDER=google_ai
     GEMMA_API_KEY=
     ```
   - Restart backend and attempt generation via `POST /api/generate`.
   - *Expected*: Immediate `503 Service Unavailable` with error code `LLM_NOT_CONFIGURED`.
   - *Crucial Check*: Verify the system **NEVER** silently falls back to canned demo text when live mode is requested.

2. **Real Google AI Studio / Gemma Verification**:
   - In `.env`, set:
     ```env
     MODEL_PROVIDER=google_ai
     GEMMA_API_KEY=your_actual_studio_key_here
     ```
   - Request generation via web UI.
   - *Expected*: Generation job transitions through `analyzing` -> `planning` -> `generating` -> `completed` with real AI-generated content relevant to the prompt.

3. **Offline Demo Mode**:
   - In `.env`, set:
     ```env
     MODEL_PROVIDER=demo
     ```
   - Generate document with prompt *"Renewable Energy Transition in 2030"*.
   - *Expected*: Instant generation of coherent, topic-derived synthetic sections without external network access.
