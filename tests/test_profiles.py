"""Run-profile registry and resolution."""
from app.services.config import Settings
from app.services.profiles import (
    PROFILES,
    default_profile,
    profile_for,
    resolve_profile,
)


def test_senior_review_team_assigns_max_to_supervisor():
    p = PROFILES["Senior Review Team"]
    assert p.models["critique"] == "qwen-max"
    assert p.models["arbitration"] == "qwen-max"
    assert p.models["architecture"] == "qwen-plus"
    assert p.rework is True and p.max_rounds == 2


def test_resolve_profile_unknown_name_falls_back_to_default():
    s = Settings()
    p = resolve_profile("does-not-exist", s)
    assert all(m == s.qwen_model for m in p.models.values())
    assert p.rework is False


def test_resolve_profile_sanitises_models_through_allowlist(monkeypatch):
    s = Settings()
    bad = PROFILES["Senior Review Team"].model_copy(
        update={"models": {**PROFILES["Senior Review Team"].models, "critique": "gpt-4"}}
    )
    monkeypatch.setitem(PROFILES, "Bad", bad)
    p = resolve_profile("Bad", s)
    assert p.models["critique"] == s.qwen_model


def test_profile_for_uniform_model():
    s = Settings()
    p = profile_for(None, "qwen-max", s)
    assert all(m == "qwen-max" for m in p.models.values())
    assert p.rework is False


def test_profile_for_unknown_model_defaults():
    s = Settings()
    p = profile_for(None, "gpt-4", s)
    assert all(m == s.qwen_model for m in p.models.values())


def test_guard_cap_raised_for_rework_headroom():
    assert Settings().guard_max_calls_per_run == 12
