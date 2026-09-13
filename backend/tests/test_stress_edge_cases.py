import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List

import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt, RGBColor
from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt

from backend.app.ai.content_fitter import ContentFitter
from backend.app.analyzer.docx_analyzer import DocxAnalyzer
from backend.app.analyzer.pptx_analyzer import PptxAnalyzer
from backend.app.analyzer.template_analyzer import TemplateAnalyzer
from backend.app.engines.docx_engine import DocxEngine
from backend.app.engines.pptx_engine import PptxEngine
from backend.app.engines.style_lock import StyleLock, StyleLockViolationError
from backend.app.models.generation import (
    DocumentPlan,
    DocumentSection,
    PresentationPlan,
    SlidePlan,
    TableData,
)
from backend.app.validation.diff_validator import DiffValidator
from backend.app.validation.style_hash import StyleHasher


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def pptx_4_3_template(tmp_path: Path) -> Path:
    """
    Creates a standard 4:3 aspect ratio PPTX template (10.0 x 7.5 inches).
    """
    file_path = tmp_path / "template_4_3.pptx"
    prs = Presentation()
    prs.slide_width = PptxInches(10.0)
    prs.slide_height = PptxInches(7.5)

    # Slide 1: Title Slide Layout (index 0)
    title_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_layout)
    slide1.placeholders[0].text = "4:3 Standard Template Presentation"
    slide1.placeholders[1].text = "Legacy 4:3 Ratio Master Verification"

    # Slide 2: Title and Content Layout (index 1)
    content_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(content_layout)
    slide2.placeholders[0].text = "Standard 4:3 Layout Content"
    tf = slide2.placeholders[1].text_frame
    tf.text = "Bullet 1: 4:3 format specification"

    prs.save(str(file_path))
    return file_path


@pytest.fixture
def docx_custom_table_template(tmp_path: Path) -> Path:
    """
    Creates a DOCX template with a deeply customized table (shading, borders, cell margins).
    """
    file_path = tmp_path / "custom_table_template.docx"
    doc = Document()

    # Configure page setup
    section = doc.sections[0]
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    doc.add_paragraph("Custom Styled Table Template", style="Title")
    doc.add_paragraph("Section with rich table styling", style="Heading 1")

    # Add a 2x3 table with custom XML shading and borders
    table = doc.add_table(rows=2, cols=3)
    table.style = "Table Grid"

    # Style Header Row
    headers = ["Component", "Status", "Throughput"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        if cell.paragraphs[0].runs:
            cell.paragraphs[0].runs[0].font.bold = True
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        # Add Navy Header Shading
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="003366"/>')
        tcPr.append(shd)

    # Style Sample Data Row
    sample_data = ["Neural Core", "Active", "12,450 req/s"]
    for i, val in enumerate(sample_data):
        cell = table.cell(1, i)
        cell.text = val
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F0F4F8"/>')
        tcPr.append(shd)

    doc.save(str(file_path))
    return file_path


# ==============================================================================
# TEST SUITE 1: MINIMAL TEMPLATES WITHOUT HEADING STYLES
# ==============================================================================

def test_minimal_docx_template_without_heading_styles_safe_fallback(tmp_path: Path):
    """
    R3.1: Minimal templates lacking Heading 1/2 styles must safely fallback
    without throwing KeyError or crashing, preserving valid DOCX and style hash.
    """
    minimal_template = tmp_path / "bare_template.docx"
    doc = Document()
    doc.add_paragraph("Bare minimal document with no custom heading styles.")
    doc.save(str(minimal_template))

    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(minimal_template))

    assert spec.document_type == "docx"
    assert len(spec.style_hash) > 0

    engine = DocxEngine()
    locked_doc = engine.load_template(str(minimal_template), spec)

    # Plan requesting styles that definitely do not exist in the bare document
    plan = DocumentPlan(
        title="Stress Test on Bare Template",
        target_audience="Engineers",
        sections=[
            DocumentSection(
                title="Primary Stress Section",
                heading_style="Heading 1",  # Not in template
                paragraphs=[
                    "First stress paragraph running on bare template.",
                    "Second stress paragraph with standard formatting."
                ],
                bullets=[
                    "Fallback bullet point Alpha",
                    "Fallback bullet point Beta"
                ]
            ),
            DocumentSection(
                title="Secondary Sub-Stress Section",
                heading_style="Heading 2",  # Not in template
                paragraphs=["Sub-section paragraph content."]
            ),
            DocumentSection(
                title="Tertiary Custom Section",
                heading_style="NonExistentCustomHeaderStyle",  # Completely arbitrary style name
                paragraphs=["Tertiary paragraph content."]
            )
        ],
        conclusion="Successful execution of bare template stress test."
    )

    output_path = tmp_path / "generated_bare_output.docx"
    result_path = engine.generate_from_plan(locked_doc, plan, str(output_path))

    assert Path(result_path).exists()

    # Verify generated document
    gen_doc = Document(str(output_path))
    all_text = " ".join([p.text for p in gen_doc.paragraphs])

    assert "Primary Stress Section" in all_text
    assert "First stress paragraph running on bare template." in all_text
    assert "Fallback bullet point Alpha" in all_text
    assert "Secondary Sub-Stress Section" in all_text
    assert "Tertiary Custom Section" in all_text
    assert "Tertiary paragraph content." in all_text

    # Verify structural style hash equivalence between original bare template and output
    hasher = StyleHasher()
    is_match, orig_hash, gen_hash, diffs = hasher.compare_hashes(str(minimal_template), str(output_path))
    assert is_match is True
    assert orig_hash == gen_hash
    assert diffs == {}

    validator = DiffValidator()
    report = validator.validate(spec, str(output_path))
    assert report.passed is True
    assert report.hash_match is True
    assert len(report.issues) == 0


