"""Model allowlist resolution on Settings."""
from app.services.config import Settings


def test_resolve_model_passes_through_allowed():
    s = Settings()
    assert s.resolve_model("qwen-max") == "qwen-max"
    assert s.resolve_model("qwen-turbo") == "qwen-turbo"


def test_resolve_model_falls_back_for_unknown_or_empty():
    s = Settings()
    assert s.resolve_model("gpt-4") == s.qwen_model
    assert s.resolve_model(None) == s.qwen_model
    assert s.resolve_model("") == s.qwen_model
