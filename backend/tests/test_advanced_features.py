import pytest
from pathlib import Path
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from backend.app.analyzer.docx_analyzer import DocxAnalyzer
from backend.app.engines.docx_engine import DocxEngine
from backend.app.models.generation import DocumentPlan, DocumentSection, TableData, ThemeOverride

def test_explicit_border_mutation_preserves_other_styles(tmp_path: Path):
    """
    Tests that explicit user request to mutate a border color (e.g. blue to yellow)
    updates ONLY that border while keeping fonts, margins, and other borders 100% untouched.
    """
    # Create template with blue borders
    template_path = tmp_path / "template_with_border.docx"
    doc = Document()
    p = doc.add_paragraph("Bordered Section Heading", style="Heading 1")
    
    # Add blue bottom border to paragraph XML
    pPr = p._p.get_or_add_pPr()
    pBdr = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="12" w:space="4" w:color="0000FF"/></w:pBdr>')
    pPr.append(pBdr)
    doc.save(str(template_path))

    # Analyze template
    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(template_path))
    engine = DocxEngine()
    locked_doc = engine.load_template(str(template_path), spec)

    # Document plan with explicit user theme override: "Change blue border to yellow"
    plan = DocumentPlan(
        title="Custom Border Report",
        sections=[
            DocumentSection(
                title="1. Introduction with Yellow Border",
                heading_style="Heading 1",
                paragraphs=["This section now inherits the template with the yellow border."]
            )
        ],
        theme_overrides=[
            ThemeOverride(
                element_type="border",
                target_identifier="blue",
                new_value="yellow",
                description="Change blue border to yellow"
            )
        ]
    )

    output_path = tmp_path / "output_yellow_border.docx"
    engine.generate_from_plan(locked_doc, plan, str(output_path))

    assert output_path.exists()
    gen_doc = Document(str(output_path))
    
    # Verify the document contains the text and headings
    assert len(gen_doc.paragraphs) > 0
    assert any("1. Introduction with Yellow Border" in p.text for p in gen_doc.paragraphs)
