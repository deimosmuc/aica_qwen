"""Stepwise pipeline: one agent stage at a time (mock mode)."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.models.schemas import StepRequest, StepResponse
from app.services.config import Settings
from app.services.stepwise import run_stage

TEXT = "A 24V industrial board with an STM32, USB-C and RS485."
STAGES = ["requirements", "architecture", "critique", "arbitration"]


def _mock_settings():
    return Settings(qwen_api_key="")


def test_each_stage_returns_its_output():
    settings = _mock_settings()
    for stage in STAGES:
        resp = run_stage(StepRequest(stage=stage, requirements_text=TEXT), settings)
        assert isinstance(resp, StepResponse)
        assert resp.stage == stage
        assert resp.mode == "mock"
        assert resp.trace_step.agent
        # Exactly the field for this stage is populated.
        assert getattr(resp, stage) is not None
        others = [s for s in STAGES if s != stage]
        assert all(getattr(resp, o) is None for o in others)


def test_step_endpoint_walks_the_pipeline(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: _mock_settings())
    client = TestClient(app)

    # Stage 1
    r1 = client.post("/api/step", json={"stage": "requirements", "requirements_text": TEXT})
    assert r1.status_code == 200
    reqs = r1.json()["requirements"]
    assert reqs is not None

    # Stage 4 carrying prior results forward (mirrors the client-driven flow).
    arch = client.post(
        "/api/step", json={"stage": "architecture", "requirements_text": TEXT, "requirements": reqs}
    ).json()["architecture"]
    crit = client.post(
        "/api/step",
        json={"stage": "critique", "requirements_text": TEXT, "requirements": reqs, "architecture": arch},
    ).json()["critique"]
    r4 = client.post(
        "/api/step",
        json={
            "stage": "arbitration",
            "requirements_text": TEXT,
            "requirements": reqs,
            "architecture": arch,
            "critique": crit,
        },
    )
    assert r4.status_code == 200
    assert r4.json()["arbitration"] is not None
    assert r4.json()["trace_step"]["role"]
