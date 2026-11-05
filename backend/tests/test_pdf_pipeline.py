from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from docx import Document

from backend.app.analyzer.pdf_analyzer import PdfAnalyzer
from backend.app.engines.pdf_extractor import PdfExtractor
from backend.app.engines.pdf_reference import PdfReferenceBuilder
from backend.app.models.template_spec import FontSpec, MarginSpec, PageSpec, TemplateSpecification


class _FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakePage:
    width = 595.0
    height = 842.0

    def extract_words(self, **_kwargs):
        return [
            {"text": "A4", "fontname": "Aptos", "size": 11},
            {"text": "Body", "fontname": "Aptos", "size": 11},
            {"text": "Heading", "fontname": "Aptos Display", "size": 18},
        ]

    def extract_tables(self):
        return [[["Name", "Value"], ["Area", "Grid"]]]

    def extract_text(self):
        return "A4 reference report"


class _BrokenPage:
    width = 842.0
    height = 595.0

    def extract_words(self, **_kwargs):
        raise KeyError("font metadata missing")

    def extract_tables(self):
        raise ValueError("table parser failed")

    def extract_text(self):
        return None


def test_pdf_extractor_returns_page_fonts_tables_and_text(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "backend.app.engines.pdf_extractor.pdfplumber.open", lambda _path: _FakePdf([_FakePage()])
    )

    extracted = PdfExtractor().extract_structure(str(tmp_path / "reference.pdf"))

    assert extracted["total_pages"] == 1
    assert extracted["page_dimensions"] == [
        {"page_number": 1, "width": 595.0, "height": 842.0, "orientation": "portrait"}
    ]
    assert extracted["detected_fonts"] == ["Aptos", "Aptos Display"]
    assert extracted["dominant_font"] == "Aptos"
    assert extracted["font_counts"] == {"Aptos": 2, "Aptos Display": 1}
    assert extracted["font_sizes"] == [11.0, 18.0]
    assert extracted["tables"] == [
        {"page": 1, "rows": 2, "cols": 2, "sample_data": [["Name", "Value"], ["Area", "Grid"]]}
    ]
    assert extracted["text_blocks"][0]["text_sample"] == "A4 reference report"


def test_pdf_extractor_warns_on_optional_metadata_errors(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "backend.app.engines.pdf_extractor.pdfplumber.open", lambda _path: _FakePdf([_BrokenPage()])
    )

    extracted = PdfExtractor().extract_structure(str(tmp_path / "broken-metadata.pdf"))

    assert extracted["page_dimensions"][0]["orientation"] == "landscape"
    assert extracted["detected_fonts"] == []
    assert extracted["tables"] == []
    assert extracted["text_blocks"] == []


def test_pdf_analyzer_uses_detected_font_and_table_facts():
    analyzer = PdfAnalyzer()
    analyzer.extractor = SimpleNamespace(
        extract_structure=lambda _path: {
            "total_pages": 2,
            "page_dimensions": [{"width": 595.0, "height": 842.0, "orientation": "portrait"}],
            "dominant_font": "Aptos",
            "detected_fonts": ["Aptos", "Aptos Display"],
            "tables": [{"rows": 4, "cols": 3}],
        }
    )

    spec = analyzer.analyze("reference.pdf")

    assert spec.page.width_pt == 595.0
    assert spec.page.height_pt == 842.0
    assert spec.fonts.default == "Aptos"
    assert spec.fonts.all_detected_fonts == ["Aptos", "Aptos Display"]
    assert [(table.rows, table.cols) for table in spec.table_rules] == [(4, 3)]


def test_pdf_reference_builder_applies_measured_geometry_and_fonts(tmp_path: Path):
    spec = TemplateSpecification(
        filename="reference.pdf",
        document_type="pdf",
        page=PageSpec(
            width_pt=595,
            height_pt=842,
            margins=MarginSpec(top_pt=42, bottom_pt=48, left_pt=51, right_pt=54),
        ),
        fonts=FontSpec(body="Aptos", heading1="Aptos Display"),
    )
    output = tmp_path / "reference-base.docx"

    PdfReferenceBuilder().build_docx_base(spec, output)

    generated = Document(output)
    section = generated.sections[0]
    assert section.page_width.pt == 595
    assert section.page_height.pt == 842
    assert section.top_margin.pt == 42
    assert section.left_margin.pt == 51
    assert generated.styles["Normal"].font.name == "Aptos"
    assert generated.styles["Heading 1"].font.name == "Aptos Display"


def test_pdf_reference_builder_does_not_guess_a_font_when_none_was_detected(tmp_path: Path):
    spec = TemplateSpecification(filename="scan.pdf", document_type="pdf", fonts=FontSpec())
    output = tmp_path / "scan-base.docx"

    PdfReferenceBuilder().build_docx_base(spec, output)

    assert Document(output).styles["Normal"].font.name is None
