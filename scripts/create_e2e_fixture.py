"""Create a minimal real DOCX template for the Playwright backend integration test."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches


def main() -> None:
    target = Path("tests/.tmp/e2e-template.docx")
    target.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    header = section.header.paragraphs[0]
    header.text = "DOCGURU E2E TEMPLATE HEADER"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer = section.footer.paragraphs[0]
    footer.text = "DOCGURU E2E TEMPLATE FOOTER"
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_heading("Integration Test Template", level=1)
    document.add_paragraph(
        "A small template used to validate the full generation and download flow."
    )
    table = document.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.cell(0, 0).text = "Property"
    table.cell(0, 1).text = "Expected"
    table.cell(1, 0).text = "Template styles"
    table.cell(1, 1).text = "Preserved"
    document.save(target)


if __name__ == "__main__":
    main()
