# DocGuru Template Validation Architecture

This document describes DocGuru's template preservation guarantees, canonicalization fingerprinting, and structural diff validation mechanics.

---

## 1. Overview & Invariants

DocGuru operates on an **exact template inheritance** model:
- Templates provided by users (in `.docx` or `.pptx` format) define sacred styling, layout structures, geometries, and typography.
- Generated content is injected into new or cloned structures derived from the template.
- The underlying styling schemas, margins, themes, master slides, and font tables must remain structurally intact.

---

## 2. Immutable vs. Mutable Components

When transforming a template into a generated document:

### Immutable Components (Strict Invariant)
These components are guarded by `backend/app/engines/style_lock.py` and validated by `backend/app/validation/fingerprint.py` & `diff_validator.py`:
- **Document Margins & Geometry**: Page width, height, top/bottom/left/right margins, and header/footer distances defined in `w:sectPr`.
- **Slide Master Geometries**: Slide dimensions (`p:sldSz`), slide master layouts, and placeholder geometry definitions in `.pptx`.
- **Style Tables & Theme Palettes**: `word/styles.xml`, `ppt/theme/theme1.xml`, color schemes, font definitions (`w:fonts`, `p:fontScheme`).
- **Document Settings**: `word/settings.xml` and core relationship files.

### Mutable Components (Permitted Additions)
- **Text Runs & Paragraphs**: New content injected into paragraphs with matching style IDs (e.g. `Heading 1`, `Heading 2`, `Normal`, `Body Text`).
- **Cloned Table Rows**: Tables present in the template can be replicated and populated with row data, preserving cell borders, shading, and cell margins.
- **Slide Clones & Layout Instances**: Slides derived from existing slide layouts with text injected into layout placeholders.
- **Embedded Visual Assets**: Images placed within designated bounding boxes with correct aspect ratios and relational part registration.

---

## 3. Package Canonicalization Fingerprint (`fingerprint.py`)

To verify that template styling has not drifted without comparing transient binary artifacts, DocGuru uses XML canonicalization (c14n) hashing:

1. **Extraction**:
   - For DOCX: `word/styles.xml`, `word/theme/theme1.xml`, `word/settings.xml`.
   - For PPTX: `ppt/presentation.xml`, `ppt/theme/theme1.xml`, `ppt/slideMasters/slideMaster1.xml`.
2. **Canonicalization**:
   - Strips whitespace variations, comments, and non-semantic XML attributes.
   - Sorts attributes deterministically.
   - Resolves namespace prefixes uniformly.
3. **SHA-256 Hashing**:
   - Produces a cryptographic fingerprint representing the immutable style payload.
   - Any modification to style definitions, fonts, or margin structures alters the canonical fingerprint.

---

## 4. Mutation-Sensitive Diff Validator (`diff_validator.py`)

`DiffValidator` inspects the generated package against the original template:
- **Structural Integrity**: Confirms that expected style nodes exist in the output with matching attributes.
- **Margin Lock Check**: Verifies that `w:top`, `w:bottom`, `w:left`, and `w:right` values match between template and output.
- **Slide Master Integrity**: Confirms slide layouts and theme definitions in `.pptx` remain structurally identical.
- **Component Verification**: Returns a granular breakdown of verified elements (margins, fonts, tables, styles, slide masters) consumed by the frontend `ResultPanel`.

---

## 5. Automated Verification

The validation engine is verified continuously by the test suite:
- `backend/tests/test_canonical_fingerprint.py`: Canonical XML sorting, attribute normalization, and fingerprint stability.
- `backend/tests/test_diff_validator.py`: Margin drift detection, style mutation sensitivity, and false-positive immunity.
- `backend/tests/test_docx_engine.py`: Margin preservation (`w:sectPr`) and table cloning.
- `backend/tests/test_pptx_engine.py`: 16:9 and 4:3 slide dimension preservation, layout fallback resilience, and bullet point structure preservation.
