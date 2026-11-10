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
    """Fixture providing the seminar template path (or a local copy)."""
    if UPLOADED_SEMINAR_TEMPLATE.exists():
        return UPLOADED_SEMINAR_TEMPLATE
    pytest.skip("Uploaded seminar report template not available.")


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
