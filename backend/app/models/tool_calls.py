from typing import Literal, Dict, List, Any, Optional
from pydantic import BaseModel, Field

class InsertHeadingArgs(BaseModel):
    style: str = Field(description="Must be an exact existing heading style name from the template (e.g. 'Heading 1', 'Heading 2', 'ChapterTitle')")
    content: str = Field(description="The heading text content")

class InsertParagraphArgs(BaseModel):
    style: str = Field(default="Normal", description="Must be an existing paragraph style name from the template")
    content: str = Field(description="The paragraph text content")

class InsertBulletArgs(BaseModel):
    content: str = Field(description="The bullet item text")
    level: int = Field(default=0, description="Nesting level (0-based)")

class InsertTableArgs(BaseModel):
    source_table_index: int = Field(default=0, description="Index of existing table in template to clone formatting and borders from")
    headers: List[str] = Field(description="Column header titles")
    rows: List[List[str]] = Field(description="Table row data")
    title: Optional[str] = Field(default=None, description="Optional table title")

class InsertSlideArgs(BaseModel):
    layout_name: str = Field(description="Must be an exact layout name defined in the template slide master")
    title: str = Field(description="Slide title")
    subtitle: Optional[str] = Field(default=None, description="Optional slide subtitle")
    bullet_points: List[str] = Field(default_factory=list, description="Bullet items for content placeholder")
    body_paragraphs: List[str] = Field(default_factory=list, description="Paragraphs for body placeholder")
    table_headers: Optional[List[str]] = Field(default=None, description="Optional table headers")
    table_rows: Optional[List[List[str]]] = Field(default=None, description="Optional table rows")
    speaker_notes: Optional[str] = Field(default=None, description="Optional speaker notes")

class ReplaceTextArgs(BaseModel):
    search_text: str = Field(description="Exact string in document to replace")
    replacement_text: str = Field(description="New replacement text")

class DuplicateSlideArgs(BaseModel):
    source_slide_index: int = Field(description="0-based index of slide to duplicate")

class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

class ToolCallResult(BaseModel):
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
