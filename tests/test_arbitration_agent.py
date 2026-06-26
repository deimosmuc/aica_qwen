"""Milestone 5: the Arbitration Agent (Chief Engineer)."""
from app.agents.arbitration import ArbitrationAgent
from app.models.schemas import Arbitration, Architecture, Block, Critique, Requirements


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat_json(self, system, user, model=None):
        self.calls.append({"system": system, "user": user})
        return self.payload


ARB = {
    "todo": ["TODO: Add DUMMY_TVS surge protection on VIN_24V."],
    "human_review": ["NEEDS HUMAN REVIEW: RS485 isolation decision."],
    "accepted_assumptions": ["24 V -> 5 V -> 3V3 cascaded power architecture"],
}

REQS = Requirements(
    requirements=["24 V supply", "RS485"],
    assumptions=["ASSUMPTION: 24 V -> 5 V -> 3V3 cascaded power architecture"],
    confidence=0.7,
)

ARCH = Architecture(
    blocks=[Block(name="Power", sheet="power.kicad_sch", purpose="24V -> 5V/3V3")],
    power=["VIN_24V", "+5V", "GND"],
    placeholder_components=["DUMMY_POWER_STAGE"],
)

CRIT = Critique(
    warnings=["No surge protection shown on VIN_24V."],
    risks=["RS485 without isolation may be insufficient on a noisy bus."],
    missing_blocks=["DUMMY_CLOCK in the MCU block"],
    recommendations=["Add a TVS/surge placeholder on the 24V input."],
)


def test_arbitration_parses_valid_result():
    client = FakeClient(ARB)
    result = ArbitrationAgent().run(client, REQS, ARCH, CRIT)
    assert isinstance(result, Arbitration)
    assert result.todo == ["TODO: Add DUMMY_TVS surge protection on VIN_24V."]
    assert result.human_review
    assert result.accepted_assumptions


def test_arbitration_approves_the_architect_architecture():
    # The arbitrator decides TODOs / review items; it does NOT redesign.
    # The approved architecture must be exactly the architect's output, even if
    # the model omits or mangles it in its JSON reply.
    client = FakeClient({**ARB, "approved_architecture": {"blocks": [], "power": []}})
    result = ArbitrationAgent().run(client, REQS, ARCH, CRIT)
    assert result.approved_architecture == ARCH


def test_arbitration_receives_all_three_inputs():
    client = FakeClient(ARB)
    ArbitrationAgent().run(client, REQS, ARCH, CRIT)
    sent = client.calls[0]["user"]
    assert "RS485" in sent          # requirements
    assert "VIN_24V" in sent        # architecture
    assert "surge protection" in sent  # critique