def test_docx_heading_fallback_safe_insertion(tmp_path: Path):
    """
    Verifies that insert_heading safely handles nonexistent styles without crashing,
    returning a valid paragraph containing the requested text.
    """
    minimal_template = tmp_path / "fallback_run_test.docx"
    doc = Document()
    doc.add_paragraph("Template body")
    doc.save(str(minimal_template))

    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(minimal_template))
    engine = DocxEngine()
    locked_doc = engine.load_template(str(minimal_template), spec)

    p1 = engine.insert_heading(locked_doc, "Fallback Title Heading 1", requested_style="Heading 1")
    assert p1 is not None
    assert p1.text == "Fallback Title Heading 1"

    p2 = engine.insert_heading(locked_doc, "Fallback Title NonExistent", requested_style="NonExistentStyle")
    assert p2 is not None
    assert p2.text == "Fallback Title NonExistent"


# ==============================================================================
# TEST SUITE 2: 16:9 VS 4:3 SLIDE DIMENSIONS & TABLE SCALING
# ==============================================================================

def test_pptx_4_3_aspect_ratio_fixture_and_layout(pptx_4_3_template: Path, tmp_path: Path):
    """
    R3.2: Verify 4:3 PPTX template fixture (10.0 x 7.5 in) extraction,
    slide layout instantiation, and table scaling vs 16:9 widescreen.
    """
    analyzer = PptxAnalyzer()
    spec = analyzer.analyze(str(pptx_4_3_template))

    assert spec.document_type == "pptx"
    assert spec.slide_dimensions is not None
    assert spec.slide_dimensions.aspect_ratio == "4:3"
    assert spec.slide_dimensions.width_inches == 10.0
    assert spec.slide_dimensions.height_inches == 7.5
    assert len(spec.available_layout_names) > 0

    engine = PptxEngine()
    locked_prs = engine.load_template(str(pptx_4_3_template), spec)

    plan = PresentationPlan(
        presentation_title="4:3 Ratio Stress Deck",
        audience="Executive Board",
        slides=[
            SlidePlan(
                slide_number=1,
                title="4:3 Executive Presentation",
                subtitle="High Integrity 4:3 Ratio Verification",
                layout_name=spec.available_layout_names[0],
                bullet_points=[]
            ),
            SlidePlan(
                slide_number=2,
                title="4:3 Dimension Matrix & Table Scaling",
                layout_name=spec.available_layout_names[1] if len(spec.available_layout_names) > 1 else spec.available_layout_names[0],
                bullet_points=[
                    "Aspect ratio locked at exactly 4:3 (10.0 x 7.5 in)",
                    "Dynamic table coordinates proportional to slide bounds"
                ],
                table_data=TableData(
                    headers=["Metric", "4:3 Target", "Result"],
                    rows=[
                        ["Width", "10.0 in", "10.0 in"],
                        ["Height", "7.5 in", "7.5 in"],
                        ["Scale factor", "0.84", "Preserved"]
                    ]
                )
            )
        ]
    )

    output_path = tmp_path / "generated_4_3_output.pptx"
    engine.generate_from_plan(locked_prs, plan, str(output_path))

    assert output_path.exists()

    gen_prs = Presentation(str(output_path))
    # Assert dimensions perfectly preserved in generated file
    assert round(gen_prs.slide_width.inches, 2) == 10.0
    assert round(gen_prs.slide_height.inches, 2) == 7.5
    assert len(gen_prs.slides) == 2

    # Verify table placement on Slide 2 matches 4:3 proportional bounds
    slide_2 = gen_prs.slides[1]
    table_shapes = [s for s in slide_2.shapes if s.has_table]
    assert len(table_shapes) == 1
    t_shape = table_shapes[0]

    # Check 4:3 table geometry (left = 10.0 * 0.08 = 0.8 in, width = 10.0 * 0.84 = 8.4 in)
    expected_left = PptxInches(10.0 * 0.08)
    expected_width = PptxInches(10.0 * 0.84)
    assert abs(t_shape.left - expected_left) < PptxInches(0.05)
    assert abs(t_shape.width - expected_width) < PptxInches(0.05)

    # Validate structural diff
    validator = DiffValidator()
    report = validator.validate(spec, str(output_path))
    assert report.passed is True
    assert report.hash_match is True
    assert report.layout_drift_detected is False


