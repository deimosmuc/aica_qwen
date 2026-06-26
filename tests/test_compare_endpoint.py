# tests/test_compare_endpoint.py
"""The /api/compare endpoint."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.services.config import Settings


def test_compare_endpoint_mock(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))
    client = TestClient(app)
    resp = client.post("/api/compare", json={"requirements_text": "A 24V STM32 board with RS485."})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 12
    assert len(data["concerns"]) == 12
    assert data["multi_score"] > data["single_score"]
    assert data["mode"] == "mock"
