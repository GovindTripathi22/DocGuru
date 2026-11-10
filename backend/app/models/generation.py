import re
from typing import Any, Literal

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
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    source_table_index: int = 0
    title: str | None = None


class DocumentSection(BaseModel):
    title: str
    heading_style: str | None = None
    action: Literal["create", "append", "insert_after", "replace"] = "create"
    target_heading: str | None = None
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    table_data: TableData | None = None
    image_query: str | None = None
    image_caption: str | None = None
    image_path: str | None = None
    citations: list[str] = Field(default_factory=list)
    subsections: list["DocumentSection"] = Field(default_factory=list)


class ResearchSource(BaseModel):
    id: str
    title: str
    url: str
    snippet: str = ""
    published_date: str | None = None
    score: float | None = None


class ThemeOverride(BaseModel):
    element_type: str = Field(
        default="border", description="'border', 'font', 'color', 'shading', etc."
    )
    target_identifier: str | None = Field(
        default=None, description="Current color, style name, or border position"
    )
    new_value: str = Field(
        default="", description="New color hex, new border style, or property value"
    )
    description: str | None = None


class ThemeOverrideRequest(BaseModel):
    target: Literal["table_border", "page_border", "heading_color"]
    selector: str | None = None
    value: str

    @field_validator("value")
    @classmethod
    def validate_hex_or_color(cls, v: str) -> str:
        clean = v.strip().lstrip("#")
        if clean.lower() in COLOR_NAMES_TO_HEX:
            return COLOR_NAMES_TO_HEX[clean.lower()]
        if re.match(r"^[0-9A-Fa-f]{6}$", clean):
            return clean.upper()
        raise ValueError(
            f"Invalid color value '{v}'. Must be a 6-digit hex color code or recognized color name."
        )


class DocumentPlan(BaseModel):
    title: str
    target_audience: str | None = "Professional / Academic"
    author: str | None = None
    guide: str | None = None
    department: str | None = None
    institution: str | None = None
    academic_year: str | None = None
    include_tables: bool = True
    sections: list[DocumentSection] = Field(default_factory=list)
    conclusion: str | None = None
    abstract: str | None = None
    applied_styles: list[str] = Field(default_factory=list)
    applied_rules: list[str] = Field(default_factory=list)
    edit_mode: str | None = "create"
    theme_overrides: list[ThemeOverride] = Field(default_factory=list)
    research_sources: list[ResearchSource] = Field(default_factory=list)
    generation_mode: str = "live"
    warnings: list[str] = Field(default_factory=list)


class SlidePlan(BaseModel):
    slide_number: int
    title: str
    subtitle: str | None = None
    layout_name: str
    layout_role: str | None = None
    bullet_points: list[str] = Field(default_factory=list)
    body_paragraphs: list[str] = Field(default_factory=list)
    table_data: TableData | None = None
    image_query: str | None = None
    image_path: str | None = None
    speaker_notes: str | None = None
    columns: list[list[str]] | None = None


class PresentationPlan(BaseModel):
    presentation_title: str
    audience: str | None = "General / Professional"
    slides: list[SlidePlan] = Field(default_factory=list)
    generation_mode: str = "live"
    warnings: list[str] = Field(default_factory=list)