def test_16_9_vs_4_3_dimension_distinction_and_hash_isolation(
    sample_pptx_template: Path,
    pptx_4_3_template: Path,
    tmp_path: Path
):
    """
    R3.2: Verify 16:9 (13.333 x 7.5) and 4:3 (10.0 x 7.5) templates produce
    strictly distinct style hashes, and neither alters the other during generation.
    """
    analyzer = PptxAnalyzer()
    spec_16_9 = analyzer.analyze(str(sample_pptx_template))
    spec_4_3 = analyzer.analyze(str(pptx_4_3_template))

    assert spec_16_9.slide_dimensions.aspect_ratio == "16:9"
    assert spec_4_3.slide_dimensions.aspect_ratio == "4:3"
    assert spec_16_9.style_hash != spec_4_3.style_hash

    engine = PptxEngine()

    # Generate 16:9 output
    locked_16_9 = engine.load_template(str(sample_pptx_template), spec_16_9)
    plan_16_9 = PresentationPlan(
        presentation_title="16:9 Test",
        audience="Test",
        slides=[SlidePlan(slide_number=1, title="16:9 Title", layout_name=spec_16_9.available_layout_names[0])]
    )
    out_16_9 = tmp_path / "out_16_9.pptx"
    engine.generate_from_plan(locked_16_9, plan_16_9, str(out_16_9))

    # Generate 4:3 output
    locked_4_3 = engine.load_template(str(pptx_4_3_template), spec_4_3)
    plan_4_3 = PresentationPlan(
        presentation_title="4:3 Test",
        audience="Test",
        slides=[SlidePlan(slide_number=1, title="4:3 Title", layout_name=spec_4_3.available_layout_names[0])]
    )
    out_4_3 = tmp_path / "out_4_3.pptx"
    engine.generate_from_plan(locked_4_3, plan_4_3, str(out_4_3))

    hasher = StyleHasher()
    match_16_9, h1, h2, _ = hasher.compare_hashes(str(sample_pptx_template), str(out_16_9))
    match_4_3, h3, h4, _ = hasher.compare_hashes(str(pptx_4_3_template), str(out_4_3))

    assert match_16_9 is True
    assert match_4_3 is True
    assert h1 == h2 == spec_16_9.style_hash
    assert h3 == h4 == spec_4_3.style_hash
    assert h1 != h3


