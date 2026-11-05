from pathlib import Path

from docx import Document

from backend.app.analyzer.docx_analyzer import DocxAnalyzer
from backend.app.engines.docx_engine import DocxEngine
from backend.app.models.generation import DocumentPlan, DocumentSection, ResearchSource, TableData


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
                    "In 2016, it defeated Lee Sedol in a five-game match.",
                ],
                bullets=[
                    "Combines deep neural networks with MCTS",
                    "Trained via supervised learning from human expert games",
                ],
            ),
            DocumentSection(
                title="2. Performance Metrics",
                heading_style="Heading 1",
                paragraphs=["Below is the comparison table:"],
                table_data=TableData(
                    title="Table: Benchmark Results",
                    headers=["Evaluation Metric", "Baseline Score", "AlphaGo Master"],
                    rows=[["Elo Rating", "3000", "3750"], ["Win Rate vs Fan Hui", "0%", "100%"]],
                    source_table_index=0,
                ),
            ),
        ],
        conclusion="AlphaGo demonstrated the power of deep reinforcement learning.",
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


def test_research_citations_and_references_render_from_returned_metadata(
    sample_docx_template: Path, tmp_path: Path
):
    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(sample_docx_template))
    engine = DocxEngine()
    locked_doc = engine.load_template(str(sample_docx_template), spec)
    plan = DocumentPlan(
        title="Climate Adaptation",
        sections=[
            DocumentSection(
                title="Planning",
                heading_style="Heading 1",
                paragraphs=[
                    "Climate adaptation planning should assess local needs and constraints."
                ],
                citations=["S1"],
            )
        ],
        conclusion="Use the stated goals to guide next steps.",
        research_sources=[
            ResearchSource(
                id="S1",
                title="Climate Adaptation Guidance",
                url="https://example.org/climate-adaptation",
                published_date="2025-01-02",
            ),
            ResearchSource(
                id="S2",
                title="Uncited Source",
                url="https://example.org/unused",
            ),
        ],
    )
    output_path = tmp_path / "cited_document.docx"

    engine.generate_from_plan(locked_doc, plan, str(output_path), template_mode="replace_body")

    generated = Document(str(output_path))
    text = "\n".join(paragraph.text for paragraph in generated.paragraphs)
    assert "[1]" in text
    assert "References" in text
    assert "[1] Climate Adaptation Guidance. Published: 2025-01-02." in text
    assert "https://example.org/climate-adaptation" in text
    assert "Uncited Source" not in text


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
                bullets=["Bullet item 1", "Bullet item 2"],
            )
        ],
        conclusion="Successful generation on minimal template.",
    )

    output_file = tmp_path / "generated_minimal.docx"
    engine.generate_from_plan(locked_doc, plan, str(output_file))

    assert output_file.exists()
    gen_doc = Document(str(output_file))
    full_text = " ".join([p.text for p in gen_doc.paragraphs])
    assert "Section Without Heading Style" in full_text
    assert "This paragraph should be rendered without crashing." in full_text


def test_docx_table_column_count_changes_and_large_table(tmp_path: Path):
    """Verify table cloning when new data has fewer/more columns and large 25-row datasets."""
    tmpl_path = tmp_path / "table_template.docx"
    doc = Document()
    tbl = doc.add_table(rows=2, cols=3)
    tbl.cell(0, 0).text = "H1"
    tbl.cell(0, 1).text = "H2"
    tbl.cell(0, 2).text = "H3"
    tbl.cell(1, 0).text = "D1"
    tbl.cell(1, 1).text = "D2"
    tbl.cell(1, 2).text = "D3"
    doc.save(str(tmpl_path))

    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(tmpl_path))
    engine = DocxEngine()
    locked = engine.load_template(str(tmpl_path), spec)

    # 1. Fewer columns (2 cols vs template 3 cols)
    # 2. More columns (4 cols vs template 3 cols)
    # 3. Large table (25 rows)
    large_rows = [[f"R{i}C1", f"R{i}C2", f"R{i}C3", f"R{i}C4"] for i in range(25)]
    plan = DocumentPlan(
        title="Table Scaling Report",
        sections=[
            DocumentSection(
                title="1. Shrunk Columns",
                heading_style="Heading 1",
                paragraphs=["Table with fewer columns:"],
                table_data=TableData(
                    headers=["Col A", "Col B"],
                    rows=[["Val A1", "Val B1"], ["Val A2", "Val B2"]],
                    source_table_index=0,
                ),
            ),
            DocumentSection(
                title="2. Expanded & Large Table",
                heading_style="Heading 1",
                paragraphs=["Table with 4 columns and 25 rows:"],
                table_data=TableData(
                    headers=["Metric", "Q1", "Q2", "Q3"],
                    rows=large_rows,
                    source_table_index=0,
                ),
            ),
        ],
    )

    out_path = tmp_path / "table_scaling_out.docx"
    engine.generate_from_plan(locked, plan, str(out_path))

    gen_doc = Document(str(out_path))
    assert len(gen_doc.tables) == 2

    # Check first table has 2 columns in body
    t1 = gen_doc.tables[0]
    assert len(t1.columns) >= 2
    assert t1.cell(0, 0).text == "Col A"

    # Check second table has 26 rows (1 header + 25 rows)
    t2 = gen_doc.tables[1]
    assert len(t2.rows) == 26
    assert t2.cell(25, 0).text == "R24C1"


