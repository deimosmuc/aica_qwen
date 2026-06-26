"""Milestone 3: the System Architect Agent."""
from app.agents.architect import SystemArchitectAgent
from app.models.schemas import Architecture, Requirements


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat_json(self, system, user, model=None):
        self.calls.append({"system": system, "user": user})
        return self.payload


ARCH = {
    "blocks": [
        {"name": "Power", "sheet": "power.kicad_sch", "purpose": "24V -> 5V/3V3"},
        {"name": "MCU", "sheet": "mcu.kicad_sch", "purpose": "STM32 core"},
        {"name": "RS485", "sheet": "rs485.kicad_sch", "purpose": "fieldbus transceiver"},
    ],
    "interfaces": ["USB-C", "RS485", "SWD"],
    "signals": ["USB_D+", "USB_D-", "RS485_A", "RS485_B"],
    "power": ["VIN_24V", "+5V", "+3V3", "GND"],
    "placeholder_components": ["DUMMY_MCU", "DUMMY_RS485", "DUMMY_POWER_STAGE"],
    "notes": ["Hierarchical design, one sheet per block."],
}

REQS = Requirements(
    requirements=["24 V supply", "STM32 MCU", "RS485 interface"],
    constraints=["single board"],
    questions=[],
    assumptions=["ASSUMPTION: SWD for debug"],
    confidence=0.7,
)


def test_architect_parses_valid_architecture():
    client = FakeClient(ARCH)
    result = SystemArchitectAgent().run(client, REQS)
    assert isinstance(result, Architecture)
    assert [b.name for b in result.blocks] == ["Power", "MCU", "RS485"]
    assert all(b.sheet.endswith(".kicad_sch") for b in result.blocks)
    assert "VIN_24V" in result.power


def test_architect_receives_the_requirements():
    client = FakeClient(ARCH)
    SystemArchitectAgent().run(client, REQS)
    # The structured requirements must actually be passed to the model.
    sent = client.calls[0]["user"]
    assert "STM32 MCU" in sent
    assert "RS485 interface" in sent
