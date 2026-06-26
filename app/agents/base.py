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
