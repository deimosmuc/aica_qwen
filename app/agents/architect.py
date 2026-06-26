"""System Architect Agent — role: Principal Hardware Architect.

Takes the structured requirements and proposes a hardware architecture:
functional blocks (one per hierarchical sheet), interfaces, major signals,
power domains and placeholder components. It prepares engineering work; it
never makes final component decisions.
"""
from __future__ import annotations

from app.agents.base import ChatClient
from app.models.schemas import Architecture, Requirements

NAME = "System Architect"
ROLE = "Principal Hardware Architect"

SYSTEM_PROMPT = """You are a principal hardware architect.

You receive structured engineering requirements and design the hardware
architecture as a hierarchical KiCad project would be organised. You never
fabricate electronics knowledge or invent specifications.

Rules:
- Identify functional blocks; each block maps to one hierarchical sheet.
- Identify interfaces, major signals and power domains.
- Recommend PLACEHOLDER components only (names like DUMMY_MCU, DUMMY_USB_C).
- Never generate resistor values or capacitor sizing.
- Never select final ICs unless the requirements explicitly ask for a part.
- Where something is uncertain, add a short note instead of guessing.

Output a JSON object with exactly these keys:
- "blocks": array of objects, each {"name": str, "sheet": str, "purpose": str}
  where "sheet" is a lowercase filename ending in ".kicad_sch"
- "interfaces": array of strings
- "signals": array of strings (net names, e.g. "USB_D+", "RS485_A")
- "power": array of strings (power-rail net names, e.g. "VIN_24V", "+3V3", "GND")
- "placeholder_components": array of strings (DUMMY_* names)
- "notes": array of strings
"""


class SystemArchitectAgent:
    name = NAME
    role = ROLE

    def run(self, client: ChatClient, requirements: Requirements) -> Architecture:
        user = (
            "Design the hardware architecture for these structured requirements.\n\n"
            + requirements.model_dump_json(indent=2)
        )
        data = client.chat_json(SYSTEM_PROMPT, user)
        return Architecture.model_validate(data)
