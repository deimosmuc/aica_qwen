"""PCB Engineer emits component candidates + floorplan zones (Phase 1)."""
from app.agents.pcb_engineer import PcbEngineerAgent, SYSTEM_PROMPT
from app.models.schemas import Arbitration, Architecture, Requirements


class _StubClient:
    def __init__(self, payload):
        self._p = payload

    def chat_json(self, system, user):
        return self._p


_BASE = {
    "layerstack": "4-layer", "layerstack_reason": "r",
    "netclasses": [], "constraints": {"min_clearance_mm": 0.2, "min_track_width_mm": 0.2,
        "via_drill_mm": 0.3, "via_annular_ring_mm": 0.1},
    "floorplan_text": "", "floorplan_ascii": "", "package_hints": [],
}


def test_prompt_requests_choices_and_zones():
    low = SYSTEM_PROMPT.lower()
    assert "component_choices" in low and "floorplan_zones" in low


def test_parses_component_choices_and_zones():
    payload = dict(
        _BASE,
        component_choices=[{
            "component_type": "MCU", "category": "mcu",
            "candidates": [
                {"part": "STM32G0", "package": "LQFP-48", "score": 4.5, "recommended": True,
                 "pros": ["enough UARTs"], "cons": ["no radio"]},
                {"part": "ESP32", "package": "module", "score": 4.0, "pros": ["WiFi"], "cons": ["bigger"]},
            ]}],
        floorplan_zones=[{"label": "Power", "category": "power", "blocks": ["Power"],
                          "placement": "edge", "separation": ["Sensor"]}],
    )
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(payload), Requirements(), Architecture(), arb)
    assert pcb.component_choices[0].component_type == "MCU"
    assert pcb.component_choices[0].candidates[0].recommended is True
    assert pcb.component_choices[0].candidates[0].score == 4.5
    assert pcb.floorplan_zones[0].placement == "edge"
    assert pcb.floorplan_zones[0].separation == ["Sensor"]


def test_missing_new_fields_default_empty():
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(dict(_BASE)), Requirements(), Architecture(), arb)
    assert pcb.component_choices == [] and pcb.floorplan_zones == []


def test_parses_dfx_checklist():
    payload = dict(_BASE, dfx_checklist=[
        {"category": "testability", "item": "SWD test points", "status": "recommended"},
        {"category": "dfm", "item": "3 fiducials", "status": "present", "note": "corners"},
        {"category": "bringup", "item": "PWR + STATUS LED", "status": "present"},
    ])
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(payload), Requirements(), Architecture(), arb)
    cats = [d.category for d in pcb.dfx_checklist]
    assert cats == ["testability", "dfm", "bringup"]
    assert pcb.dfx_checklist[0].status == "recommended"


def test_prompt_requests_dfx():
    low = SYSTEM_PROMPT.lower()
    assert "dfx_checklist" in low and "fiducial" in low and "test point" in low


def test_missing_dfx_defaults_empty():
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(dict(_BASE)), Requirements(), Architecture(), arb)
    assert pcb.dfx_checklist == []
