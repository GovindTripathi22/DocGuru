from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.app.main import app


def test_analyze_refuses_an_absolute_path_outside_storage(tmp_path: Path):
    sentinel = tmp_path / "outside.docx"
    Document().save(sentinel)

    response = TestClient(app).post("/api/analyze", json={"template_id": str(sentinel)})
    assert response.status_code in {400, 404}
