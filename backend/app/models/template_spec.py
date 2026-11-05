from typing import Any, Literal

from pydantic import BaseModel, Field


class MarginSpec(BaseModel):
    top_pt: float = 72.0
    bottom_pt: float = 72.0
    left_pt: float = 72.0
    right_pt: float = 72.0
    header_pt: float = 36.0
    footer_pt: float = 36.0


class PageSpec(BaseModel):
    width_pt: float = 612.0
    height_pt: float = 792.0
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins: MarginSpec = Field(default_factory=MarginSpec)
    columns_count: int = 1
    page_borders: dict[str, Any] | None = None
    background_color: str | None = None


class FontSpec(BaseModel):
    default: str | None = None
    body: str | None = None
    heading1: str | None = None
    heading2: str | None = None
    heading3: str | None = None
    ascii_font: str | None = None
    east_asian_font: str | None = None
    complex_script_font: str | None = None
    all_detected_fonts: list[str] = Field(default_factory=list)


class StyleSpec(BaseModel):
    name: str
    type: Literal["paragraph", "character", "table", "numbering"] = "paragraph"
    font_name: str | None = None
    font_size_pt: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    color_hex: str | None = None
    highlight: str | None = None
    alignment: str | None = "left"  # left, center, right, justify
    spacing_before_pt: float | None = 0.0
    spacing_after_pt: float | None = 0.0
    line_spacing: float | None = 1.15
    keep_with_next: bool = False
    keep_lines_together: bool = False
    widow_control: bool = True
    is_heading: bool = False
    outline_level: int | None = None
    based_on: str | None = None


class ParagraphRuleSpec(BaseModel):
    alignment: str = "left"
    indent_left_pt: float = 0.0
    indent_right_pt: float = 0.0
    first_line_indent_pt: float = 0.0
    spacing_before_pt: float = 0.0
    spacing_after_pt: float = 6.0
    line_spacing: float = 1.15
    keep_with_next: bool = False
    keep_lines_together: bool = False
    widow_orphan: bool = True


class BorderItemSpec(BaseModel):
    val: str = "single"  # single, double, dashed, dotted, etc.
    sz_pt: float = 0.5  # border thickness in points
    color: str = "auto"
    space_pt: float = 0.0


class BorderSpec(BaseModel):
    top: BorderItemSpec | None = None
    bottom: BorderItemSpec | None = None
    left: BorderItemSpec | None = None
    right: BorderItemSpec | None = None
    insideH: BorderItemSpec | None = None
    insideV: BorderItemSpec | None = None


class TableRuleSpec(BaseModel):
    table_index: int = 0
    rows: int = 0
    cols: int = 0
    col_widths_pt: list[float] = Field(default_factory=list)
    borders: BorderSpec | None = None
    shading_color: str | None = None
    alignment: str = "center"
    header_row_formatting: dict[str, Any] | None = None
    cell_margins_pt: dict[str, float] | None = None
    style_name: str | None = None


class HeaderFooterSpec(BaseModel):
    has_content: bool = False
    text_preview: str | None = None
    alignment: str | None = "left"
    distance_pt: float = 36.0
    has_page_number: bool = False
    has_logo: bool = False
    is_linked_to_previous: bool = True
    paragraph_count: int = 0


class NumberingSpec(BaseModel):
    detected: bool = False
    numbering_styles: list[str] = Field(default_factory=list)
    format_types: list[str] = Field(
        default_factory=list
    )  # decimal, upperLetter, lowerLetter, bullet
    has_bullet_lists: bool = False
    has_numbered_lists: bool = False


class ThemeColorScheme(BaseModel):
    dark1: str | None = None
    light1: str | None = None
    dark2: str | None = None
    light2: str | None = None
    accent1: str | None = None
    accent2: str | None = None
    accent3: str | None = None
    accent4: str | None = None
    accent5: str | None = None
    accent6: str | None = None


class ThemeFontScheme(BaseModel):
    major_font: str | None = None  # Heading font
    minor_font: str | None = None  # Body font


class ThemeSpec(BaseModel):
    name: str | None = None
    color_scheme: ThemeColorScheme | None = None
    font_scheme: ThemeFontScheme | None = None


class PlaceholderSpec(BaseModel):
    index: int
    name: str
    type: str  # TITLE, BODY, CENTER_TITLE, SUBTITLE, TABLE, PICTURE, FOOTER, SLIDE_NUMBER, DATE
    left_inches: float = 0.0
    top_inches: float = 0.0
    width_inches: float = 0.0
    height_inches: float = 0.0


class LayoutSpec(BaseModel):
    index: int
    name: str
    placeholders: list[PlaceholderSpec] = Field(default_factory=list)
    master_name: str | None = None
    background_type: str | None = None


class MasterSpec(BaseModel):
    index: int
    name: str
    layout_count: int = 0
    theme_ref: str | None = None


class SlideDimensionSpec(BaseModel):
    width_inches: float = 13.333
    height_inches: float = 7.5
    aspect_ratio: str = "16:9"  # "16:9", "4:3", etc.


class LockStatus(BaseModel):
    fonts: str = "guarded"
    colors: str = "guarded"
    borders: str = "guarded"
    margins: str = "guarded"
    layouts: str = "guarded"
    headers: str = "guarded"
    footers: str = "guarded"
    theme: str = "guarded"
    page_size: str = "guarded"
    styles: str = "guarded"
    table_styles: str = "guarded"


class TemplateSpecification(BaseModel):
    filename: str
    document_type: Literal["docx", "pptx", "pdf"]
    total_pages_or_slides: int = 1
    page: PageSpec | None = None
    slide_dimensions: SlideDimensionSpec | None = None
    fonts: FontSpec = Field(default_factory=FontSpec)
    styles: dict[str, StyleSpec] = Field(default_factory=dict)
    paragraph_rules: dict[str, ParagraphRuleSpec] = Field(default_factory=dict)
    table_rules: list[TableRuleSpec] = Field(default_factory=list)
    header: HeaderFooterSpec | None = None
    footer: HeaderFooterSpec | None = None
    numbering: NumberingSpec | None = None
    borders: dict[str, BorderSpec] = Field(default_factory=dict)
    theme: ThemeSpec | None = None
    layouts: list[LayoutSpec] | None = None
    masters: list[MasterSpec] | None = None
    available_heading_styles: list[str] = Field(default_factory=list)
    available_body_styles: list[str] = Field(default_factory=list)
    available_layout_names: list[str] = Field(default_factory=list)
    extracted_rules: list[str] = Field(default_factory=list)
    document_outline: list[str] = Field(default_factory=list)
    document_text_summary: str | None = None
    style_hash: str = ""
    lock_status: LockStatus = Field(default_factory=LockStatus)
