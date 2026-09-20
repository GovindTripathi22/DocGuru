from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AppError(Exception):
    code: str
    http_status: int
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class LLMNotConfigured(AppError):
    def __init__(
        self,
        message: str = "The AI provider is not configured. Set GEMINI_API_KEY or select MODEL_PROVIDER=demo.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="LLM_NOT_CONFIGURED",
            http_status=503,
            message=message,
            details=details or {},
        )


class LLMUnavailable(AppError):
    def __init__(
        self,
        message: str = "The AI service is currently unavailable. Please retry.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="LLM_UNAVAILABLE",
            http_status=502,
            message=message,
            details=details or {},
        )


class LLMTimeout(AppError):
    def __init__(
        self,
        message: str = "The AI request timed out. Please retry with a smaller scope.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="LLM_TIMEOUT",
            http_status=504,
            message=message,
            details=details or {},
        )


class LLMRateLimited(AppError):
    def __init__(
        self,
        message: str = "Rate limit exceeded. Please wait before trying again.",
        retry_after: int = 30,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        d = details or {}
        d["retry_after"] = retry_after
        super().__init__(
            code="LLM_RATE_LIMITED",
            http_status=429,
            message=message,
            details=d,
        )


class LLMBlocked(AppError):
    def __init__(
        self,
        message: str = "The request was blocked by safety filters.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="LLM_BLOCKED",
            http_status=422,
            message=message,
            details=details or {},
        )


class LLMTruncated(AppError):
    def __init__(
        self,
        message: str = "The model response was truncated.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="LLM_TRUNCATED",
            http_status=502,
            message=message,
            details=details or {},
        )


class LLMInvalidResponse(AppError):
    def __init__(
        self,
        message: str = "The model returned an invalid or empty response.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="LLM_INVALID_RESPONSE",
            http_status=502,
            message=message,
            details=details or {},
        )


class TemplateNotFound(AppError):
    def __init__(
        self,
        template_id: str,
        message: Optional[str] = None,
    ) -> None:
        super().__init__(
            code="TEMPLATE_NOT_FOUND",
            http_status=404,
            message=message or f"Template '{template_id}' was not found.",
            details={"template_id": template_id},
        )


class OutputNotFound(AppError):
    def __init__(
        self,
        output_id: str,
        message: Optional[str] = None,
    ) -> None:
        super().__init__(
            code="OUTPUT_NOT_FOUND",
            http_status=404,
            message=message or f"File '{output_id}' was not found.",
            details={"output_id": output_id},
        )


class TemplateDriftDetected(AppError):
    def __init__(
        self,
        message: str = "Template formatting drift detected beyond allowable tolerance.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="TEMPLATE_DRIFT_DETECTED",
            http_status=422,
            message=message,
            details=details or {},
        )


class EditTargetNotFound(AppError):
    def __init__(
        self,
        target: str,
        candidates: Optional[list[str]] = None,
    ) -> None:
        super().__init__(
            code="EDIT_TARGET_NOT_FOUND",
            http_status=422,
            message=f"Edit target '{target}' could not be resolved.",
            details={"target": target, "candidates": candidates or []},
        )


class UnsupportedFile(AppError):
    def __init__(
        self,
        message: str = "Unsupported or protected file.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="UNSUPPORTED_OR_PROTECTED_FILE",
            http_status=422,
            message=message,
            details=details or {},
        )


class PayloadTooLarge(AppError):
    def __init__(
        self,
        message: str = "Uploaded file exceeds maximum allowed size.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code="PAYLOAD_TOO_LARGE",
            http_status=413,
            message=message,
            details=details or {},
        )
