"""User persona → prompt instruction + display label.

A persona re-tones every agent's output. It rides the existing ``guidance`` channel
(routes.py prepends ``persona_instruction(...)``), so no agent signature changes. Pure
and deterministic; unknown / missing personas fall back to "professional".
"""
from __future__ import annotations

from typing import Literal

Persona = Literal["professional", "student", "maker"]

_DEFAULT: str = "professional"

PERSONA_INSTRUCTIONS: dict[str, str] = {
    "professional": ("Audience: a professional hardware engineer. Be concise and "
                     "technical, assume EE fluency, reference relevant standards / best "
                     "practices, minimal hand-holding."),
    "student": ("Audience: an engineering student. Explain reasoning and trade-offs in "
                "teaching terms, define jargon on first use, favour clarity over brevity."),
    "maker": ("Audience: a hobbyist maker. Be practical and DIY-friendly, prefer "
              "accessible low-cost widely-available parts, use plain language, flag where "
              "a simpler approach suffices."),
}

PERSONA_LABELS: dict[str, str] = {
    "professional": "Professional", "student": "Student", "maker": "Maker",
}


def resolve_persona(persona: str | None) -> str:
    """Return a valid persona key; unknown / None -> the default ("professional")."""
    return persona if persona in PERSONA_INSTRUCTIONS else _DEFAULT


def persona_instruction(persona: str | None) -> str:
    """The audience instruction string for the resolved persona."""
    return PERSONA_INSTRUCTIONS[resolve_persona(persona)]


def persona_label(persona: str | None) -> str:
    """The display label for the resolved persona."""
    return PERSONA_LABELS[resolve_persona(persona)]
