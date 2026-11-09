import pytest
from backend.app.errors import LLMInvalidResponse
from backend.app.llm.json_repair import repair_and_parse_json


def test_repair_and_parse_valid_json():
    data = '{"title": "Overview", "paragraphs": ["First para", "Second para"]}'
    res = repair_and_parse_json(data)
    assert res == {"title": "Overview", "paragraphs": ["First para", "Second para"]}


def test_repair_and_parse_markdown_fences():
    data = '```json\n{"status": "ok", "count": 42}\n```'
    res = repair_and_parse_json(data)
    assert res == {"status": "ok", "count": 42}


def test_repair_and_parse_trailing_commas():
    data = '{"items": [1, 2, 3, ], "enabled": true, }'
    res = repair_and_parse_json(data)
    assert res == {"items": [1, 2, 3], "enabled": True}


def test_repair_and_parse_truncated_ollama_user_error():
    # Exact user error string reported:
    data = '{ "title": "Architecture and Methodology", "paragraphs": [ "Google\'s AlphaGo project marked a significant breakthrough in the field of artificial intelligence, achieving a level of mastery in'
    res = repair_and_parse_json(data, source_name="Ollama")
    assert isinstance(res, dict)
    assert res["title"] == "Architecture and Methodology"
    assert len(res["paragraphs"]) >= 1
    assert "Google's AlphaGo project" in res["paragraphs"][0]


def test_repair_and_parse_truncated_nested_arrays_and_objects():
    data = '{"sections": [{"title": "Sec 1", "subsections": [{"name": "Sub 1.1'
    res = repair_and_parse_json(data)
    assert isinstance(res, dict)
    assert "sections" in res
    assert res["sections"][0]["title"] == "Sec 1"
    assert res["sections"][0]["subsections"][0]["name"] == "Sub 1.1"


def test_repair_and_parse_empty_string_raises():
    with pytest.raises(LLMInvalidResponse):
        repair_and_parse_json("", source_name="Ollama")
