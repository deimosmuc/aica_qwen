"""Architect emits a functional category per block (Smart Diagrams Phase 1)."""
from app.agents.architect import SystemArchitectAgent, SYSTEM_PROMPT
from app.models.schemas import Requirements


class _StubClient:
    def __init__(self, payload):
        self._p = payload

    def chat_json(self, system, user):
        return self._p


def test_architect_prompt_requests_category():
    assert "category" in SYSTEM_PROMPT.lower()


def test_architect_parses_block_category():
    payload = {
        "blocks": [{"name": "MCU", "sheet": "mcu.kicad_sch", "purpose": "core", "category": "mcu"}],
        "interfaces": [], "signals": [], "power": [], "placeholder_components": [],
        "connections": [], "notes": [],
    }
    arch = SystemArchitectAgent().run(_StubClient(payload), Requirements())
    assert arch.blocks[0].category == "mcu"


def test_architect_missing_category_defaults_other():
    payload = {
        "blocks": [{"name": "X", "sheet": "x.kicad_sch", "purpose": "p"}],
        "interfaces": [], "signals": [], "power": [], "placeholder_components": [],
        "connections": [], "notes": [],
    }
    arch = SystemArchitectAgent().run(_StubClient(payload), Requirements())
    assert arch.blocks[0].category == "other"
