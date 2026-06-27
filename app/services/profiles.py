"""Run profiles — compose the agent team like an engineering org.

A profile assigns a model to each pipeline stage (a strong supervisor can run on
a stronger model than the junior sub-agents) and decides whether the Critic→
Architect review-and-rework loop runs. Slot keys are the four pipeline STAGE
names so /step can map a stage straight to its model. Six stages in total.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.services.config import Settings

ROLES = ("requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critique")


class RunProfile(BaseModel):
    name: str
    models: dict[str, str]      # stage name -> model
    rework: bool = False
    max_rounds: int = 2         # total review rounds (1 initial + up to max_rounds-1 reworks)


def uniform_profile(name: str, model: str) -> RunProfile:
    return RunProfile(name=name, models={r: model for r in ROLES}, rework=False, max_rounds=1)


PROFILES: dict[str, RunProfile] = {
    "Uniform qwen-plus": uniform_profile("Uniform qwen-plus", "qwen-plus"),
    "Uniform qwen-max": uniform_profile("Uniform qwen-max", "qwen-max"),
    "Budget Turbo": uniform_profile("Budget Turbo", "qwen-turbo"),
    "Senior Review Team": RunProfile(
        name="Senior Review Team",
        models={
            "requirements": "qwen-plus",
            "architecture": "qwen-plus",
            "critique": "qwen-max",
            "arbitration": "qwen-max",
            "pcb_engineer": "qwen-plus",
            "pcb_critique": "qwen-max",
        },
        rework=True,
        max_rounds=2,
    ),
}


def default_profile(settings: Settings) -> RunProfile:
    """Uniform profile on the configured default model (today's single-model behaviour)."""
    return uniform_profile(f"Uniform {settings.qwen_model}", settings.qwen_model)


def resolve_profile(name: str | None, settings: Settings) -> RunProfile:
    """Look up a named profile and sanitise every model slot through the allowlist.
    Unknown name -> the uniform default profile."""
    profile = PROFILES.get(name) if name else None
    if profile is None:
        return default_profile(settings)
    models = {role: settings.resolve_model(m) for role, m in profile.models.items()}
    return profile.model_copy(update={"models": models})


def profile_for(name: str | None, model: str | None, settings: Settings) -> RunProfile:
    """Resolve a request to a profile: a named profile wins; else a uniform profile
    from a single model; else the default. All models pass the allowlist."""
    if name:
        return resolve_profile(name, settings)
    if model:
        m = settings.resolve_model(model)
        return uniform_profile(f"Uniform {m}", m)
    return default_profile(settings)
