# Seminar & Structured Template In-Place Generation Plan

## Overview
We will upgrade the document analysis, rule extraction, and synthesis pipeline so uploaded seminar reports and structured institutional templates are populated **in-place** rather than appending a second document at the end. Embedded formatting rules and instruction notes written inside the template will be automatically parsed, strictly enforced on generated headings and body paragraphs, and completely stripped from the final document.

---

## Key Features & Changes

### 1. In-Place Front Matter Preservation & Chapter Replacement (Eliminating the "Second Document" Bug)
- **Broadened Structured Template Detection**: Expand template analysis so any multi-page or structured `.docx` template containing front matter (`Cover Page`, `Certificate`, `Declaration`, `Acknowledgement`, `Abstract`, `Table of Contents`) or sample chapter anchors (`Chapter 1`, `1. Introduction`, `Main Body`) is recognized for **in-place inhabitation** rather than falling back to append mode.
- **Clean Chapter Anchor Truncation**: Locate the exact start of the body/sample chapter section, preserve all preceding front-matter sections and section breaks (`w:sectPr`), and remove all sample chapters and dummy body paragraphs from that anchor onward before inserting the newly generated chapters.
- **Unified Engine Support**: Synchronize this in-place replacement behavior across both the Python backend (`docx_analyzer.py` + `docx_engine.py`) and the built-in Next.js standalone engine (`standalone-engine.ts`).

### 2. Automatic Rule Extraction, Enforcement & Complete Instruction Stripping
- **Comprehensive Rule Parser**: Extract typography and layout rules written inside the template body (such as `Font Style: Times New Roman`, `Font Size: 14 pt. (Bold)`, `For All Content Font Size: 12`, `Line Spacing: 1.5`, `Alignment: Justified`, `ALL CAPS`, `Centered`, and margin/numbering instructions).
- **Strict Formatting Application**: Apply the extracted rules directly to generated chapter titles, numbered subheadings (`1.1`, `1.1.1`), body paragraphs, bullet lists, and captions so the output matches the template's exact typography specifications.
- **Complete Instruction & Guideline Removal**: Strip all instructional paragraphs, formatting tips, and guideline notes (e.g., `Font Style: ...`, `Sub Heading Formatting Tips:`, `Note: Chapter 1 will start from this page`, `(Write approximately 200 words...)`, `[Insert ... here]`) across front matter, abstract, table of contents, and body sections while preserving any attached page/section breaks (`w:sectPr`).

### 3. Front-Matter Metadata Inputs & Automatic Prompt Detection
- **Optional Metadata Controls in UI**: Add a collapsible **Report & Author Details (Optional)** section in the prompt configuration panel allowing users to enter **Student / Author Name**, **Roll / ID Number**, **Guide / Supervisor Name**, **Department**, **Institution / College**, and **Academic Year** when working with `.docx` templates.
- **Automatic Prompt Extraction Fallback**: Automatically extract author, guide, department, institution, and title metadata from the user's prompt if those optional fields are left blank, and populate the Cover Page, Certificate, Acknowledgement, Abstract, and Table of Contents placeholders seamlessly.

### 4. Clean Paragraph Splitting & Warning Resolution
- **Improved Sentence & Clause Splitting**: Refine `ContentFitter` paragraph splitting to recognize abbreviations, semicolons, and natural clause boundaries cleanly before falling back to word boundaries.
- **Suppress Internal Splitter Tokens from User Warnings**: Stop emitting raw internal machine tokens like `long_sentence_split_at_word_boundary` and `long_sentence_split_at_clause_boundary` into user-facing result warnings, ensuring only actionable human-readable validation feedback is shown in the result panel.

---

## Architecture & Files to Update

- **`backend/app/analyzer/docx_analyzer.py`**: Broaden institutional/seminar front-matter detection, instruction-line pattern matching, and typography rule extraction from inline template text.
- **`backend/app/engines/docx_engine.py`**:
  - Prevent `template_mode="auto"` from falling into `append` mode on structured templates.
  - Purge all matched instruction/guideline paragraphs cleanly from front matter, abstract, TOC, and body while preserving section breaks (`w:sectPr`).
  - Apply extracted typography rules (font family, size, bold/italic, uppercase, alignment, `1.5` line spacing) to all generated sections and front-matter insertions.
- **`backend/app/ai/content_fitter.py`**: Improve sentence boundary splitting and remove raw `long_sentence_split_at_word_boundary` / `long_sentence_split_at_clause_boundary` warning tokens.
- **`src/lib/standalone-engine.ts`**: Mirror institutional template rule extraction, instruction paragraph removal, front-matter placeholder substitution, and in-place chapter replacement in the standalone OpenXML engine.
- **`src/app/components/PromptInput.tsx` & `src/app/page.tsx`**: Add optional Author / Guide / Department / Institution metadata inputs and wire them into the generation request payload.
- **Automated Tests**: Add regression tests covering seminar report in-place generation, instruction text stripping, rule enforcement, and clean warning output.
