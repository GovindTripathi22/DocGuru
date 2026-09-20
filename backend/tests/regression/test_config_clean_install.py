from pathlib import Path

import pytest


@pytest.mark.xfail(strict=True, reason="CFG-01: Ollama is an undeclared runtime dependency")
def test_llm_client_has_no_undeclared_ollama_import():
    source = (Path(__file__).parents[2] / "app" / "ai" / "gemma_client.py").read_text(encoding="utf-8")
    assert "import ollama" not in source
