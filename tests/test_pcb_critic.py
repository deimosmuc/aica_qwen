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


def test_pcb_critic_prompt_covers_dfx():
    from app.agents.pcb_critic import SYSTEM_PROMPT
    low = SYSTEM_PROMPT.lower()
    assert "test point" in low and "fiducial" in low and "dfx_checklist" in low


def test_pcb_critic_flags_dfx_gap_in_missing_blocks():
    from app.agents.pcb_critic import PcbCriticAgent
    from app.models.schemas import PcbReadiness, ConstraintSet, Requirements

    class _Stub:
        def __init__(self, p): self._p = p
        def chat_json(self, s, u): return self._p

    pcb = PcbReadiness(layerstack="2-layer", layerstack_reason="r", netclasses=[],
                       constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                                 via_drill_mm=0.3, via_annular_ring_mm=0.1),
                       floorplan_text="", floorplan_ascii="", package_hints=[])
    payload = {"missing_blocks": ["No SWD test points on the debug net — add them for bring-up."],
               "warnings": [], "risks": []}
    crit = PcbCriticAgent().run(_Stub(payload), Requirements(), pcb)
    assert any("test point" in m.lower() for m in crit.missing_blocks)