# ==============================================================================
# TEST SUITE 3: CONTENT FITTER (PARAGRAPH & BULLET AUTO-FITTING)
# ==============================================================================

def test_content_fitter_long_paragraph_chunking():
    """
    R3.3: Long paragraphs exceeding MAX_PARAGRAPH_WORDS (150 words) must be chunked
    into multiple readable paragraphs without modifying template fonts or margins,
    and without losing any words.
    """
    # Create 380 words paragraph
    words_source = [f"word{i}" for i in range(380)]
    long_paragraph = " ".join(words_source)

    plan = DocumentPlan(
        title="Content Fitter Long Paragraph Stress Test",
        target_audience="General",
        sections=[
            DocumentSection(
                title="Deep Analysis",
                heading_style="Heading 1",
                paragraphs=[long_paragraph, "Short paragraph under 150 words."],
                bullets=["Bullet 1"],
                subsections=[
                    DocumentSection(
                        title="Nested Sub-Analysis",
                        heading_style="Heading 2",
                        paragraphs=[" ".join([f"subword{i}" for i in range(220)])]
                    )
                ]
            )
        ],
        conclusion="Done."
    )

    fitted_plan = ContentFitter.fit_document_plan(plan)

    # Section 0 main paragraphs: 380 words should split into 150 + 150 + 80 (3 paras) + 1 short para = 4 paras
    main_sec = fitted_plan.sections[0]
    assert len(main_sec.paragraphs) == 4
    for idx, p in enumerate(main_sec.paragraphs[:3]):
        p_len = len(p.split())
        assert p_len <= ContentFitter.MAX_PARAGRAPH_WORDS

    # Verify zero word loss in chunked text
    reconstructed_words = " ".join(main_sec.paragraphs[:3]).split()
    assert reconstructed_words == words_source

    # Subsection: 220 words should split into 150 + 70 = 2 paras
    sub_sec = main_sec.subsections[0]
    assert len(sub_sec.paragraphs) == 2
    assert len(sub_sec.paragraphs[0].split()) == 150
    assert len(sub_sec.paragraphs[1].split()) == 70


def test_content_fitter_bullet_overflow_multislide_splitting():
    """
    R3.3: Slide bullet overflow (>5 items) must split into multiple consecutive slides
    with '(Cont.)' continuation titles while strictly reusing identical slide layouts.
    """
    bullets_14 = [f"Strategic Pillar {i+1}: Action item and detailed guidance description" for i in range(14)]

    plan = PresentationPlan(
        presentation_title="Bullet Overflow Deck",
        audience="Operations Team",
        slides=[
            SlidePlan(
                slide_number=1,
                title="Executive Agenda",
                subtitle="Q4 Operations",
                layout_name="Title Slide",
                bullet_points=[]
            ),
            SlidePlan(
                slide_number=2,
                title="Strategic Initiatives",
                layout_name="Title and Content",
                bullet_points=bullets_14
            ),
            SlidePlan(
                slide_number=3,
                title="Closing Notes",
                layout_name="Title and Content",
                bullet_points=["Single final bullet."]
            )
        ]
    )

    fitted_plan = ContentFitter.fit_presentation_plan(plan)

    # 1 Title Slide + (14 bullets split into 5, 5, 4 -> 3 slides) + 1 Closing Slide = 5 slides total
    assert len(fitted_plan.slides) == 5

    # Check slide sequence & numbers
    for idx, slide in enumerate(fitted_plan.slides):
        assert slide.slide_number == idx + 1

    # Check split slides
    s2 = fitted_plan.slides[1]
    assert s2.title == "Strategic Initiatives"
    assert len(s2.bullet_points) == 5
    assert s2.layout_name == "Title and Content"
    assert s2.bullet_points[0].startswith("Strategic Pillar 1:")

    s3 = fitted_plan.slides[2]
    assert s3.title == "Strategic Initiatives (Cont.)"
    assert len(s3.bullet_points) == 5
    assert s3.layout_name == "Title and Content"
    assert s3.bullet_points[0].startswith("Strategic Pillar 6:")

    s4 = fitted_plan.slides[3]
    assert s4.title == "Strategic Initiatives (Cont.)"
    assert len(s4.bullet_points) == 4
    assert s4.layout_name == "Title and Content"
    assert s4.bullet_points[0].startswith("Strategic Pillar 11:")

    # Verify all 14 bullets preserved in order
    all_split_bullets = s2.bullet_points + s3.bullet_points + s4.bullet_points
    assert all_split_bullets == bullets_14

    # Final slide preserved
    s5 = fitted_plan.slides[4]
    assert s5.title == "Closing Notes"
    assert len(s5.bullet_points) == 1


