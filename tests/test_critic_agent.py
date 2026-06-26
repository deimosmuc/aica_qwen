"""Milestone 4: the Design Critic Agent."""
from app.agents.critic import DesignCriticAgent
from app.models.schemas import Architecture, Block, Critique, Requirements


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat_json(self, system, user, model=None):
        self.calls.append({"system": system, "user": user})
        return self.payload


CRIT = {
    "warnings": ["No surge protection shown on VIN_24V."],
    "risks": ["RS485 without isolation may be insufficient on a noisy bus."],
    "missing_blocks": ["DUMMY_CLOCK in the MCU block"],
    "recommendations": ["Add a TVS/surge placeholder on the 24V input."],
}

REQS = Requirements(requirements=["24 V supply", "RS485"], confidence=0.7)

ARCH = Architecture(
    blocks=[Block(name="Power", sheet="power.kicad_sch", purpose="24V -> 5V/3V3")],
    power=["VIN_24V", "+5V", "GND"],
    placeholder_components=["DUMMY_POWER_STAGE"],
)


def test_critic_parses_valid_critique():
    client = FakeClient(CRIT)
    result = DesignCriticAgent().run(client, REQS, ARCH)
    assert isinstance(result, Critique)
    assert result.missing_blocks == ["DUMMY_CLOCK in the MCU block"]
    assert result.recommendations


def test_critic_receives_requirements_and_architecture():
    client = FakeClient(CRIT)
    DesignCriticAgent().run(client, REQS, ARCH)
    sent = client.calls[0]["user"]
    # Both the requirements and the architecture must reach the critic.
    assert "RS485" in sent
    assert "VIN_24V" in sent
    assert "power.kicad_sch" in sent
