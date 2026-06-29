from app.models.schemas import NetClass, ConstraintSet, PackageHint, PcbReadiness, RunResponse

def test_netclass_fields():
    nc = NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3V3"])
    assert nc.name == "PWR"
    assert nc.nets == ["GND", "+3V3"]

def test_netclass_coerces_non_string_impedance():
    # Live Qwen sometimes returns impedance as a number (or small object) rather
    # than a string; one descriptive field must not collapse the whole run.
    nc = NetClass.model_validate(
        {"name": "USB", "min_width_mm": 0.2, "clearance_mm": 0.2, "impedance": 90}
    )
    assert nc.impedance == "90 Ω"
    nc2 = NetClass.model_validate(
        {"name": "DDR", "min_width_mm": 0.1, "clearance_mm": 0.1,
         "impedance": {"single": "50", "diff": "90"}}
    )
    assert isinstance(nc2.impedance, str) and "50" in nc2.impedance
    nc3 = NetClass.model_validate(
        {"name": "GND", "min_width_mm": 0.3, "clearance_mm": 0.3, "impedance": None}
    )
    assert nc3.impedance is None


def test_constraint_set_fields():
    cs = ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                       via_drill_mm=0.3, via_annular_ring_mm=0.1)
    assert cs.via_drill_mm == 0.3

def test_package_hint_fields():
    ph = PackageHint(component_type="MCU", recommended_package="QFN-32",
                     reason="thermal pad improves heat dissipation")
    assert ph.recommended_package == "QFN-32"

def test_pcb_readiness_round_trip():
    pr = PcbReadiness(
        layerstack="4-layer",
        layerstack_reason="RF module requires solid GND plane",
        netclasses=[NetClass(name="Signal", min_width_mm=0.2, clearance_mm=0.2, nets=[])],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                  via_drill_mm=0.3, via_annular_ring_mm=0.1),
        floorplan_text="Isolate RF section from digital core.",
        floorplan_ascii="[RF] | [MCU] [PWR]",
        package_hints=[PackageHint(component_type="Resistor",
                                   recommended_package="0603",
                                   reason="hand-solderable")],
    )
    assert pr.layerstack == "4-layer"
    data = pr.model_dump()
    assert data["netclasses"][0]["name"] == "Signal"

def test_run_response_pcb_readiness_optional():
    # Mock mode now includes PCB readiness data
    from app.services.mock import mock_run
    r = mock_run("test")
    assert r.pcb_readiness is not None
    assert r.pcb_readiness.layerstack == "4-layer"


# --- Smart Diagrams & Component Candidates (Phase 1) -------------------------

from app.models.schemas import (
    Block, Candidate, ComponentChoice, FloorplanZone, GenerateRequest,
)
from app.services.mock import mock_run


def test_block_category_defaults_to_other():
    assert Block(name="X", sheet="x.kicad_sch", purpose="p").category == "other"
    assert Block(name="M", sheet="m.kicad_sch", purpose="p", category="mcu").category == "mcu"


def test_candidate_and_choice_defaults():
    c = Candidate(part="STM32G0", package="LQFP-48")
    assert c.score == 0.0 and c.recommended is False and c.pros == [] and c.cons == []
    cc = ComponentChoice(component_type="MCU")
    assert cc.category == "other" and cc.candidates == []


def test_floorplan_zone_defaults():
    z = FloorplanZone(label="Power")
    assert z.category == "other" and z.placement == "center"
    assert z.blocks == [] and z.separation == []


def test_pcb_readiness_new_fields_default_empty():
    bare = PcbReadiness(
        layerstack="2-layer", layerstack_reason="r", netclasses=[],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                   via_drill_mm=0.3, via_annular_ring_mm=0.1),
        floorplan_text="", floorplan_ascii="", package_hints=[],
    )
    assert bare.component_choices == [] and bare.floorplan_zones == []


def test_generate_request_architecture_svg_optional():
    req = GenerateRequest(requirements_text="x", result=mock_run("x"))
    assert req.architecture_svg is None


def test_dfx_item_defaults():
    from app.models.schemas import DfxItem
    d = DfxItem(category="testability", item="SWD test points")
    assert d.status == "recommended" and d.note == ""
    d2 = DfxItem(category="dfm", item="3 fiducials", status="present", note="corners")
    assert d2.status == "present" and d2.note == "corners"


def test_dfx_item_coerces_out_of_set_enums():
    # Live Qwen sometimes returns a status/category outside the allowed set
    # (e.g. status "ok", category "manufacturing"). A single non-critical field
    # must not crash the run — it should be mapped onto the nearest valid value.
    from app.models.schemas import DfxItem
    d = DfxItem.model_validate({"category": "manufacturing", "item": "x", "status": "ok"})
    assert d.status == "present"
    assert d.category == "dfm"


def test_dfx_item_unknown_enum_falls_back_to_default():
    from app.models.schemas import DfxItem
    d = DfxItem.model_validate({"category": "wat", "item": "x", "status": "weird"})
    assert d.status == "recommended"
    assert d.category == "dfm"


def test_pcb_readiness_dfx_defaults_empty():
    from app.models.schemas import PcbReadiness, ConstraintSet
    pcb = PcbReadiness(
        layerstack="2-layer", layerstack_reason="r", netclasses=[],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                  via_drill_mm=0.3, via_annular_ring_mm=0.1),
        floorplan_text="", floorplan_ascii="", package_hints=[],
    )
    assert pcb.dfx_checklist == []


def test_step_request_response_pcb_critic_fields():
    from app.models.schemas import StepRequest, StepResponse, TraceStep
    req = StepRequest(stage="pcb_critic", requirements_text="x")
    assert req.pcb_readiness is None
    resp = StepResponse(stage="pcb_critic", mode="mock",
                        trace_step=TraceStep(agent="PCB Critic", role="Senior PCB Reviewer", summary="s"))
    assert resp.pcb_critique is None


def test_persona_fields_default_none():
    from app.models.schemas import RunRequest, StepRequest, GenerateRequest
    from app.services.mock import mock_run
    assert RunRequest(requirements_text="x").persona is None
    assert StepRequest(stage="requirements", requirements_text="x").persona is None
    assert GenerateRequest(requirements_text="x", result=mock_run("x")).persona is None
    assert RunRequest(requirements_text="x", persona="student").persona == "student"
