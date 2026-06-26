"""Orchestrator: per-role model wiring + behaviour preservation."""
from app.services.config import Settings
from app.services.orchestrator import Orchestrator
from app.services.profiles import PROFILES


def test_client_per_role_uses_profile_model():
    orch = Orchestrator(Settings(qwen_api_key="sk-test"), profile=PROFILES["Senior Review Team"])
    assert orch._client_for("critique")._model == "qwen-max"
    assert orch._client_for("arbitration")._model == "qwen-max"
    assert orch._client_for("architecture")._model == "qwen-plus"


def test_default_profile_is_uniform():
    s = Settings(qwen_api_key="sk-test")
    orch = Orchestrator(s)
    assert orch._client_for("critique")._model == s.qwen_model


def test_mock_mode_pipeline_unchanged():
    out = Orchestrator(Settings(qwen_api_key="")).run("a 24V board")
    assert out.mode == "mock"
    assert len(out.trace) == 4
    assert all(s.round == 1 for s in out.trace)
