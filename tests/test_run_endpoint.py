"""The /api/run and /api/step endpoints resolve an optional profile / model."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.services.mock import mock_run


def _fake_orch_capturing(captured):
    class FakeOrch:
        def __init__(self, settings, profile=None, client=None):
            captured["profile"] = profile

        def run(self, text, guidance=None):
            return mock_run(text)

    return FakeOrch


def test_run_uniform_model_builds_uniform_profile(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "model": "qwen-max"})
    assert r.status_code == 200
    assert all(m == "qwen-max" for m in captured["profile"].models.values())
    assert captured["profile"].rework is False


def test_run_named_profile_assigns_per_role_models(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "profile": "Senior Review Team"})
    assert r.status_code == 200
    assert captured["profile"].models["critique"] == "qwen-max"
    assert captured["profile"].models["architecture"] == "qwen-plus"
    assert captured["profile"].rework is True


def test_run_unknown_profile_falls_back_to_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "profile": "nope"})
    assert r.status_code == 200
    assert captured["profile"].models["critique"] == "qwen-plus"  # default
    assert captured["profile"].rework is False


def test_step_uses_profile_model_for_its_stage(monkeypatch):
    from app.models.schemas import StepResponse, TraceStep
    captured = {}

    def fake_run_stage(req, settings):
        captured["model"] = settings.qwen_model
        return StepResponse(
            stage=req.stage, mode="qwen",
            trace_step=TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", summary="ok"),
        )

    monkeypatch.setattr(routes, "run_stage", fake_run_stage)
    client = TestClient(app)
    r = client.post("/api/step", json={"stage": "critique", "requirements_text": "x",
                                       "profile": "Senior Review Team"})
    assert r.status_code == 200
    assert captured["model"] == "qwen-max"  # the supervisor model for the critique stage


def test_step_pcb_critic_endpoint_resolves_model(monkeypatch):
    # Regression: /api/step looked up profile.models[stage], but the pcb_critic
    # stage maps to the "pcb_critique" model slot — must not KeyError.
    from app.services.config import Settings
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))
    client = TestClient(app)
    r = client.post("/api/step", json={"stage": "pcb_critic", "requirements_text": "x",
                                       "profile": "Senior Review Team"})
    assert r.status_code == 200
    assert r.json()["pcb_critique"] is not None


def test_run_prepends_persona_instruction_to_guidance(monkeypatch):
    captured = {}

    class FakeOrch:
        def __init__(self, settings, profile=None, client=None):
            pass

        def run(self, text, guidance=None):
            captured["guidance"] = guidance
            return mock_run(text)

    monkeypatch.setattr(routes, "Orchestrator", FakeOrch)
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "persona": "student",
                                      "guidance": ["Use part XYZ"]})
    assert r.status_code == 200
    g = captured["guidance"]
    assert "engineering student" in g[0].lower()
    assert g[1] == "Use part XYZ"


def test_step_prepends_persona_instruction(monkeypatch):
    from app.services.config import Settings
    captured = {}
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))

    def fake_run_stage(req, settings):
        captured["guidance"] = req.guidance
        from app.models.schemas import StepResponse, TraceStep
        return StepResponse(stage=req.stage, mode="mock",
                            trace_step=TraceStep(agent="Requirements Agent", role="r", summary="s"))

    monkeypatch.setattr(routes, "run_stage", fake_run_stage)
    client = TestClient(app)
    r = client.post("/api/step", json={"stage": "requirements", "requirements_text": "x",
                                       "persona": "maker", "guidance": ["keep it cheap"]})
    assert r.status_code == 200
    assert "hobbyist maker" in captured["guidance"][0].lower()
    assert captured["guidance"][1] == "keep it cheap"
