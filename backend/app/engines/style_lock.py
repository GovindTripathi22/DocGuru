import logging
from typing import Any

from ..models.template_spec import LockStatus, TemplateSpecification

logger = logging.getLogger(__name__)


class StyleLockViolationError(Exception):
    """Raised when an operation attempts to violate the locked template styles."""


class LockedTemplate:
    """
    Wrapper around a loaded DOCX Document that enforces strict style locking.
    """

    def __init__(self, docx_document: Any, template_path: str, spec: TemplateSpecification):
        self.doc = docx_document
        self.template_path = template_path
        self.spec = spec
        self.initial_style_hash = spec.style_hash
        self.allowed_heading_styles: set[str] = set(spec.available_heading_styles or [])
        self.allowed_styles: set[str] = set(spec.styles.keys() if spec.styles else [])

        # Detect valid paragraph and table styles directly on the document object
        self.valid_doc_paragraph_styles: set[str] = set()
        self.valid_doc_table_styles: set[str] = set()
        if hasattr(docx_document, "styles"):
            try:
                from docx.enum.style import WD_STYLE_TYPE

                for s in docx_document.styles:
                    if s.type == WD_STYLE_TYPE.PARAGRAPH:
                        self.valid_doc_paragraph_styles.add(s.name)
                    elif s.type == WD_STYLE_TYPE.TABLE:
                        self.valid_doc_table_styles.add(s.name)
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                logger.debug("Template styles could not be enumerated: %s", exc)

        # Determine safe default body style
        if "Normal" in self.valid_doc_paragraph_styles or "Normal" in self.allowed_styles:
            self.default_body_style = "Normal"
        elif self.spec.available_body_styles:
            self.default_body_style = self.spec.available_body_styles[0]
        elif self.valid_doc_paragraph_styles:
            self.default_body_style = min(self.valid_doc_paragraph_styles)
        else:
            self.default_body_style = "Normal"

    def get_valid_table_style(self) -> str | None:
        """
        Returns a verified TABLE style name (type 3) from the document styles, or None.
        Guarantees that a paragraph style (type 1) is NEVER returned for table styling.
        """
        if self.spec and self.spec.table_rules:
            for tr in self.spec.table_rules:
                if tr.style_name and tr.style_name in self.valid_doc_table_styles:
                    return tr.style_name

        for s in sorted(self.valid_doc_table_styles):
            if "grid" in s.lower():
                return s
        for s in sorted(self.valid_doc_table_styles):
            if "table" in s.lower():
                return s

        if self.valid_doc_table_styles:
            return min(self.valid_doc_table_styles)

        return None

    def validate_style_allowed(self, style_name: str | None) -> str | None:
        """
        Verify that the requested style exists in the template.
        Returns the valid style name or falls back to an existing closest match,
        or None if no matching style exists in the document.
        """
        if not style_name:
            return self.default_body_style

        # Direct check against document's actual paragraph styles if available
        if self.valid_doc_paragraph_styles:
            if style_name in self.valid_doc_paragraph_styles:
                return style_name

            # Case-insensitive match in actual doc paragraph styles
            for s in sorted(self.valid_doc_paragraph_styles):
                if s.lower() == style_name.lower():
                    return s

            # Heading style match in actual doc paragraph styles
            if "heading" in style_name.lower():
                for s in sorted(self.valid_doc_paragraph_styles):
                    if "heading" in s.lower():
                        if "1" in style_name and "1" in s:
                            return s
                        if "2" in style_name and "2" in s:
                            return s
                        if "3" in style_name and "3" in s:
                            return s
                # Fall back to any heading style found
                for s in sorted(self.valid_doc_paragraph_styles):
                    if "heading" in s.lower() or "title" in s.lower():
                        return s

            # If style not found, return default body style if valid, else None
            return (
                self.default_body_style
                if self.default_body_style in self.valid_doc_paragraph_styles
                else None
            )

        # Fallback if valid_doc_paragraph_styles wasn't populated
        if style_name in self.allowed_styles:
            return style_name

        for s in sorted(self.allowed_styles):
            if s.lower() == style_name.lower():
                return s

        if "heading" in style_name.lower() and self.allowed_heading_styles:
            return min(self.allowed_heading_styles)

        return self.default_body_style


