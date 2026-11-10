"""Unit and integration tests for academic / institutional template inhabitation and rule enforcement."""

from pathlib import Path
import docx
from docx.shared import Pt
import pytest

from backend.app.analyzer.template_analyzer import TemplateAnalyzer
from backend.app.engines.docx_engine import DocxEngine
from backend.app.engines.style_lock import LockedTemplate
from backend.app.models.generation import DocumentPlan, DocumentSection, ResearchSource
from backend.app.validation.diff_validator import DiffValidator

UPLOADED_SEMINAR_TEMPLATE = Path(
    r"C:\Users\USER\.gemini\antigravity\brain\a7a3b296-4475-41ee-b829-919b085c20d2\.user_uploaded\media_1794214019181_bebe1687.docx"
)


@pytest.fixture
def seminar_template_path(tmp_path) -> Path:
    """Fixture providing the seminar template path (or building a realistic seminar report template)."""
    if UPLOADED_SEMINAR_TEMPLATE.exists():
        return UPLOADED_SEMINAR_TEMPLATE

    doc = docx.Document()
    # Cover Page
    doc.add_paragraph("A SEMINAR REPORT ON")
    doc.add_paragraph("<Title>")
    doc.add_paragraph("Formatting Tips: Font Style: Times New Roman(Bold), 14 Pt, Capital, Center Aligned")
    doc.add_paragraph("SUBMITTED TO THE SAVITRIBAI PHULE PUNE UNIVERSITY")
    doc.add_paragraph("SUBMITTED BY")
    doc.add_paragraph("Name of Student")
    doc.add_paragraph("Roll No: 4101")
    doc.add_paragraph("UNDER THE GUIDANCE OF")
    doc.add_paragraph("Prof. Guide Name")
    doc.add_paragraph("DEPARTMENT OF COMPUTER ENGINEERING")
    doc.add_paragraph("Academic Year 2023-24")

    # Certificate
    doc.add_paragraph("CERTIFICATE", style="Heading 1")
    doc.add_paragraph(
        'This is to certify that the seminar report entitled "<Title>" submitted by '
        "Name of Student is a bonafide work carried out under the supervision of Prof. Guide Name."
    )

    # Acknowledgement
    doc.add_paragraph("ACKNOWLEDGEMENT", style="Heading 1")
    doc.add_paragraph(
        'I express my sincere gratitude to my guide Prof. Guide Name for constant guidance on "<Title>".'
    )
    doc.add_paragraph("Name of Student")

    # Abstract
    doc.add_paragraph("ABSTRACT", style="Heading 1")
    doc.add_paragraph("Formatting Rule: Abstract should be 150-200 words in Times New Roman, 12 Pt, 1.5 line spacing.")
    doc.add_paragraph("Sample placeholder abstract text that will be replaced during generation.")

    # Table of Contents
    doc.add_paragraph("TABLE OF CONTENT", style="Heading 1")
    toc_table = doc.add_table(rows=3, cols=3)
    toc_table.cell(0, 0).text = "Chapter"
    toc_table.cell(0, 1).text = "Title"
    toc_table.cell(0, 2).text = "Page No"
    toc_table.cell(1, 0).text = "1"
    toc_table.cell(1, 1).text = "Introduction"
    toc_table.cell(1, 2).text = "1"
    toc_table.cell(2, 0).text = "2"
    toc_table.cell(2, 1).text = "Literature Survey"
    toc_table.cell(2, 2).text = "5"

    # Body Anchor (Chapter 1) + Sample Chapters & Guidelines to be replaced in-place
    doc.add_paragraph("CHAPTER 1: INTRODUCTION", style="Heading 1")
    doc.add_paragraph("Note: Chapter 1 will start from this page and will be introduction part.")
    doc.add_paragraph("Font Style: Times New Roman(Bold), 14 Pt, Capital, Center Aligned for Chapter Headings.")
    doc.add_paragraph("Sub Heading 2 Formatting Tips: 12 Pt Bold Left Aligned.")
    doc.add_paragraph("For giving long space please do not use space bar, use tab key instead.")
    doc.add_paragraph("Block Diagram of Honeypot System")
    for idx in range(2, 7):
        doc.add_paragraph(f"CHAPTER {idx}: SAMPLE CHAPTER {idx}", style="Heading 1")
        for p_i in range(25):
            doc.add_paragraph(
                f"Dummy sample chapter {idx} paragraph {p_i} that must be purged and replaced in-place."
            )

    out_file = tmp_path / "synthetic_seminar_template.docx"
    doc.save(str(out_file))
    return out_file


