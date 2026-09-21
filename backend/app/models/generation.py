from typing import Literal, Dict, List, Any, Optional, Union
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from .template_spec import TemplateSpecification


COLOR_NAMES_TO_HEX = {
    "black": "000000",
    "white": "FFFFFF",
    "red": "FF0000",
    "green": "008000",
    "blue": "0000FF",
    "navy": "000080",
    "teal": "008080",
    "gray": "808080",
    "grey": "808080",
    "maroon": "800000",
    "purple": "800080",
    "olive": "808000",
    "silver": "C0C0C0",
    "auto": "auto",
}


class TableData(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    source_table_index: int = 0
    title: Optional[str] = None


class DocumentSection(BaseModel):
    title: str
    heading_style: Optional[str] = None
    action: Literal["create", "append", "insert_after", "replace"] = "create"
    target_heading: Optional[str] = None
    paragraphs: List[str] = Field(default_factory=list)
    bullets: List[str] = Field(default_factory=list)
    table_data: Optional[TableData] = None
    image_query: Optional[str] = None
    image_caption: Optional[str] = None
    image_path: Optional[str] = None
    subsections: List['DocumentSection'] = Field(default_factory=list)


class ThemeOverride(BaseModel):
    element_type: str = Field(default="border", description="'border', 'font', 'color', 'shading', etc.")
    target_identifier: Optional[str] = Field(default=None, description="Current color, style name, or border position")
    new_value: str = Field(default="", description="New color hex, new border style, or property value")
    description: Optional[str] = None


class ThemeOverrideRequest(BaseModel):
    target: Literal["table_border", "page_border", "heading_color"]
    selector: Optional[str] = None
    value: str

    @field_validator("value")
    @classmethod
    def validate_hex_or_color(cls, v: str) -> str:
        clean = v.strip().lstrip("#")
        if clean.lower() in COLOR_NAMES_TO_HEX:
            return COLOR_NAMES_TO_HEX[clean.lower()]
        if re.match(r"^[0-9A-Fa-f]{6}$", clean):
            return clean.upper()
        raise ValueError(f"Invalid color value '{v}'. Must be a 6-digit hex color code or recognized color name.")


class DocumentPlan(BaseModel):
    title: str
    target_audience: Optional[str] = "Professional / Academic"
    sections: List[DocumentSection] = Field(default_factory=list)
    conclusion: Optional[str] = None
    abstract: Optional[str] = None
    applied_styles: List[str] = Field(default_factory=list)
    applied_rules: List[str] = Field(default_factory=list)
    edit_mode: Optional[str] = "create"
    theme_overrides: List[ThemeOverride] = Field(default_factory=list)


class SlidePlan(BaseModel):
    slide_number: int
    title: str
    subtitle: Optional[str] = None
    layout_name: str
    layout_role: Optional[str] = None
    bullet_points: List[str] = Field(default_factory=list)
    body_paragraphs: List[str] = Field(default_factory=list)
    table_data: Optional[TableData] = None
    image_query: Optional[str] = None
    image_path: Optional[str] = None
    speaker_notes: Optional[str] = None
    columns: Optional[List[List[str]]] = None


class PresentationPlan(BaseModel):
    presentation_title: str
    audience: Optional[str] = "General / Professional"
    slides: List[SlidePlan] = Field(default_factory=list)


class GenerationRequest(BaseModel):
    template_id: str
    prompt: str
    document_type: Literal["docx", "pptx", "pdf"] = "docx"
    mode: Literal["create_document", "create_presentation", "edit_document", "edit_presentation"] = "create_document"
    target_sections: Optional[int] = Field(default=None, ge=1, le=50)
    target_pages: Optional[int] = Field(default=None, ge=1, le=50)
    target_slides: Optional[int] = Field(default=None, ge=1, le=50)
    target_pages_or_slides: Optional[int] = Field(default=None, ge=1, le=50)  # Deprecated alias
    custom_instructions: Optional[str] = None
    include_images: bool = True
    image_mode: Literal["off", "search", "placeholder", "auto", "generate"] = "search"
    template_mode: Literal["auto", "fill", "append", "replace_body"] = "auto"
    body_anchor_index: Optional[int] = None
    overrides: List[ThemeOverrideRequest] = Field(default_factory=list)
    edit_target_index: Optional[int] = None
    edit_target_heading: Optional[str] = None
    edit_action: Optional[Literal["append", "insert_after", "replace", "update_text"]] = None


class ComponentResult(BaseModel):
    name: str
    status: Literal["identical", "changed", "intentional_override"]
    detail: Optional[str] = None


class ValidationReport(BaseModel):
    status: Literal["passed", "failed", "not_applicable"]
    passed: bool = True
    components: List[ComponentResult] = Field(default_factory=list)
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
    intentional_overrides: List[str] = Field(default_factory=list)
    content_checks: Dict[str, bool] = Field(default_factory=dict)
    original_fingerprint: Optional[Dict[str, str]] = None
    generated_fingerprint: Optional[Dict[str, str]] = None
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reconcile_status_and_passed(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "status" not in data and "passed" in data:
                data["status"] = "passed" if data["passed"] else "failed"
            elif "status" in data and "passed" not in data:
                data["passed"] = (data["status"] != "failed")
            elif "status" in data and "passed" in data:
                data["passed"] = (data["status"] != "failed")
        return data


class GenerationResponse(BaseModel):
    success: bool
    output_filename: str
    download_url: str
    template_spec: TemplateSpecification
    plan: Optional[Union[DocumentPlan, PresentationPlan, Dict[str, Any]]] = None
    validation: ValidationReport
    execution_time_sec: float = 0.0
    message: str = "Artifact generated and verified."
    generation_mode: str = "live"
    warnings: List[str] = Field(default_factory=list)
