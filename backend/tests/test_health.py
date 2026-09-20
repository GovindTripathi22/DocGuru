import pytest
from fastapi.testclient import TestClient
from unittest.mock import PropertyMock, patch

from backend.app.main import app
from backend.app.config import Settings


def test_health_live_endpoint():
    client = TestClient(app)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_ready_endpoint():
    client = TestClient(app)
    with patch.object(Settings, "ready", new_callable=PropertyMock, return_value=True), \
         patch.object(Settings, "mode", new_callable=PropertyMock, return_value="live"):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True
        assert resp.json()["mode"] == "live"

    with patch.object(Settings, "ready", new_callable=PropertyMock, return_value=False), \
         patch.object(Settings, "mode", new_callable=PropertyMock, return_value="misconfigured"):
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.json()["ready"] is False
        assert resp.json()["mode"] == "misconfigured"


def test_api_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "version" in data
    assert "model_provider" in data
    assert "model_name" in data
    assert "mode" in data
    assert "ready" in data
    assert "time" in data
    assert "capabilities" in data
    assert isinstance(data["capabilities"], dict)
