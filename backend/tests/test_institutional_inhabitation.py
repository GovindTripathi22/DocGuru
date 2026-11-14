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


def test_non_institutional_rule_mode_enforces_embedded_rules_and_strips_instructions(tmp_path):
    """Test that document rule mode extracts rules from a plain docx, enforces them on styles/page, and removes instructions."""
    doc = docx.Document()
    doc.add_paragraph(
        "Formatting Guideline: Font Style Arial, Heading 16 pt uppercase left aligned, body 11 pt double spacing (2.0), left margin 1.5 inches, A4 page size."
    )
    doc.add_paragraph("Required Sections: Executive Overview, Technical Architecture, Conclusion")
    doc.add_paragraph("Regular placeholder body text.")
    tpl_path = tmp_path / "rules_only_template.docx"
    doc.save(str(tpl_path))

    analyzer = TemplateAnalyzer()
    spec = analyzer.analyze(str(tpl_path))
    assert spec.has_embedded_rules is True
    assert spec.parsed_typography_rules.get("heading1", {}).get("size_pt") == 16.0
    assert spec.parsed_structural_rules.get("page_size") == "A4"

    locked_doc = LockedTemplate(docx.Document(str(tpl_path)), str(tpl_path), spec)
    plan = DocumentPlan(
        title="Platform Security Architecture",
        sections=[
            DocumentSection(title="Executive Overview", paragraphs=["Security baseline overview."]),
            DocumentSection(title="Technical Architecture", paragraphs=["Zero-trust control plane."]),
        ],
        conclusion="All controls verified.",
    )
    out_path = tmp_path / "ruled_output.docx"
    DocxEngine().generate_from_plan(locked_doc=locked_doc, plan=plan, output_path=str(out_path), rule_mode="document")

    gen = docx.Document(str(out_path))
    full_text = "\n".join(p.text for p in gen.paragraphs)
    assert "Formatting Guideline:" not in full_text
    assert "Required Sections:" not in full_text
    assert "EXECUTIVE OVERVIEW" in full_text
    assert round(gen.sections[0].left_margin.inches, 2) == 1.5


def test_custom_rule_mode_overrides_template_without_rules(tmp_path):
    """Test that rule_mode='custom' applies CustomRulePreferences when a template has no embedded rules."""
    from backend.app.models.generation import CustomRulePreferences

    doc = docx.Document()
    doc.add_paragraph("Sample Heading", style="Heading 1")
    doc.add_paragraph("Sample body content with no written formatting instructions.")
    tpl_path = tmp_path / "plain_no_rules.docx"
    doc.save(str(tpl_path))

    spec = TemplateAnalyzer().analyze(str(tpl_path))
    assert spec.has_embedded_rules is False

    locked_doc = LockedTemplate(docx.Document(str(tpl_path)), str(tpl_path), spec)
    plan = DocumentPlan(
        title="Cloud Cost Governance",
        sections=[DocumentSection(title="Cost Allocation", paragraphs=["Tagging and budget guardrails."])],
    )
    prefs = CustomRulePreferences(
        font_name="Calibri",
        heading1_size_pt=18.0,
        body_size_pt=11.0,
        line_spacing=1.5,
        body_alignment="justify",
        heading1_alignment="center",
        heading1_case="uppercase",
        margin_inches=0.75,
        page_size="A4",
    )
    out_path = tmp_path / "custom_output.docx"
    DocxEngine().generate_from_plan(
        locked_doc=locked_doc,
        plan=plan,
        output_path=str(out_path),
        rule_mode="custom",
        custom_rules=prefs,
    )

    gen = docx.Document(str(out_path))
    assert "COST ALLOCATION" in "\n".join(p.text for p in gen.paragraphs)
    assert round(gen.sections[0].top_margin.inches, 2) == 0.75
    assert gen.styles["Normal"].font.name == "Calibri"

