# tests/test_baseline_agent.py
"""The single-agent baseline (one fair, high-level call)."""
from app.agents.baseline import SingleAgentBaseline
from app.models.schemas import BaselineResult


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat_json(self, system, user, model=None):
        self.calls.append({"system": system, "user": user})
        return self.payload


PAYLOAD = {
    "architecture": ["MCU block", "Power 24V->5V->3V3"],
    "concerns": ["Check current budget"],
    "todos": ["TODO: pick STM32 variant"],
    "human_review": [],
    "assumptions": ["Assumption: single board"],
    "notes": ["SWD for programming"],
}


def test_baseline_parses_result():
    client = FakeClient(PAYLOAD)
    result = SingleAgentBaseline().run(client, "A 24V STM32 board")
    assert isinstance(result, BaselineResult)
    assert result.architecture == ["MCU block", "Power 24V->5V->3V3"]
    assert result.assumptions


def test_baseline_prompt_demands_high_level_json():
    client = FakeClient(PAYLOAD)
    SingleAgentBaseline().run(client, "A 24V STM32 board")
    system = client.calls[0]["system"].lower()
    assert "json" in system           # required for Qwen json_object mode
    assert "placeholder" in system    # stays high-level, no real parts
