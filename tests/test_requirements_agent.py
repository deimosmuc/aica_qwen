"""Milestone 2: the Requirements Agent and orchestrator wiring.

These tests use a fake Qwen client so they are deterministic and need no
network or API key. The live call is exercised separately via
tools/smoke_requirements.py.
"""
import pytest

from app.agents.requirements import RequirementsAgent
from app.models.schemas import Requirements
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.orchestrator import Orchestrator
from app.services.qwen_client import QwenError


class FakeClient:
    """Stand-in for QwenClient.

    `payload` may be a single dict (always returned), an Exception (raised), or
    a list of those returned in sequence (one per call).
    """

    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self._i = 0

    def chat_json(self, system, user, model=None):
        self.calls.append({"system": system, "user": user})
        p = self.payload
        if isinstance(p, list):
            p = p[min(self._i, len(p) - 1)]
            self._i += 1
        if isinstance(p, Exception):
            raise p
        return p


VALID = {
    "requirements": ["24 V supply", "STM32 MCU"],
    "constraints": ["single board"],
    "questions": ["Is RS485 isolation required?"],
    "assumptions": ["ASSUMPTION: SWD for debug"],
    "confidence": 0.7,
}

VALID_ARCH = {
    "blocks": [
        {"name": "Power", "sheet": "power.kicad_sch", "purpose": "24V -> 5V/3V3"},
        {"name": "MCU", "sheet": "mcu.kicad_sch", "purpose": "STM32 core"},
    ],
    "interfaces": ["USB-C", "RS485"],
    "signals": ["USB_D+", "RS485_A"],
    "power": ["VIN_24V", "+5V", "+3V3", "GND"],
    "placeholder_components": ["DUMMY_MCU", "DUMMY_RS485"],
    "notes": ["hierarchical design"],
}

VALID_CRIT = {
    "warnings": ["No surge protection on VIN_24V."],
    "risks": ["RS485 without isolation may be noisy."],
    "missing_blocks": ["DUMMY_CLOCK"],
    "recommendations": ["Add a TVS placeholder on the 24V input."],
}


def test_agent_parses_valid_json_into_requirements():
    client = FakeClient(VALID)
    result = RequirementsAgent().run(client, "A 24V board with an STM32")
    assert isinstance(result, Requirements)
    assert result.requirements == ["24 V supply", "STM32 MCU"]
    assert result.confidence == 0.7
    # The user's text must actually reach the model.
    assert "STM32" in client.calls[0]["user"]


def test_agent_appends_hard_constraints_to_prompt():
    client = FakeClient(VALID)
    RequirementsAgent().run(
        client, "A 24V board", guidance=["Must use the XYZ123 MCU (company policy)"]
    )
    sent = client.calls[0]["user"]
    assert "XYZ123" in sent
    assert "MANDATORY USER CONSTRAINTS" in sent


def test_agent_without_guidance_adds_no_constraint_block():
    client = FakeClient(VALID)
    RequirementsAgent().run(client, "A 24V board")
    assert "MANDATORY USER CONSTRAINTS" not in client.calls[0]["user"]


def test_agent_rejects_non_dict_payload():
    client = FakeClient(QwenError("bad json"))
    with pytest.raises(QwenError):
        RequirementsAgent().run(client, "anything")


def test_orchestrator_mock_mode_without_key():
    settings = Settings(qwen_api_key="")
    result = Orchestrator(settings).run("24V sensor board")
    assert result.mode == "mock"
    assert len(result.trace) == 4


VALID_ARB = {
    "approved_architecture": VALID_ARCH,
    "todo": ["TODO: verify RS485 isolation"],
    "human_review": [],
    "accepted_assumptions": [],
}

VALID_PCB = {
    "layerstack": "2-layer",
    "layerstack_reason": "simple board",
    "netclasses": [{"name": "Default", "min_width_mm": 0.2, "clearance_mm": 0.2, "nets": []}],
    "constraints": {"min_clearance_mm": 0.2, "min_track_width_mm": 0.2,
                    "via_drill_mm": 0.4, "via_annular_ring_mm": 0.15},
    "floorplan_text": "MCU central.",
    "floorplan_ascii": "[MCU]",
    "package_hints": [],
}

VALID_PCB_CRIT = {"missing_blocks": [], "warnings": [], "risks": []}


def test_orchestrator_qwen_mode_runs_three_live_agents():
    settings = Settings(qwen_api_key="test-key")  # non-empty -> qwen mode
    # req -> arch -> critic -> arbitration -> pcb_engineer -> pcb_critic
    client = FakeClient([VALID, VALID_ARCH, VALID_CRIT, VALID_ARB, VALID_PCB, VALID_PCB_CRIT])
    result = Orchestrator(settings, client=client).run("A 24V board with an STM32")
    assert result.mode == "qwen"
    # The live requirements replace the mock ones...
    assert result.requirements.requirements == ["24 V supply", "STM32 MCU"]
    # ...the live architecture is used...
    assert [b.name for b in result.architecture.blocks] == ["Power", "MCU"]
    # ...the live critique is used...
    assert result.critique.missing_blocks == ["DUMMY_CLOCK"]
    # ...arbitration is kept consistent with the real architecture...
    assert result.arbitration.approved_architecture.blocks[0].name == "Power"
    # ...and the trace marks the first three steps as the live ones.
    assert [s.agent for s in result.trace[:3]] == [
        "Requirements Agent",
        "System Architect",
        "Design Critic",
    ]
    # The critic found issues, so its step is a warning.
    assert result.trace[2].status == "warning"


def test_orchestrator_falls_back_to_mock_when_guard_blocks():
    settings = Settings(qwen_api_key="test-key")
    client = FakeClient(GuardBlocked("budget cap reached"))
    result = Orchestrator(settings, client=client).run("A 24V board with an STM32")
    # Guard blocked the live call -> example data with a clear notice, no charge.
    assert result.mode == "mock"
    assert result.notice is not None
    assert "budget" in result.notice.lower()


VALID_WITH_CLARIFY = {
    "requirements": ["24 V supply"],
    "constraints": [],
    "questions": [],
    "assumptions": [],
    "confidence": 0.6,
    "clarifications": [
        {
            "id": "power",
            "text": "Which power source?",
            "options": [
                {"label": "USB-C, 5V", "detail": "simple"},
                {"label": "Li-Ion + charger", "detail": "portable"},
            ],
            "select": "single",
            "assumption": "USB 5V",
        }
    ],
}


def test_agent_parses_clarifications():
    client = FakeClient(VALID_WITH_CLARIFY)
    result = RequirementsAgent().run(client, "a small board")
    assert len(result.clarifications) == 1
    q = result.clarifications[0]
    assert q.id == "power"
    assert q.select == "single"
    assert q.options[0].label == "USB-C, 5V"
    # questions backfilled from the clarification text
    assert result.questions == ["Which power source?"]
    # the prompt must instruct the model to produce options
    assert "clarifications" in client.calls[0]["system"]
