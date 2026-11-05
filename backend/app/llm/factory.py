"""Factory function to resolve and instantiate the active LLMProvider."""

from ..config import settings
from .base import LLMProvider
from .demo import DemoProvider
from .google_ai import GoogleAIProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    name = (provider_name or settings.MODEL_PROVIDER).lower().strip()
    if name == "demo":
        return DemoProvider()
    elif name == "google_ai":
        return GoogleAIProvider()
    elif name == "ollama":
        return OllamaProvider()
    elif name == "openai_compat":
        return OpenAICompatProvider()
    else:
        raise ValueError(
            f"Unknown LLM provider: '{name}'. Supported: google_ai, ollama, openai_compat, demo."
        )