def test_content_fitter_e2e_document_and_presentation_generation(
    sample_docx_template: Path,
    sample_pptx_template: Path,
    tmp_path: Path
):
    """
    R3.3 & R3.6: End-to-end generation of fitted document and presentation plans,
    confirming zero crashes, accurate formatting, and style hash match.
    """
    # 1. DOCX with long text fitting
    analyzer_docx = DocxAnalyzer()
    spec_docx = analyzer_docx.analyze(str(sample_docx_template))
    engine_docx = DocxEngine()
    locked_doc = engine_docx.load_template(str(sample_docx_template), spec_docx)

    long_text = " ".join(["PreserveInvariants" for _ in range(400)])
    doc_plan = DocumentPlan(
        title="Fitted Long Document",
        sections=[
            DocumentSection(
                title="1. Fitted Section",
                heading_style="Heading 1",
                paragraphs=[long_text]
            )
        ]
    )
    doc_plan = ContentFitter.fit_document_plan(doc_plan)

    docx_out = tmp_path / "fitted_gen.docx"
    engine_docx.generate_from_plan(locked_doc, doc_plan, str(docx_out))
    assert docx_out.exists()

    validator = DiffValidator()
    docx_report = validator.validate(spec_docx, str(docx_out))
    assert docx_report.passed is True
    assert docx_report.hash_match is True

    # 2. PPTX with bullet fitting
    analyzer_pptx = PptxAnalyzer()
    spec_pptx = analyzer_pptx.analyze(str(sample_pptx_template))
    engine_pptx = PptxEngine()
    locked_prs = engine_pptx.load_template(str(sample_pptx_template), spec_pptx)

    prs_plan = PresentationPlan(
        presentation_title="Fitted Presentation",
        slides=[
            SlidePlan(
                slide_number=1,
                title="Many Bullets",
                layout_name=spec_pptx.available_layout_names[1],
                bullet_points=[f"Action {i}" for i in range(12)]
            )
        ]
    )
    prs_plan = ContentFitter.fit_presentation_plan(prs_plan)
    pptx_out = tmp_path / "fitted_gen.pptx"
    engine_pptx.generate_from_plan(locked_prs, prs_plan, str(pptx_out))
    assert pptx_out.exists()

    pptx_report = validator.validate(spec_pptx, str(pptx_out))
    assert pptx_report.passed is True
    assert pptx_report.hash_match is True


# ==============================================================================
# TEST SUITE 4: MULTI-ROW TABLE CLONING & EXPANSION
# ==============================================================================

