from typing import Literal, Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from .template_spec import TemplateSpecification

class TableData(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    source_table_index: int = 0
    title: Optional[str] = None

class DocumentSection(BaseModel):
    title: str
    heading_style: Optional[str] = None
    paragraphs: List[str] = Field(default_factory=list)
    bullets: List[str] = Field(default_factory=list)
    table_data: Optional[TableData] = None
    image_query: Optional[str] = None
    image_caption: Optional[str] = None
    image_path: Optional[str] = None
    subsections: List['DocumentSection'] = Field(default_factory=list)

class ThemeOverride(BaseModel):
    element_type: str = Field(description="'border', 'font', 'color', 'shading', etc.")
    target_identifier: Optional[str] = Field(default=None, description="Current color, style name, or border position")
    new_value: str = Field(description="New color hex, new border style, or property value")
    description: Optional[str] = None

class DocumentPlan(BaseModel):
    title: str
    target_audience: Optional[str] = "Professional / Academic"
    sections: List[DocumentSection] = Field(default_factory=list)
    conclusion: Optional[str] = None
    applied_styles: List[str] = Field(default_factory=list)
    theme_overrides: List[ThemeOverride] = Field(default_factory=list)

class SlidePlan(BaseModel):
    slide_number: int
    title: str
    subtitle: Optional[str] = None
    layout_name: str
    bullet_points: List[str] = Field(default_factory=list)
    body_paragraphs: List[str] = Field(default_factory=list)
    table_data: Optional[TableData] = None
    image_query: Optional[str] = None
    image_path: Optional[str] = None
    speaker_notes: Optional[str] = None

class PresentationPlan(BaseModel):
    presentation_title: str
    audience: Optional[str] = "General / Professional"
    slides: List[SlidePlan] = Field(default_factory=list)
    applied_layouts: List[str] = Field(default_factory=list)

class GenerationRequest(BaseModel):
    template_id: str
    prompt: str
    document_type: Literal["docx", "pptx", "pdf"] = "docx"
    mode: Literal["create_document", "create_presentation", "edit_document", "edit_presentation"] = "create_document"
    target_pages_or_slides: Optional[int] = None
    custom_instructions: Optional[str] = None
    include_images: bool = True
    image_mode: Literal["search", "generate", "auto"] = "auto"

class ValidationReport(BaseModel):
    passed: bool = True
    original_style_hash: str = ""
    generated_style_hash: str = ""
    hash_match: bool = True
    font_drift_detected: bool = False
    border_drift_detected: bool = False
    margin_drift_detected: bool = False
    layout_drift_detected: bool = False
    header_footer_preserved: bool = True
    table_formatting_preserved: bool = True
    issues: List[str] = Field(default_factory=list)
    differences: Dict[str, Any] = Field(default_factory=dict)

class GenerationResponse(BaseModel):
    success: bool
    output_filename: str
    download_url: str
    template_spec: TemplateSpecification
    plan: Optional[Union[DocumentPlan, PresentationPlan, Dict[str, Any]]] = None
    validation: ValidationReport
    execution_time_sec: float = 0.0
    message: str = "Successfully generated artifact using exact template inheritance."
