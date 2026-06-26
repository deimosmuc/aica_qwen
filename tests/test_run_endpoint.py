"""The /api/run endpoint threads an optional model override into the Orchestrator."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.services.mock import mock_run


def _fake_orch_capturing(captured):
    class FakeOrch:
        def __init__(self, settings):
            captured["model"] = settings.qwen_model

        def run(self, text, guidance=None):
            return mock_run(text)

    return FakeOrch


def test_run_applies_allowlisted_model(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "model": "qwen-max"})
    assert r.status_code == 200
    assert captured["model"] == "qwen-max"


def test_run_unknown_model_falls_back_to_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "model": "gpt-4"})
    assert r.status_code == 200
    assert captured["model"] == "qwen-plus"  # the default
