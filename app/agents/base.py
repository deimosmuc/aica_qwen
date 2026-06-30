"""Shared protocol for agents.

Every agent is stateless: it takes a Qwen client and a payload, calls the
model once, and returns a validated JSON contract. The orchestrator owns all
state and decides the order in which agents run.
"""
from __future__ import annotations

from typing import Protocol


class ChatClient(Protocol):
    """Minimal interface agents depend on (real QwenClient or a test fake)."""

    def chat_json(self, system: str, user: str, model: str | None = None) -> dict: ...


def guidance_block(guidance: list[str] | None) -> str:
    """Render the human's hard constraints as a prompt block every agent honors.

    These are non-negotiable user directives (e.g. a company-mandated or
    legally-required component). Appended to an agent's user message so the model
    sees them in context and must not contradict them.
    """
    if not guidance:
        return ""
    items = "\n".join(f"- {g}" for g in guidance if g and g.strip())
    if not items:
        return ""
    return (
        "\n\nMANDATORY USER CONSTRAINTS — hard requirements (e.g. company policy or "
        "regulation). You MUST honor these exactly and never contradict them:\n" + items
    )


def original_request_block(text: str | None) -> str:
    """Render the user's verbatim request as context for downstream agents.

    Only the Requirements agent sees the raw request directly; every later agent
    otherwise works off the structured Requirements object. Carrying the original
    words along keeps detail and intent that the structuring step may have
    generalised away — so nothing the user wrote silently disappears mid-pipeline.
    """
    if not text or not text.strip():
        return ""
    return (
        "\n\nORIGINAL USER REQUEST (verbatim — the user's own words. The structured "
        "requirements above are derived from this; stay faithful to its intent and "
        "detail, and do not drop specifics it mentions):\n" + text.strip()
    )


def revision_block(revisions: list[str] | None) -> str:
    """Render soft revision requests from a prior result.

    These are changes the user asked for after reviewing an earlier run (or a
    course-correction between steps). Unlike guidance_block's hard constraints,
    they are preferences to apply — honored unless they conflict with the
    MANDATORY USER CONSTRAINTS.
    """
    if not revisions:
        return ""
    items = "\n".join(f"- {r}" for r in revisions if r and r.strip())
    if not items:
        return ""
    return (
        "\n\nREVISION REQUESTS — the user reviewed an earlier result and asked for "
        "these changes. Apply them unless they conflict with the MANDATORY USER "
        "CONSTRAINTS:\n" + items
    )