def test_docx_adjacent_tables_and_empty_paragraphs(tmp_path: Path):
    """Verify adjacent tables and whitespace/empty paragraphs do not break generation."""
    tmpl_path = tmp_path / "adjacent_template.docx"
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "A"
    t.cell(0, 1).text = "B"
    t.cell(1, 0).text = "1"
    t.cell(1, 1).text = "2"
    doc.save(str(tmpl_path))

    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(tmpl_path))
    engine = DocxEngine()
    locked = engine.load_template(str(tmpl_path), spec)

    plan = DocumentPlan(
        title="Adjacent Tables",
        sections=[
            DocumentSection(
                title="Section 1",
                heading_style="Heading 1",
                paragraphs=["", "   ", "Valid introductory text.", ""],
                table_data=TableData(
                    headers=["X", "Y"],
                    rows=[["10", "20"]],
                ),
            ),
            DocumentSection(
                title="Section 2",
                heading_style="Heading 1",
                paragraphs=["Immediately following table:"],
                table_data=TableData(
                    headers=["Alpha", "Beta"],
                    rows=[["A", "B"]],
                ),
            ),
        ],
    )

    out_path = tmp_path / "adjacent_out.docx"
    engine.generate_from_plan(locked, plan, str(out_path))

    gen_doc = Document(str(out_path))
    assert len(gen_doc.tables) == 2
    assert gen_doc.tables[0].cell(1, 0).text == "10"
    assert gen_doc.tables[1].cell(1, 0).text == "A"


def test_docx_merged_table_cells_preservation(tmp_path: Path):
    """Verify table with merged cells in template clones safely."""
    tmpl_path = tmp_path / "merged_tbl_template.docx"
    doc = Document()
    t = doc.add_table(rows=3, cols=3)
    # Merge row 0 cell 0 and cell 1
    t.cell(0, 0).merge(t.cell(0, 1))
    t.cell(0, 0).text = "Merged Header"
    t.cell(0, 2).text = "Header 3"
    t.cell(1, 0).text = "R1C0"
    t.cell(1, 1).text = "R1C1"
    t.cell(1, 2).text = "R1C2"
    doc.save(str(tmpl_path))

    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(tmpl_path))
    engine = DocxEngine()
    locked = engine.load_template(str(tmpl_path), spec)

    plan = DocumentPlan(
        title="Merged Table Plan",
        sections=[
            DocumentSection(
                title="Merged Table Section",
                heading_style="Heading 1",
                paragraphs=["Populating merged structure:"],
                table_data=TableData(
                    headers=["Group Header", "Group Cont", "Col 3"],
                    rows=[["Data A", "Data B", "Data C"], ["Data D", "Data E", "Data F"]],
                    source_table_index=0,
                ),
            )
        ],
    )

    out_path = tmp_path / "merged_out.docx"
    engine.generate_from_plan(locked, plan, str(out_path))

    gen_doc = Document(str(out_path))
    assert len(gen_doc.tables) == 1
    assert "Data A" in gen_doc.tables[0].cell(1, 0).text

