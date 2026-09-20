import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_settings_default_provider_and_model():
    s = Settings(_env_file=None, GEMINI_API_KEY="test-key")
    assert s.MODEL_PROVIDER == "google_ai"
    assert s.MODEL_NAME == "gemma-4-31b-it"
    assert s.MODEL_ENDPOINT == "https://generativelanguage.googleapis.com/v1beta"
    assert s.mode == "live"
    assert s.ready is True


def test_settings_invalid_provider_raises_validation_error():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, MODEL_PROVIDER="unsupported_provider")


def test_settings_demo_mode_requires_explicit_value():
    s = Settings(_env_file=None, MODEL_PROVIDER="demo")
    assert s.mode == "demo"
    assert s.ready is True
    assert s.MODEL_ENDPOINT == ""


def test_settings_misconfigured_mode_when_key_missing():
    s = Settings(_env_file=None, MODEL_PROVIDER="google_ai", GEMINI_API_KEY="", GEMMA_API_KEY="")
    assert s.mode == "misconfigured"
    assert s.ready is False


def test_settings_gemma_api_key_deprecated_alias(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        s = Settings(_env_file=None, MODEL_PROVIDER="google_ai", GEMINI_API_KEY="", GEMMA_API_KEY="legacy-key")
        assert s.api_key == "legacy-key"
        assert s.mode == "live"
        assert any("deprecated" in record.message for record in caplog.records)


def test_settings_wildcard_cors_rejected():
    with pytest.raises(ValidationError, match="CORS_ORIGINS must name explicit origins"):
        Settings(_env_file=None, CORS_ORIGINS="*")


def test_settings_provider_endpoints():
    s_ollama = Settings(_env_file=None, MODEL_PROVIDER="ollama")
    assert s_ollama.MODEL_ENDPOINT == "http://127.0.0.1:11434"

    s_openai = Settings(_env_file=None, MODEL_PROVIDER="openai_compat")
    assert s_openai.MODEL_ENDPOINT == "http://127.0.0.1:8001"
