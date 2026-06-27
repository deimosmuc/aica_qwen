"""Milestone 1 verification: the scaffold runs end-to-end in Mock Mode."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.config import Settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_mock_mode(monkeypatch):
    """Pin these checks to Mock Mode regardless of any real QWEN_API_KEY in the
    developer's .env. The init kwarg outranks env vars and the .env file, so the
    app reports/uses mock mode here even when a live key is configured locally."""
    mock_settings = Settings(qwen_api_key="")
    monkeypatch.setattr("app.api.routes.get_settings", lambda: mock_settings)


def test_health_reports_mock_mode_without_api_key():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "mock"  # no QWEN_API_KEY configured in the test env


def test_index_page_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "AI Circuit Architect" in r.text


def test_run_returns_full_pipeline():
    r = client.post("/api/run", json={"requirements_text": "24V sensor board with STM32 and RS485"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "mock"
    assert body["needs_approval"] is True
    # The agent trace must show all six collaborating agents (arch + PCB).
    assert len(body["trace"]) == 6
    # Architecture must carry hierarchical blocks and power domains.
    assert len(body["architecture"]["blocks"]) >= 4
    assert "VIN_24V" in body["architecture"]["power"]
    # Honest engineering: open items must be surfaced, not hidden.
    assert body["arbitration"]["human_review"]


def test_run_requires_requirements_text():
    r = client.post("/api/run", json={})
    assert r.status_code == 422