def test_docx_analyzer_detects_institutional_template(seminar_template_path):
    """Test that DocxAnalyzer correctly flags an academic template, extracts rules, and finds the body anchor."""
    analyzer = TemplateAnalyzer()
    spec = analyzer.analyze(str(seminar_template_path))

    assert spec.is_institutional_template is True
    assert spec.body_anchor_index is not None
    assert spec.body_anchor_index > 0
    assert "heading1" in spec.parsed_typography_rules
    assert spec.parsed_typography_rules["heading1"]["size_pt"] == 14.0
    assert spec.parsed_typography_rules["heading1"]["font_name"] == "Times New Roman"
    assert spec.parsed_typography_rules["body"]["alignment"] == "justify"


def test_docx_engine_inhabits_seminar_template_without_second_doc(seminar_template_path, tmp_path):
    """
    Test that DocxEngine:
    1. Inhabits Cover, Certificate, and Acknowledgement with user metadata.
    2. Inhabits Abstract and strips abstract guidelines.
    3. Purges all dummy guideline/tip paragraphs and dummy honeypot diagrams.
    4. Generates body chapters starting directly at Chapter 1 (NOT appended at end).
    5. Passes DiffValidator with status 'passed' and 0 drift issues.
    """
    analyzer = TemplateAnalyzer()
    spec = analyzer.analyze(str(seminar_template_path))

    title = "DECENTRALIZED AUTONOMOUS AGENTS IN IOT"
    author = "Devon Vance"
    guide = "Dr. S. K. Wankhade"
    abstract_text = (
        "This seminar report explores decentralized autonomous agents in IoT edge environments. "
        "We evaluate consensus mechanisms, latency metrics, and self-healing resilience."
    )

    plan = DocumentPlan(
        title=title,
        author=author,
        guide=guide,
        abstract=abstract_text,
        sections=[
            DocumentSection(
                title="Introduction",
                paragraphs=[
                    "Decentralized autonomous agents represent a transformative architecture in IoT networks. Edge-based intelligent agents coordinate tasks without round-trip dependencies on centralized cloud services.",
                ],
                subsections=[
                    DocumentSection(
                        title="Problem Statement and Motivation",
                        paragraphs=[
                            "Intermittent edge connectivity necessitates distributed local consensus and autonomous decision recovery.",
                        ],
                    )
                ],
            ),
            DocumentSection(
                title="Literature Review and Theoretical Foundations",
                paragraphs=[
                    "Early distributed consensus protocols laid the groundwork for state replication across Byzantine edge nodes.",
                ],
            ),
            DocumentSection(
                title="System Architecture and Methodology",
                paragraphs=[
                    "The system architecture incorporates lightweight peer agents operating over gossip communication topologies.",
                ],
            ),
            DocumentSection(
                title="Results and Performance Analysis",
                paragraphs=[
                    "Empirical tests across edge clusters demonstrated a 40% reduction in response latency and zero message dropping.",
                ],
            ),
        ],
        conclusion="In conclusion, decentralized autonomous agents provide robust resilience for edge IoT networks.",
        research_sources=[
            ResearchSource(
                id="src-1",
                title="Consensus in Edge IoT",
                url="https://doi.org/10.1109/IOT.2025.101",
                published_date="2025",
            )
        ],
    )

    output_path = tmp_path / "generated_seminar_report.docx"
    doc = docx.Document(str(seminar_template_path))
    locked_doc = LockedTemplate(doc, str(seminar_template_path), spec)
    engine = DocxEngine()

    result_path = engine.generate_from_plan(
        locked_doc=locked_doc,
        plan=plan,
        output_path=str(output_path),
    )

    assert Path(result_path).exists()
    gen_doc = docx.Document(result_path)

    # 1. Check Front Matter Inhabitation
    full_text = "\n".join(p.text for p in gen_doc.paragraphs)
    assert title in full_text
    assert author in full_text
    assert guide in full_text

    # Cover page checks
    assert any(title in p.text for p in gen_doc.paragraphs[:10])
    assert any(author in p.text for p in gen_doc.paragraphs[:10])

    # 2. Check Guideline Removal
    # Rule instructions, tips, and dummy block diagrams must NOT be present
    forbidden_snippets = [
        "Font Style: Times New Roman(Bold)",
        "Sub Heading 2 Formatting Tips:",
        "For giving long space please do not use space bar",
        "Block Diagram of Honeypot System",
        "Note: Chapter 1 will start from this page",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in full_text, f"Guideline snippet '{snippet}' was not purged from final doc!"

    # 3. Check True Body Inhabitation (not appended after 240+ paragraphs)
    # The clean document should have significantly fewer paragraphs than the bloated template + appended content
    assert len(gen_doc.paragraphs) < 180, f"Expected <180 paragraphs, found {len(gen_doc.paragraphs)} (likely appended second doc)!"

    # Check that Chapter 1 starts near the body anchor
    chapter1_found_early = any(
        "CHAPTER 1: INTRODUCTION" in p.text.upper() for p in gen_doc.paragraphs[:125]
    )
    assert chapter1_found_early, "Chapter 1 was not found in the proper body position!"

    # 4. Check DiffValidator Invariance
    validator = DiffValidator()
    report = validator.validate(spec, result_path, original_file_path=str(seminar_template_path))
    assert report.passed is True, f"DiffValidator failed with issues: {report.issues}"
    assert report.status == "passed"


def test_repetition_loop_breaker_and_markdown_table_normalization():
    """Test deduplicate_repetitive_text, extract_markdown_table, and is_stray_placeholder_or_schema_key."""
    from backend.app.planning.normalize import (
        deduplicate_repetitive_text,
        extract_markdown_table,
        is_stray_placeholder_or_schema_key,
        normalize_plan,
    )

    # 1. Test deduplicate_repetitive_text with degenerate repeating loops
    repeated_title = "Table 1: AlphaGo vs. DeepMind's Other Systems\n" * 50
    cleaned_repetition = deduplicate_repetitive_text(repeated_title)
    assert cleaned_repetition.count("Table 1: AlphaGo") <= 2
    assert len(cleaned_repetition) < len(repeated_title)

    # Inline repeated sentence loop
    looping_sentence = (
        "AlphaGo defeated Lee Sedol. " * 20
    )
    cleaned_inline = deduplicate_repetitive_text(looping_sentence)
    assert cleaned_inline.count("AlphaGo defeated Lee Sedol.") <= 2

    # 2. Test extract_markdown_table parses pipe-formatted table and strips it from paragraphs
    paragraphs_with_table = [
        "In this chapter we analyze performance trade-offs.",
        "| Feature | AlphaGo | Other Systems | Notes |\n|---|---|---|---|\n| Search | MCTS | Minimax | Deep RL |\n| GPU Clusters | 48 | 8 | Scaled |",
        "Overall the results show clear superiority.",
    ]
    extracted_tbl, clean_paras = extract_markdown_table(paragraphs_with_table)
    assert extracted_tbl is not None
    assert extracted_tbl["headers"] == ["Feature", "AlphaGo", "Other Systems", "Notes"]
    assert len(extracted_tbl["rows"]) == 2
    assert extracted_tbl["rows"][0] == ["Search", "MCTS", "Minimax", "Deep RL"]
    assert len(clean_paras) == 2
    assert "Search | MCTS" not in clean_paras[0] and "Search | MCTS" not in clean_paras[1]

    # 3. Test stray schema keys and guideline callouts are caught
    assert is_stray_placeholder_or_schema_key("bullet_points") is True
    assert is_stray_placeholder_or_schema_key("table_data") is True
    assert is_stray_placeholder_or_schema_key(": lowercase") is True
    assert is_stray_placeholder_or_schema_key(": Uppercase tent") is True
    assert is_stray_placeholder_or_schema_key("[Seminar Topic]") is True
    assert is_stray_placeholder_or_schema_key("Valid paragraph introducing AlphaGo architecture.") is False

    # 4. Test normalize_plan extracts markdown table and purges stray artifacts
    raw_plan_dict = {
        "title": "AlphaGo Report",
        "sections": [
            {
                "title": "Architecture Overview",
                "paragraphs": [
                    ": lowercase",
                    "bullet_points",
                    "AlphaGo uses deep convolutional networks combined with tree search.",
                    "| Component | Architecture | Role |\n| Policy Net | 13-layer CNN | Move selection |\n| Value Net | 13-layer CNN | Position evaluation |",
                ],
                "bullets": ["Trained on KGS Go server", "Self-play reinforcement learning"],
            }
        ],
    }
    normalized = normalize_plan(raw_plan_dict)
    sec = normalized["sections"][0]
    assert sec.get("table_data") is not None
    assert sec["table_data"]["headers"] == ["Component", "Architecture", "Role"]
    assert len(sec["table_data"]["rows"]) == 2
    assert not any(": lowercase" in p for p in sec["paragraphs"])
    assert not any("bullet_points" in p for p in sec["paragraphs"])


def test_docx_engine_table_rendering_and_inhabitation(seminar_template_path, tmp_path):
    """Test DocxEngine table styling (borders, shading, captions) and table inclusion/exclusion."""
    from backend.app.models.generation import TableData

    analyzer = TemplateAnalyzer()
    spec = analyzer.analyze(str(seminar_template_path))

    plan_with_tables = DocumentPlan(
        title="ADVANCED AI ARCHITECTURES",
        author="Rohit Verma",
        guide="Dr. P. Sharma",
        abstract="Comparative analysis of deep reinforcement learning systems.",
        include_tables=True,
        sections=[
            DocumentSection(
                title="System Comparison",
                paragraphs=["Below is the comparative analysis of deep RL architectures."],
                table_data=TableData(
                    title="Table 1: Benchmark Comparison Across Reinforcement Learning Frameworks",
                    headers=["Framework", "Policy Type", "Throughput", "Convergence Time"],
                    rows=[
                        ["AlphaGo", "MCTS + Value Net", "12,000 pos/sec", "21 days"],
                        ["MuZero", "Model-Based RL", "18,500 pos/sec", "14 days"],
                        ["AlphaZero", "Self-Play RL", "15,000 pos/sec", "10 days"],
                    ],
                ),
            )
        ],
    )

    doc = docx.Document(str(seminar_template_path))
    locked_doc = LockedTemplate(doc, str(seminar_template_path), spec)
    engine = DocxEngine()
    out_with_tables = tmp_path / "report_with_tables.docx"
    engine.generate_from_plan(locked_doc, plan_with_tables, str(out_with_tables))

    gen_doc = docx.Document(str(out_with_tables))
    # Assert table was rendered
    assert len(gen_doc.tables) >= 1
    # Check table content
    table_texts = [cell.text for tbl in gen_doc.tables for row in tbl.rows for cell in row.cells]
    assert "AlphaGo" in table_texts
    assert "MuZero" in table_texts
    assert "MCTS + Value Net" in table_texts

    # Check caption
    full_text = "\n".join(p.text for p in gen_doc.paragraphs)
    assert "Table 1: Benchmark Comparison" in full_text

    # Validate DiffValidator
    validator = DiffValidator()
    report = validator.validate(spec, str(out_with_tables), original_file_path=str(seminar_template_path))
    assert report.passed is True

    # Now verify plan with include_tables=False does not render tables
    plan_no_tables = DocumentPlan(
        title="ADVANCED AI ARCHITECTURES",
        author="Rohit Verma",
        guide="Dr. P. Sharma",
        abstract="Comparative analysis of deep reinforcement learning systems.",
        include_tables=False,
        sections=[
            DocumentSection(
                title="System Comparison",
                paragraphs=["Below is the narrative comparison."],
            )
        ],
    )
    doc_no_tables = docx.Document(str(seminar_template_path))
    locked_no_tables = LockedTemplate(doc_no_tables, str(seminar_template_path), spec)
    out_no_tables = tmp_path / "report_no_tables.docx"
    engine.generate_from_plan(locked_no_tables, plan_no_tables, str(out_no_tables))
    gen_doc_no_tables = docx.Document(str(out_no_tables))
    assert len(gen_doc_no_tables.tables) == 0

