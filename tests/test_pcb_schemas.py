from app.models.schemas import NetClass, ConstraintSet, PackageHint, PcbReadiness, RunResponse

def test_netclass_fields():
    nc = NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3V3"])
    assert nc.name == "PWR"
    assert nc.nets == ["GND", "+3V3"]

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