def test_multi_row_table_cloning_and_expansion(docx_custom_table_template: Path, tmp_path: Path):
    """
    R3.4: Test table cloning with large datasets (15+ rows), verifying cell borders,
    background shading (w:shd), column counts, and style hash invariance.
    """
    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(docx_custom_table_template))
    engine = DocxEngine()
    locked_doc = engine.load_template(str(docx_custom_table_template), spec)

    # 20 Data Rows with 3 columns each
    large_dataset = [
        [f"Service Microservice {i+1:02d}", "Online" if i % 2 == 0 else "Degraded", f"{1000 + i * 250} ops/sec"]
        for i in range(20)
    ]

    plan = DocumentPlan(
        title="High Scale Table Expansion Report",
        sections=[
            DocumentSection(
                title="1. Infrastructure Performance Benchmarks",
                heading_style="Heading 1",
                paragraphs=["Below is the expanded table containing 20 microservice benchmark records:"],
                table_data=TableData(
                    title="Microservice Cluster Telemetry",
                    headers=["Service Microservice", "Health Status", "Query Rate"],
                    rows=large_dataset,
                    source_table_index=0
                )
            )
        ],
        conclusion="All 20 rows expanded with template table XML preservation."
    )

    output_path = tmp_path / "expanded_table_output.docx"
    engine.generate_from_plan(locked_doc, plan, str(output_path))

    assert output_path.exists()

    gen_doc = Document(str(output_path))
    assert len(gen_doc.tables) == 1
    table = gen_doc.tables[0]

    # Total rows = 1 header + 20 data = 21 rows
    assert len(table.rows) == 21
    assert len(table.columns) == 3

    # Check header row content
    assert table.cell(0, 0).text == "Service Microservice"
    assert table.cell(0, 1).text == "Health Status"
    assert table.cell(0, 2).text == "Query Rate"

    # Check first and last data rows
    assert table.cell(1, 0).text == "Service Microservice 01"
    assert table.cell(1, 1).text == "Online"
    assert table.cell(20, 0).text == "Service Microservice 20"
    assert table.cell(20, 1).text == "Degraded"

    # Verify XML formatting preservation: Header cell should contain w:shd fill="003366"
    h_cell_xml = table.cell(0, 0)._tc.xml
    assert "w:shd" in h_cell_xml
    assert "003366" in h_cell_xml

    # Verify Data cell inherited w:shd fill="F0F4F8"
    d_cell_xml = table.cell(15, 0)._tc.xml
    assert "w:shd" in d_cell_xml
    assert "F0F4F8" in d_cell_xml

    # Structural Hash validation
    validator = DiffValidator()
    report = validator.validate(spec, str(output_path))
    assert report.passed is True
    assert report.hash_match is True
    assert report.margin_drift_detected is False


# ==============================================================================
# TEST SUITE 5: RAPID CONSECUTIVE CALLS & CONCURRENCY STRESS
# ==============================================================================