class LockedPresentation:
    """
    Wrapper around a loaded PPTX Presentation that enforces strict theme and layout locking.
    """

    def __init__(self, pptx_presentation: Any, template_path: str, spec: TemplateSpecification):
        self.prs = pptx_presentation
        self.template_path = template_path
        self.spec = spec
        self.initial_style_hash = spec.style_hash
        self.available_layout_names: list[str] = spec.available_layout_names
        self.layout_map: dict[str, Any] = {}

        # Build mapping of layout names to layout objects
        for layout in self.prs.slide_layouts:
            self.layout_map[layout.name] = layout

    def get_layout(self, layout_name: str) -> Any:
        """
        Return the exact slide layout requested, or the closest existing layout.
        NEVER creates a new layout.
        """
        if layout_name in self.layout_map:
            return self.layout_map[layout_name]

        # Case-insensitive search
        for name, layout in self.layout_map.items():
            if name.lower() == layout_name.lower():
                return layout

        # Partial search (e.g. "Title and Content" matching "Title + Content")
        for name, layout in self.layout_map.items():
            if (
                "title" in layout_name.lower()
                and "content" in layout_name.lower()
                and "title" in name.lower()
                and ("content" in name.lower() or "body" in name.lower())
            ):
                return layout
            if (
                "title" in layout_name.lower()
                and "slide" in layout_name.lower()
                and "title" in name.lower()
                and "slide" in name.lower()
            ):
                return layout

        # Fallback to the first available layout or layout 1 (standard title & content)
        if len(self.prs.slide_layouts) > 1:
            return self.prs.slide_layouts[1]
        return self.prs.slide_layouts[0]


class StyleLock:
    """
    Template Style Lock Manager.
    Ensures all formatting properties remain immutable during generation.
    """

    LOCKED_FIELDS = (
        "fonts",
        "colors",
        "borders",
        "margins",
        "layouts",
        "headers",
        "footers",
        "theme",
        "page_size",
        "styles",
        "table_styles",
        "paragraph_styles",
    )

    @staticmethod
    def get_lock_status() -> LockStatus:
        return LockStatus()

    FORBIDDEN_OPERATION_FIELDS = (
        "font_size",
        "font_size_pt",
        "font_name",
        "font_family",
        "font",
        "color",
        "font_color",
        "border_color",
        "border_width",
        "margin_top",
        "margin_left",
        "custom_style",
        "new_style",
        "override_theme",
        "override_font",
        "theme_overrides",
    )

    @classmethod
    def assert_content_only(cls, operation_args: dict[str, Any]) -> None:
        """
        Assert that the given operation arguments do NOT contain raw formatting parameters.
        """
        for key in cls.FORBIDDEN_OPERATION_FIELDS:
            matching_key = next(
                (candidate for candidate in operation_args if candidate.lower() == key), None
            )
            if matching_key is not None and operation_args[matching_key] is not None:
                raise StyleLockViolationError(
                    f"StyleLock Violation: AI attempted to override '{matching_key}'. "
                    f"All styling must be inherited directly from the original template."
                )

    @classmethod
    def assert_plan_content_only(cls, value: Any) -> None:
        """Recursively reject model fields that request template formatting changes."""
        if isinstance(value, dict):
            cls.assert_content_only(value)
            for child in value.values():
                cls.assert_plan_content_only(child)
        elif isinstance(value, list):
            for child in value:
                cls.assert_plan_content_only(child)

    @classmethod
    def check_direct_formatting_violations(cls, element: Any) -> list[str]:
        """Inspect paragraphs and runs for injected direct formatting mutations."""
        violations = []
        if hasattr(element, "paragraphs"):
            paras = element.paragraphs
        elif isinstance(element, (list, tuple)):
            paras = element
        else:
            paras = [element]

        for p in paras:
            if hasattr(p, "paragraph_format"):
                pf = p.paragraph_format
                if (
                    getattr(pf, "space_before", None) is not None
                    and getattr(pf.space_before, "pt", 0) > 36
                ):
                    violations.append(f"Injected paragraph space_before: {pf.space_before.pt}pt")
            if hasattr(p, "runs"):
                for run in p.runs:
                    if hasattr(run, "font"):
                        if getattr(run.font, "size", None) is not None:
                            violations.append(f"Injected run font size: {run.font.size.pt}pt")
                        if (
                            getattr(run.font, "color", None) is not None
                            and getattr(run.font.color, "rgb", None) is not None
                        ):
                            violations.append(f"Injected run font color: {run.font.color.rgb}")
        return violations

    @classmethod
    def assert_no_direct_formatting(cls, element: Any) -> None:
        """Asserts that no unauthorized direct font size or spacing mutations were injected."""
        violations = cls.check_direct_formatting_violations(element)
        if violations:
            raise StyleLockViolationError(
                f"StyleLock Violation: Direct formatting mutation detected: {'; '.join(violations)}"
            )
