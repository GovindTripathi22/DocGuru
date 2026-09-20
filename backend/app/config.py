"""Validated application configuration. Secrets are never logged."""

from pathlib import Path
import shutil
from typing import Literal
import logging

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR.parent / ".env"), env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "DocGuru"
    DEBUG: bool = False
    LOG_CONTENT: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65535)
    MODEL_PROVIDER: Literal["google_ai", "ollama", "openai_compat", "demo"] = "google_ai"
    MODEL_NAME: str = "gemma-4-31b-it"
    MODEL_ENDPOINT: str | None = None
    GEMINI_API_KEY: str = ""
    GEMMA_API_KEY: str = ""  # Deprecated alias; retained only for migration.
    TEMPERATURE: float = Field(default=0.2, ge=0, le=2)
    MAX_TOKENS: int = Field(default=8192, ge=128, le=65536)  # Legacy shim until Phase 2.
    OUTLINE_MAX_TOKENS: int = Field(default=1200, ge=128, le=16384)
    SECTION_MAX_TOKENS: int = Field(default=1800, ge=128, le=16384)
    LLM_TIMEOUT_SEC: int = Field(default=90, ge=1, le=600)
    LLM_MAX_RETRIES: int = Field(default=3, ge=0, le=10)
    LLM_MAX_CONCURRENCY: int = Field(default=3, ge=1, le=32)
    LLM_THINKING: Literal["off", "default"] = "default"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    API_KEYS: str = ""
    MAX_UPLOAD_MB: int = Field(default=25, ge=1, le=250)
    MAX_PDF_PAGES: int = Field(default=100, ge=1, le=1000)
    RETENTION_HOURS: int = Field(default=24, ge=1, le=720)
    WORKER_THREADS: int = Field(default=4, ge=1, le=32)
    MAX_CONCURRENT_JOBS: int = Field(default=4, ge=1, le=64)
    MIN_FREE_MB: int = Field(default=512, ge=1)
    PREVIEW_ENABLED: bool = False
    PAGE_BREAK_BETWEEN_SECTIONS: bool = False
    IMAGE_PLACEHOLDERS: bool = False
    IMAGE_CACHE_MAX_MB: int = Field(default=500, ge=1)
    IMAGE_TIMEOUT_SEC: int = Field(default=8, ge=1, le=60)
    IMAGE_BUDGET_SEC: int = Field(default=25, ge=1, le=300)
    UNSPLASH_ACCESS_KEY: str = ""
    PEXELS_API_KEY: str = ""
    OFFLINE_MODE: bool = False  # Compatibility input; demo is explicit provider.
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    TEMP_DIR: Path = BASE_DIR / "temp"
    DATA_DIR: Path = BASE_DIR / "data"
    JOBS_DIR: Path = BASE_DIR / "data" / "jobs"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def reject_wildcard_cors(cls, value: str) -> str:
        if "*" in value:
            raise ValueError("CORS_ORIGINS must name explicit origins; '*' is not allowed")
        return value

    @model_validator(mode="after")
    def handle_aliases_and_defaults(self) -> "Settings":
        if self.GEMMA_API_KEY and not self.GEMINI_API_KEY:
            logger.warning("GEMMA_API_KEY is deprecated; use GEMINI_API_KEY")
        if self.MODEL_ENDPOINT is None:
            self.MODEL_ENDPOINT = {
                "google_ai": "https://generativelanguage.googleapis.com/v1beta",
                "ollama": "http://127.0.0.1:11434",
                "openai_compat": "http://127.0.0.1:8001",
                "demo": "",
            }[self.MODEL_PROVIDER]
        return self

    @property
    def api_key(self) -> str:
        return self.GEMINI_API_KEY or self.GEMMA_API_KEY

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.CORS_ORIGINS.split(",") if value.strip()]

    @property
    def mode(self) -> Literal["live", "demo", "misconfigured"]:
        if self.MODEL_PROVIDER == "demo":
            return "demo"
        if self.MODEL_PROVIDER == "google_ai" and not self.api_key:
            return "misconfigured"
        return "live"

    @property
    def ready(self) -> bool:
        try:
            for directory in (self.UPLOAD_DIR, self.OUTPUT_DIR, self.TEMP_DIR):
                directory.mkdir(parents=True, exist_ok=True)
                test_file = directory / ".write_test"
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink(missing_ok=True)
            try:
                free_mb = shutil.disk_usage(self.BASE_DIR).free // (1024 * 1024)
                if free_mb < self.MIN_FREE_MB:
                    return False
            except OSError:
                pass
            return self.mode != "misconfigured"
        except OSError:
            return False


settings = Settings()
for directory in (settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.TEMP_DIR, settings.DATA_DIR, settings.JOBS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
