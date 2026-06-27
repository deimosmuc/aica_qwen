import json
import pytest
from unittest.mock import MagicMock
from app.agents.pcb_engineer import PcbEngineerAgent
from app.models.schemas import (
    Architecture, Block, Connection, Requirements, ClarifyingQuestion,
    Arbitration, PcbReadiness
)

def _mock_requirements() -> Requirements:
    return Requirements(
        requirements=["24V input", "STM32 MCU", "RS485 interface"],
        constraints=["Industrial environment"],
        clarifications=[],
    )

def _mock_architecture() -> Architecture:
    return Architecture(
        blocks=[
            Block(name="MCU", sheet="sheet_mcu", purpose="STM32 microcontroller"),
            Block(name="RS485", sheet="sheet_rs485", purpose="Transceiver"),
            Block(name="Power", sheet="sheet_power", purpose="24V→3.3V converter"),
        ],
        interfaces=["RS485"],
        signals=["RS485_A", "RS485_B"],
        power=["24V", "+3.3V", "GND"],
        connections=[],
    )

def _mock_arbitration() -> Arbitration:
    return Arbitration(
        approved_architecture=_mock_architecture(),
        todo=["TODO: add TVS diode"],
        human_review=[],
        accepted_assumptions=["Single-board design"],
    )

def _agent_response() -> dict:
    return {
        "layerstack": "4-layer",
        "layerstack_reason": "Solid GND plane needed for RS485 signal integrity",
        "netclasses": [
            {"name": "PWR", "min_width_mm": 0.5, "clearance_mm": 0.3, "nets": ["GND", "+3.3V", "24V"]},
            {"name": "Signal", "min_width_mm": 0.2, "clearance_mm": 0.2, "nets": ["RS485_A", "RS485_B"]},
        ],
        "constraints": {
            "min_clearance_mm": 0.2,
            "min_track_width_mm": 0.2,
            "via_drill_mm": 0.4,
            "via_annular_ring_mm": 0.15,
        },
        "floorplan_text": "Power section isolated in corner. RS485 transceiver near connector.",
        "floorplan_ascii": "+------------------+\n| [PWR]  | [RS485] |\n| [MCU]           |\n+------------------+",
        "package_hints": [
            {"component_type": "MCU", "recommended_package": "LQFP-64", "reason": "hand-solderable"},
            {"component_type": "Resistor", "recommended_package": "0603", "reason": "hand-solderable"},
        ],
    }

def test_pcb_engineer_returns_pcb_readiness():
    client = MagicMock()
    client.chat_json.return_value = _agent_response()
    agent = PcbEngineerAgent()
    result = agent.run(client, _mock_requirements(), _mock_architecture(), _mock_arbitration())
    assert isinstance(result, PcbReadiness)
    assert result.layerstack == "4-layer"
    assert len(result.netclasses) == 2
    assert result.netclasses[0].name == "PWR"
    assert result.constraints.via_drill_mm == 0.4

def test_pcb_engineer_package_hints():
    client = MagicMock()
    client.chat_json.return_value = _agent_response()
    result = PcbEngineerAgent().run(
        client, _mock_requirements(), _mock_architecture(), _mock_arbitration()
    )
    assert any(h.component_type == "MCU" for h in result.package_hints)

def test_pcb_engineer_guidance_included():
    client = MagicMock()
    client.chat_json.return_value = _agent_response()
    PcbEngineerAgent().run(
        client, _mock_requirements(), _mock_architecture(), _mock_arbitration(),
        guidance=["Prefer SMD components"]
    )
    call_args = client.chat_json.call_args
    assert "Prefer SMD components" in call_args[0][1]
