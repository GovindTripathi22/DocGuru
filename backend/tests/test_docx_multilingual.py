from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from backend.app.analyzer.docx_analyzer import DocxAnalyzer
from backend.app.engines.docx_engine import DocxEngine
from backend.app.models.generation import DocumentPlan, DocumentSection, TableData


def _set_default_script_fonts(document: Document, *, use_theme: bool) -> None:
    rfonts = document.styles.element.xpath("./w:docDefaults/w:rPrDefault/w:rPr/w:rFonts")[0]
    if use_theme:
        rfonts.set(qn("w:asciiTheme"), "majorHAnsi")
        rfonts.set(qn("w:eastAsiaTheme"), "majorEastAsia")
        rfonts.set(qn("w:cstheme"), "majorBidi")
    else:
        rfonts.set(qn("w:ascii"), "Aptos")
        rfonts.set(qn("w:eastAsia"), "Noto Sans CJK")
        rfonts.set(qn("w:cs"), "Noto Naskh Arabic")


def _write_theme_fonts(source: Path, target: Path) -> None:
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as updated,
    ):
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == "word/theme/theme1.xml":
                root = etree.fromstring(data)
                major = root.xpath(".//*[local-name()='majorFont']")[0]
                for name, value in (
                    ("latin", "Aptos Display"),
                    ("ea", "Noto Sans CJK JP"),
                    ("cs", "Noto Naskh Arabic UI"),
                ):
                    major.xpath(f"./*[local-name()='{name}']")[0].set("typeface", value)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            updated.writestr(item, data)


def test_docx_generation_preserves_multilingual_text_and_uses_template_script_fonts(tmp_path: Path):
    template_path = tmp_path / "multilingual-defaults.docx"
    template = Document()
    _set_default_script_fonts(template, use_theme=False)
    template.save(template_path)

    analyzer = DocxAnalyzer()
    spec = analyzer.analyze(str(template_path))
    assert spec.fonts.ascii_font == "Aptos"
    assert spec.fonts.east_asian_font == "Noto Sans CJK"
    assert spec.fonts.complex_script_font == "Noto Naskh Arabic"

    engine = DocxEngine()
    locked = engine.load_template(str(template_path), spec)
    plan = DocumentPlan(
        title="Multilingual report",
        sections=[
            DocumentSection(
                title="Sample text",
                paragraphs=["हिन्दी नमूना", "مرحبا بالعالم", "日本語の文章", "Science 🧪 Cafe\u0301"],
                table_data=TableData(headers=["भाषा"], rows=[["हिन्दी तालिका"]]),
            )
        ],
    )
    output_path = tmp_path / "multilingual-output.docx"
    engine.generate_from_plan(locked, plan, str(output_path))

    generated = Document(output_path)
    paragraphs = {paragraph.text: paragraph for paragraph in generated.paragraphs}
    assert (
        paragraphs["हिन्दी नमूना"].runs[0]._element.rPr.rFonts.get(qn("w:cs")) == "Noto Naskh Arabic"
    )
    arabic = paragraphs["مرحبا بالعالم"]
    assert arabic._p.pPr.find(qn("w:bidi")).get(qn("w:val")) == "1"
    assert arabic.runs[0]._element.rPr.rtl.val is True
    assert arabic.runs[0]._element.rPr.rFonts.get(qn("w:cs")) == "Noto Naskh Arabic"
    assert (
        paragraphs["日本語の文章"].runs[0]._element.rPr.rFonts.get(qn("w:eastAsia"))
        == "Noto Sans CJK"
    )
    assert paragraphs["Science 🧪 Cafe\u0301"].text == "Science 🧪 Cafe\u0301"
    assert generated.tables[0].cell(1, 0).text == "हिन्दी तालिका"
    assert (
        generated.tables[0].cell(1, 0).paragraphs[0].runs[0]._element.rPr.rFonts.get(qn("w:cs"))
        == "Noto Naskh Arabic"
    )


def test_docx_analyzer_resolves_script_fonts_from_theme(tmp_path: Path):
    base_path = tmp_path / "theme-base.docx"
    template = Document()
    _set_default_script_fonts(template, use_theme=True)
    template.save(base_path)
    themed_path = tmp_path / "theme-fonts.docx"
    _write_theme_fonts(base_path, themed_path)

    spec = DocxAnalyzer().analyze(str(themed_path))

    assert spec.fonts.ascii_font == "Aptos Display"
    assert spec.fonts.east_asian_font == "Noto Sans CJK JP"
    assert spec.fonts.complex_script_font == "Noto Naskh Arabic UI"
