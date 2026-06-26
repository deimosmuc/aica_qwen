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