class GenerationRequest(BaseModel):
    template_id: str
    prompt: str = Field(min_length=1, max_length=4000)
    document_type: Literal["docx", "pptx", "pdf"] = "docx"
    mode: Literal[
        "create_document", "create_presentation", "edit_document", "edit_presentation"
    ] = "create_document"
    target_sections: int | None = Field(default=None, ge=1, le=50)
    target_pages: int | None = Field(default=None, ge=1, le=50)
    detail_level: Literal["low", "medium", "high"] | None = None
    target_slides: int | None = Field(default=None, ge=1, le=50)
    target_pages_or_slides: int | None = Field(default=None, ge=1, le=50)  # Deprecated alias
    enabled_rule_indices: list[int] | None = Field(default=None, max_length=12)
    custom_instructions: str | None = Field(default=None, max_length=1000)
    research_enabled: bool = False
    include_images: bool = True
    include_tables: bool = True
    image_mode: Literal["off", "search", "placeholder", "auto", "generate"] = "search"
    template_mode: Literal["auto", "fill", "append", "replace_body"] = "auto"
    body_anchor_index: int | None = None
    author: str | None = Field(default=None, max_length=200)
    guide: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    institution: str | None = Field(default=None, max_length=200)
    academic_year: str | None = Field(default=None, max_length=50)
    overrides: list[ThemeOverrideRequest] = Field(default_factory=list)
    edit_target_index: int | None = Field(default=None, ge=0)
    edit_target_heading: str | None = None
    edit_action: Literal["append", "insert_after"] | None = None

    @model_validator(mode="after")
    def validate_length_and_research_options(self) -> "GenerationRequest":
        if self.enabled_rule_indices is not None and (
            len(set(self.enabled_rule_indices)) != len(self.enabled_rule_indices)
            or any(index < 0 or index > 11 for index in self.enabled_rule_indices)
        ):
            raise ValueError("enabled_rule_indices must contain unique indexes from 0 through 11.")

        if self.target_pages is not None and self.detail_level is not None:
            raise ValueError("Choose either target_pages or detail_level, not both.")

        if self.target_pages_or_slides is not None:
            if self.document_type == "pptx":
                if (
                    self.target_slides is not None
                    and self.target_slides != self.target_pages_or_slides
                ):
                    raise ValueError(
                        "target_slides conflicts with the legacy target_pages_or_slides value."
                    )
                self.target_slides = self.target_slides or self.target_pages_or_slides
            else:
                if (
                    self.target_pages is not None
                    and self.target_pages != self.target_pages_or_slides
                ):
                    raise ValueError(
                        "target_pages conflicts with the legacy target_pages_or_slides value."
                    )
                if self.detail_level is not None:
                    raise ValueError(
                        "Use target_pages or detail_level with the legacy combined field, not both."
                    )
                self.target_pages = self.target_pages or self.target_pages_or_slides

        if self.document_type == "pptx":
            if (
                self.target_pages is not None
                or self.detail_level is not None
                or self.target_sections is not None
            ):
                raise ValueError(
                    "Presentations use target_slides; page and detail targets apply to documents."
                )
            if self.research_enabled:
                raise ValueError("Web research is currently available for documents only.")
        elif self.target_slides is not None:
            raise ValueError("target_slides applies only to presentations.")

        if self.detail_level is None and self.target_pages is None and self.document_type != "pptx":
            self.detail_level = "medium"
        if self.research_enabled and self.mode.startswith("edit"):
            raise ValueError("Research mode is available for new documents, not edit requests.")
        return self


class ComponentResult(BaseModel):
    name: str
    status: Literal["identical", "changed", "intentional_override"]
    detail: str | None = None


class ValidationReport(BaseModel):
    status: Literal["passed", "failed", "not_applicable"]
    passed: bool = True
    components: list[ComponentResult] = Field(default_factory=list)
    original_style_hash: str = ""
    generated_style_hash: str = ""
    hash_match: bool = True
    font_drift_detected: bool = False
    border_drift_detected: bool = False
    margin_drift_detected: bool = False
    layout_drift_detected: bool = False
    header_footer_preserved: bool = True
    table_formatting_preserved: bool = True
    issues: list[str] = Field(default_factory=list)
    differences: dict[str, Any] = Field(default_factory=dict)
    intentional_overrides: list[str] = Field(default_factory=list)
    content_checks: dict[str, bool] = Field(default_factory=dict)
    original_fingerprint: dict[str, str] | None = None
    generated_fingerprint: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reconcile_status_and_passed(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "status" not in data and "passed" in data:
                data["status"] = "passed" if data["passed"] else "failed"
            elif "status" in data and "passed" not in data or "status" in data and "passed" in data:
                data["passed"] = data["status"] != "failed"
        return data


class GenerationResponse(BaseModel):
    success: bool
    output_filename: str
    download_url: str
    template_spec: TemplateSpecification
    plan: DocumentPlan | PresentationPlan | dict[str, Any] | None = None
    validation: ValidationReport
    execution_time_sec: float = 0.0
    message: str = "Artifact generated and verified."
    generation_mode: str = "live"
    warnings: list[str] = Field(default_factory=list)
