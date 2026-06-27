from unittest.mock import MagicMock
from app.agents.pcb_critic import PcbCriticAgent
from app.models.schemas import (
    Requirements, ConstraintSet, NetClass, PackageHint, PcbReadiness, PcbCritique,
)

def _pcb_readiness(via_drill=0.4) -> PcbReadiness:
    return PcbReadiness(
        layerstack="4-layer",
        layerstack_reason="RF module present",
        netclasses=[
            NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3.3V"]),
            NetClass(name="Signal", min_width_mm=0.2, clearance_mm=0.2, nets=["TX", "RX"]),
        ],
        constraints=ConstraintSet(
            min_clearance_mm=0.2,
            min_track_width_mm=0.2,
            via_drill_mm=via_drill,
            via_annular_ring_mm=0.15,
        ),
        floorplan_text="MCU central, RF in corner.",
        floorplan_ascii="[RF] [MCU]\n[PWR]",
        package_hints=[PackageHint(component_type="MCU", recommended_package="QFN-32", reason="thermal")],
    )

def _requirements() -> Requirements:
    return Requirements(
        requirements=["500mA peak current on PWR rail"],
        constraints=[],
        clarifications=[],
    )

def test_critic_finds_missing_blocks():
    client = MagicMock()
    client.chat_json.return_value = {
        "missing_blocks": ["Via drill 0.2mm too small for 500mA PWR net — increase to 0.4mm"],
        "warnings": [],
        "risks": [],
    }
    result = PcbCriticAgent().run(client, _requirements(), _pcb_readiness(via_drill=0.2))
    assert isinstance(result, PcbCritique)
    assert len(result.missing_blocks) == 1
    assert "0.2mm" in result.missing_blocks[0]

def test_critic_clean_pass():
    client = MagicMock()
    client.chat_json.return_value = {
        "missing_blocks": [],
        "warnings": [],
        "risks": [],
    }
    result = PcbCriticAgent().run(client, _requirements(), _pcb_readiness(via_drill=0.4))
    assert result.missing_blocks == []

def test_critic_guidance_forwarded():
    client = MagicMock()
    client.chat_json.return_value = {"missing_blocks": [], "warnings": [], "risks": []}
    PcbCriticAgent().run(
        client, _requirements(), _pcb_readiness(),
        guidance=["Target: hand-assembly prototype"]
    )
    assert "hand-assembly" in client.chat_json.call_args[0][1]
