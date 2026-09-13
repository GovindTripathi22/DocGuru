from typing import Literal, Dict, List, Any, Optional
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
    page_borders: Optional[Dict[str, Any]] = None
    background_color: Optional[str] = None

class FontSpec(BaseModel):
    default: str = "Calibri"
    body: str = "Calibri"
    heading1: Optional[str] = None
    heading2: Optional[str] = None
    heading3: Optional[str] = None
    ascii_font: Optional[str] = None
    east_asian_font: Optional[str] = None
    complex_script_font: Optional[str] = None
    all_detected_fonts: List[str] = Field(default_factory=list)

class StyleSpec(BaseModel):
    name: str
    type: Literal["paragraph", "character", "table", "numbering"] = "paragraph"
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    strike: Optional[bool] = None
    color_hex: Optional[str] = None
    highlight: Optional[str] = None
    alignment: Optional[str] = "left"  # left, center, right, justify
    spacing_before_pt: Optional[float] = 0.0
    spacing_after_pt: Optional[float] = 0.0
    line_spacing: Optional[float] = 1.15
    keep_with_next: bool = False
    keep_lines_together: bool = False
    widow_control: bool = True
    is_heading: bool = False
    outline_level: Optional[int] = None
    based_on: Optional[str] = None

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
    sz_pt: float = 0.5   # border thickness in points
    color: str = "auto"
    space_pt: float = 0.0

class BorderSpec(BaseModel):
    top: Optional[BorderItemSpec] = None
    bottom: Optional[BorderItemSpec] = None
    left: Optional[BorderItemSpec] = None
    right: Optional[BorderItemSpec] = None
    insideH: Optional[BorderItemSpec] = None
    insideV: Optional[BorderItemSpec] = None

class TableRuleSpec(BaseModel):
    table_index: int = 0
    rows: int = 0
    cols: int = 0
    col_widths_pt: List[float] = Field(default_factory=list)
    borders: Optional[BorderSpec] = None
    shading_color: Optional[str] = None
    alignment: str = "center"
    header_row_formatting: Optional[Dict[str, Any]] = None
    cell_margins_pt: Optional[Dict[str, float]] = None
    style_name: Optional[str] = None

class HeaderFooterSpec(BaseModel):
    has_content: bool = False
    text_preview: Optional[str] = None
    alignment: Optional[str] = "left"
    distance_pt: float = 36.0
    has_page_number: bool = False
    has_logo: bool = False
    is_linked_to_previous: bool = True
    paragraph_count: int = 0

class NumberingSpec(BaseModel):
    detected: bool = False
    numbering_styles: List[str] = Field(default_factory=list)
    format_types: List[str] = Field(default_factory=list)  # decimal, upperLetter, lowerLetter, bullet
    has_bullet_lists: bool = False
    has_numbered_lists: bool = False

class ThemeColorScheme(BaseModel):
    dark1: Optional[str] = None
    light1: Optional[str] = None
    dark2: Optional[str] = None
    light2: Optional[str] = None
    accent1: Optional[str] = None
    accent2: Optional[str] = None
    accent3: Optional[str] = None
    accent4: Optional[str] = None
    accent5: Optional[str] = None
    accent6: Optional[str] = None

class ThemeFontScheme(BaseModel):
    major_font: Optional[str] = None  # Heading font
    minor_font: Optional[str] = None  # Body font

class ThemeSpec(BaseModel):
    name: Optional[str] = None
    color_scheme: Optional[ThemeColorScheme] = None
    font_scheme: Optional[ThemeFontScheme] = None

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
    placeholders: List[PlaceholderSpec] = Field(default_factory=list)
    master_name: Optional[str] = None
    background_type: Optional[str] = None

class MasterSpec(BaseModel):
    index: int
    name: str
    layout_count: int = 0
    theme_ref: Optional[str] = None

class SlideDimensionSpec(BaseModel):
    width_inches: float = 13.333
    height_inches: float = 7.5
    aspect_ratio: str = "16:9"  # "16:9", "4:3", etc.

class LockStatus(BaseModel):
    fonts: str = "LOCKED"
    colors: str = "LOCKED"
    borders: str = "LOCKED"
    margins: str = "LOCKED"
    layouts: str = "LOCKED"
    headers: str = "LOCKED"
    footers: str = "LOCKED"
    theme: str = "LOCKED"
    page_size: str = "LOCKED"
    styles: str = "LOCKED"
    table_styles: str = "LOCKED"

class TemplateSpecification(BaseModel):
    filename: str
    document_type: Literal["docx", "pptx", "pdf"]
    total_pages_or_slides: int = 1
    page: Optional[PageSpec] = None
    slide_dimensions: Optional[SlideDimensionSpec] = None
    fonts: FontSpec = Field(default_factory=FontSpec)
    styles: Dict[str, StyleSpec] = Field(default_factory=dict)
    paragraph_rules: Dict[str, ParagraphRuleSpec] = Field(default_factory=dict)
    table_rules: List[TableRuleSpec] = Field(default_factory=list)
    header: Optional[HeaderFooterSpec] = None
    footer: Optional[HeaderFooterSpec] = None
    numbering: Optional[NumberingSpec] = None
    borders: Dict[str, BorderSpec] = Field(default_factory=dict)
    theme: Optional[ThemeSpec] = None
    layouts: Optional[List[LayoutSpec]] = None
    masters: Optional[List[MasterSpec]] = None
    available_heading_styles: List[str] = Field(default_factory=list)
    available_body_styles: List[str] = Field(default_factory=list)
    available_layout_names: List[str] = Field(default_factory=list)
    style_hash: str = ""
    lock_status: LockStatus = Field(default_factory=LockStatus)