def test_concurrency_rapid_consecutive_generation_stress(
    sample_docx_template: Path,
    sample_pptx_template: Path,
    tmp_path: Path
):
    """
    R3.5: Execute 12 rapid concurrent generation cycles across DOCX and PPTX,
    verifying thread safety, non-colliding temp files, and zero hash drift.
    """
    analyzer_docx = DocxAnalyzer()
    spec_docx = analyzer_docx.analyze(str(sample_docx_template))

    analyzer_pptx = PptxAnalyzer()
    spec_pptx = analyzer_pptx.analyze(str(sample_pptx_template))

    engine_docx = DocxEngine()
    engine_pptx = PptxEngine()
    hasher = StyleHasher()

    def run_docx_worker(worker_id: int) -> dict:
        locked_doc = engine_docx.load_template(str(sample_docx_template), spec_docx)
        plan = DocumentPlan(
            title=f"Concurrent DOCX Batch {worker_id}",
            sections=[
                DocumentSection(
                    title=f"Section {worker_id}",
                    heading_style="Heading 1",
                    paragraphs=[f"Thread safe concurrent paragraph for worker {worker_id}"],
                    bullets=[f"Thread bullet {worker_id}.1", f"Thread bullet {worker_id}.2"],
                    table_data=TableData(
                        headers=["Thread ID", "Status"],
                        rows=[[str(worker_id), "Active"], [f"{worker_id}-sub", "Completed"]]
                    )
                )
            ]
        )
        out_file = tmp_path / f"concurrent_docx_{worker_id}.docx"
        engine_docx.generate_from_plan(locked_doc, plan, str(out_file))

        is_match, orig_h, gen_h, diffs = hasher.compare_hashes(str(sample_docx_template), str(out_file))
        return {
            "worker_id": worker_id,
            "type": "docx",
            "exists": out_file.exists(),
            "size": out_file.stat().st_size if out_file.exists() else 0,
            "hash_match": is_match,
            "diffs": diffs
        }

    def run_pptx_worker(worker_id: int) -> dict:
        locked_prs = engine_pptx.load_template(str(sample_pptx_template), spec_pptx)
        plan = PresentationPlan(
            presentation_title=f"Concurrent PPTX Batch {worker_id}",
            slides=[
                SlidePlan(
                    slide_number=1,
                    title=f"Concurrent Slide {worker_id}",
                    layout_name=spec_pptx.available_layout_names[0]
                ),
                SlidePlan(
                    slide_number=2,
                    title=f"Concurrent Data {worker_id}",
                    layout_name=spec_pptx.available_layout_names[1],
                    bullet_points=[f"Worker {worker_id} point A", f"Worker {worker_id} point B"]
                )
            ]
        )
        out_file = tmp_path / f"concurrent_pptx_{worker_id}.pptx"
        engine_pptx.generate_from_plan(locked_prs, plan, str(out_file))

        is_match, orig_h, gen_h, diffs = hasher.compare_hashes(str(sample_pptx_template), str(out_file))
        return {
            "worker_id": worker_id,
            "type": "pptx",
            "exists": out_file.exists(),
            "size": out_file.stat().st_size if out_file.exists() else 0,
            "hash_match": is_match,
            "diffs": diffs
        }

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        # Dispatch 6 DOCX and 6 PPTX workers simultaneously
        for i in range(6):
            futures.append(executor.submit(run_docx_worker, i))
        for i in range(6):
            futures.append(executor.submit(run_pptx_worker, i + 100))

        for f in futures:
            results.append(f.result())

    assert len(results) == 12
    for r in results:
        assert r["exists"] is True, f"Worker {r['worker_id']} failed to create file"
        assert r["size"] > 0, f"Worker {r['worker_id']} output is empty"
        assert r["hash_match"] is True, f"Worker {r['worker_id']} suffered style hash drift: {r['diffs']}"


# ==============================================================================
# TEST SUITE 6: STRUCTURAL HASH DIFF COMPARISON & DRIFT DETECTION
# ==============================================================================

def test_structural_hash_diff_detects_deliberate_margin_drift(sample_docx_template: Path, tmp_path: Path):
    """
    R3.6: Verify DiffValidator and StyleHasher genuinely detect intentional
    page margin modifications (anti-false-positive validation).
    """
    # Create modified DOCX with 3.0 inch margins instead of 1.0 inch
    mutated_doc_path = tmp_path / "mutated_margins.docx"
    doc = Document(str(sample_docx_template))
    sec = doc.sections[0]
    sec.top_margin = Inches(3.0)
    sec.left_margin = Inches(3.0)
    doc.save(str(mutated_doc_path))

    analyzer = DocxAnalyzer()
    orig_spec = analyzer.analyze(str(sample_docx_template))

    validator = DiffValidator()
    report = validator.validate(orig_spec, str(mutated_doc_path))

    assert report.passed is False
    assert report.hash_match is False
    assert report.margin_drift_detected is True
    assert len(report.issues) > 0


def test_structural_hash_diff_detects_deliberate_slide_dimension_drift(sample_pptx_template: Path, tmp_path: Path):
    """
    R3.6: Verify DiffValidator genuinely detects intentional slide dimension changes
    (e.g., altering width from 13.333 to 8.0 inches).
    """
    mutated_prs_path = tmp_path / "mutated_dimensions.pptx"
    prs = Presentation(str(sample_pptx_template))
    prs.slide_width = PptxInches(8.0)
    prs.slide_height = PptxInches(6.0)
    prs.save(str(mutated_prs_path))

    analyzer = PptxAnalyzer()
    orig_spec = analyzer.analyze(str(sample_pptx_template))

    validator = DiffValidator()
    report = validator.validate(orig_spec, str(mutated_prs_path))

    assert report.passed is False
    assert report.hash_match is False
    assert report.layout_drift_detected is True
    assert any("Slide dimension drift" in issue for issue in report.issues)
