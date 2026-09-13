import pytest
from pathlib import Path
from docx import Document
from backend.app.analyzer.docx_analyzer import DocxAnalyzer
from backend.app.engines.docx_engine import DocxEngine
from backend.app.models.generation import DocumentPlan, DocumentSection, TableData

def test_docx_load_and_spec_extraction(sample_docx_template: Path):
    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(sample_docx_template))

    assert spec.document_type == "docx"
    assert spec.page is not None
    assert spec.page.margins.top_pt == 72.0
    assert "Heading 1" in spec.available_heading_styles
    assert spec.header is not None
    assert spec.footer is not None
    assert len(spec.style_hash) > 0

def test_docx_template_content_replacement(sample_docx_template: Path, tmp_path: Path):
    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(sample_docx_template))
    engine = DocxEngine()

    locked_doc = engine.load_template(str(sample_docx_template), spec)

    plan = DocumentPlan(
        title="AlphaGo Architecture Report",
        target_audience="Research Scientists",
        sections=[
            DocumentSection(
                title="1. Introduction to AlphaGo",
                heading_style="Heading 1",
                paragraphs=[
                    "AlphaGo is a computer program that plays the board game Go.",
                    "In 2016, it defeated Lee Sedol in a five-game match."
                ],
                bullets=[
                    "Combines deep neural networks with MCTS",
                    "Trained via supervised learning from human expert games"
                ]
            ),
            DocumentSection(
                title="2. Performance Metrics",
                heading_style="Heading 1",
                paragraphs=["Below is the comparison table:"],
                table_data=TableData(
                    title="Table: Benchmark Results",
                    headers=["Evaluation Metric", "Baseline Score", "AlphaGo Master"],
                    rows=[
                        ["Elo Rating", "3000", "3750"],
                        ["Win Rate vs Fan Hui", "0%", "100%"]
                    ],
                    source_table_index=0
                )
            )
        ],
        conclusion="AlphaGo demonstrated the power of deep reinforcement learning."
    )

    output_file = tmp_path / "generated_alphago.docx"
    engine.generate_from_plan(locked_doc, plan, str(output_file))

    assert output_file.exists()

    # Verify generated document
    gen_doc = Document(str(output_file))
    
    # Check headers and footers preserved
    sec = gen_doc.sections[0]
    assert sec.header.paragraphs[0].text == "ORGANIZATIONAL TEMPLATE: CONFIDENTIAL RESEARCH REPORT"
    assert sec.footer.paragraphs[0].text == "Page 1 of Document — All Rights Reserved"

    # Check content replaced
    full_text = " ".join([p.text for p in gen_doc.paragraphs])
    assert "AlphaGo is a computer program" in full_text
    assert "1. Introduction to AlphaGo" in full_text
    assert "Combines deep neural networks" in full_text

    # Check table structure preserved
    assert len(gen_doc.tables) == 1
    table = gen_doc.tables[0]
    assert table.cell(0, 0).text == "Evaluation Metric"
    assert table.cell(1, 0).text == "Elo Rating"
    assert table.cell(1, 1).text == "3000"


def test_docx_generation_without_heading_styles(tmp_path: Path):
    """
    Verify that templates lacking built-in 'Heading 1' styles (e.g. minimal or custom docs)
    generate successfully without throwing 'no style with name Heading 1'.
    """
    # Create a minimal document with only a paragraph (no Heading 1 style)
    min_doc_path = tmp_path / "minimal_template.docx"
    doc = Document()
    doc.add_paragraph("Minimal template content")
    doc.save(str(min_doc_path))

    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(min_doc_path))

    engine = DocxEngine()
    locked_doc = engine.load_template(str(min_doc_path), spec)

    plan = DocumentPlan(
        title="Minimal Template Test Report",
        target_audience="General",
        sections=[
            DocumentSection(
                title="Section Without Heading Style",
                heading_style="Heading 1",  # User or planner requested Heading 1
                paragraphs=["This paragraph should be rendered without crashing."],
                bullets=["Bullet item 1", "Bullet item 2"]
            )
        ],
        conclusion="Successful generation on minimal template."
    )

    output_file = tmp_path / "generated_minimal.docx"
    engine.generate_from_plan(locked_doc, plan, str(output_file))

    assert output_file.exists()
    gen_doc = Document(str(output_file))
    full_text = " ".join([p.text for p in gen_doc.paragraphs])
    assert "Section Without Heading Style" in full_text
    assert "This paragraph should be rendered without crashing." in full_text

