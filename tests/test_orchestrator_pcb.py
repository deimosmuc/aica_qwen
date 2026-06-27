"""Integration-level tests for the PCB stage in the orchestrator."""
import json
from unittest.mock import MagicMock

import pytest

from app.models.schemas import RunResponse
from app.services.orchestrator import Orchestrator
from app.services.config import Settings
from app.services.profiles import uniform_profile


def _pcb_response() -> dict:
    return {
        "layerstack": "4-layer",
        "layerstack_reason": "RS485 isolation required",
        "netclasses": [
            {"name": "PWR", "min_width_mm": 0.5, "clearance_mm": 0.3, "nets": ["GND", "+3.3V"]},
            {"name": "Signal", "min_width_mm": 0.2, "clearance_mm": 0.2, "nets": []},
        ],
        "constraints": {
            "min_clearance_mm": 0.2,
            "min_track_width_mm": 0.2,
            "via_drill_mm": 0.4,
            "via_annular_ring_mm": 0.15,
        },
        "floorplan_text": "MCU central, RS485 near connector.",
        "floorplan_ascii": "[MCU] [RS485]\n[PWR]",
        "package_hints": [
            {"component_type": "MCU", "recommended_package": "LQFP-64", "reason": "hand-solderable"},
        ],
    }


def _clean_critique() -> dict:
    return {"missing_blocks": [], "warnings": [], "risks": []}


def _make_client(seq: list[dict]) -> MagicMock:
    """Return a mock ChatClient that returns items from seq in order."""
    mock = MagicMock()
    mock.chat_json.side_effect = seq
    return mock


def _settings() -> Settings:
    return Settings(qwen_api_key="test", mock_mode=False)


# ---- existing agents return values (needed to mock all 5 stages) ----

def _requirements_response() -> dict:
    return {
        "requirements": ["24V input", "STM32 MCU"],
        "constraints": ["Industrial"],
        "questions": [],
        "assumptions": [],
        "confidence": 0.9,
        "clarifications": [],
    }


def _architecture_response() -> dict:
    return {
        "blocks": [{"name": "MCU", "sheet": "main", "purpose": "Control"}],
        "interfaces": ["RS485"],
        "signals": ["TX", "RX"],
        "power": ["+3.3V", "GND"],
        "placeholder_components": [],
        "connections": [],
        "notes": [],
    }


def _critique_response(missing: list[str] | None = None) -> dict:
    return {
        "warnings": [],
        "risks": [],
        "missing_blocks": missing or [],
        "recommendations": [],
    }


def _arbitration_response() -> dict:
    return {
        "approved_architecture": _architecture_response(),
        "todo": ["TODO: add TVS diode"],
        "human_review": [],
        "accepted_assumptions": [],
    }


def test_pcb_stage_runs_and_returns_pcb_readiness():
    """Full mock run: all 5 stages complete, pcb_readiness populated."""
    seq = [
        _requirements_response(),
        _architecture_response(),  # arch round 1
        _critique_response(),      # critic round 1 — clean
        _arbitration_response(),   # arbitration
        _pcb_response(),           # pcb_engineer round 1
        _clean_critique(),         # pcb_critic round 1 — clean
    ]
    client = _make_client(seq)
    orch = Orchestrator(_settings(), client=client)
    result = orch.run("Build RS485 interface")
    assert isinstance(result, RunResponse)
    assert result.pcb_readiness is not None
    assert result.pcb_readiness.layerstack == "4-layer"


def test_pcb_stage_trace_has_pcb_steps():
    """TraceStep list must include PCB Engineer and PCB Critic steps."""
    seq = [
        _requirements_response(),
        _architecture_response(),
        _critique_response(),
        _arbitration_response(),
        _pcb_response(),
        _clean_critique(),
    ]
    client = _make_client(seq)
    orch = Orchestrator(_settings(), client=client)
    result = orch.run("Build RS485 interface")
    agent_names = [s.agent for s in result.trace]
    assert "PCB Engineer" in agent_names
    assert "PCB Critic" in agent_names


def test_pcb_rework_loop():
    """PCB rework: round 1 critic flags missing_blocks, round 2 passes."""
    seq = [
        _requirements_response(),
        _architecture_response(),
        _critique_response(),
        _arbitration_response(),
        _pcb_response(),                              # pcb_engineer round 1
        {"missing_blocks": ["via too small"], "warnings": [], "risks": []},  # pcb_critic flags
        _pcb_response(),                              # pcb_engineer round 2 (rework)
        _clean_critique(),                            # pcb_critic round 2 — clean
    ]
    client = _make_client(seq)
    profile = uniform_profile("test", "qwen-turbo")
    profile = profile.model_copy(update={"rework": True, "max_rounds": 3})
    orch = Orchestrator(_settings(), profile=profile, client=client)
    result = orch.run("Build RS485 interface")
    pcb_steps = [s for s in result.trace if s.agent == "PCB Engineer"]
    assert len(pcb_steps) == 2  # round 1 + rework round 2
