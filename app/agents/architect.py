"""System Architect Agent — role: Principal Hardware Architect.

Takes the structured requirements and proposes a hardware architecture:
functional blocks (one per hierarchical sheet), interfaces, major signals,
power domains and placeholder components. It prepares engineering work; it
never makes final component decisions.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block, original_request_block, revision_block
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
- "blocks": array of objects, each {"name": str, "sheet": str, "purpose": str,
  "category": one of "mcu" | "sensor" | "power" | "connectivity" | "debug" | "status" | "other"}
  where "sheet" is a lowercase filename ending in ".kicad_sch". Assign exactly one
  category per block; protection (fuse, reverse-polarity, TVS/ESD) counts as "power";
  use "other" only when nothing fits.
- "interfaces": array of strings
- "signals": array of strings (net names, e.g. "USB_D+", "RS485_A")
- "power": array of strings (power-rail net names, e.g. "VIN_24V", "+3V3", "GND")
- "placeholder_components": array of strings (DUMMY_* names)
- "connections": array of objects, each {"source": block name, "target": block name,
  "type": one of "power" | "data" | "control" | "debug"} describing how the blocks
  link up. "source" and "target" MUST be names that appear in "blocks". Use "power"
  for supply rails, "data" for buses/interfaces, "control" for control/enable lines,
  "debug" for programming/debug links.
- "notes": array of strings
"""


class SystemArchitectAgent:
    name = NAME
    role = ROLE

    def run(
        self,
        client: ChatClient,
        requirements: Requirements,
        guidance: list[str] | None = None,
        *,
        original_request: str | None = None,
        revisions: list[str] | None = None,
    ) -> Architecture:
        user = (
            "Design the hardware architecture for these structured requirements.\n\n"
            + requirements.model_dump_json(indent=2)
            + original_request_block(original_request)
            + revision_block(revisions)
            + guidance_block(guidance)
        )
        data = client.chat_json(SYSTEM_PROMPT, user)
        return Architecture.model_validate(data)
