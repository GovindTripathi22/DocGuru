from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application settings
    APP_NAME: str = "Exact Template Inheritance Generator"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # AI Model Configuration (Default: Local GPU-accelerated Gemma)
    MODEL_PROVIDER: str = Field(default="ollama", description="ollama, google_ai, or openai_compat")
    MODEL_NAME: str = Field(default="gemma2:2b", description="Gemma model variant (e.g. gemma2:2b, gemma4:e4b, gemma4:12b)")
    MODEL_ENDPOINT: str = Field(default="http://127.0.0.1:11434", description="API endpoint")
    GEMMA_API_KEY: str = Field(default="", description="API Key for Google AI Studio / Gemini / Provider")
    GEMINI_API_KEY: str = Field(default="", description="Alternative API Key env var")
    TEMPERATURE: float = Field(default=0.2, description="Sampling temperature for deterministic template-guided planning")
    MAX_TOKENS: int = Field(default=2048, description="Maximum token generation limit")
    OFFLINE_MODE: bool = Field(default=False, description="Offline resilience mode; bypasses external network calls")

    # Storage paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    TEMP_DIR: Path = BASE_DIR / "temp"

    @property
    def api_key(self) -> str:
        return self.GEMMA_API_KEY or self.GEMINI_API_KEY or os.environ.get("GEMMA_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")

settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
