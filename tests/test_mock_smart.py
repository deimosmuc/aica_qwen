"""Mock fixtures populate the smart-diagram fields (Phase 1)."""
from app.services.mock import mock_run, mock_run_rework


def test_mock_blocks_have_categories():
    arch = mock_run("x").architecture
    cats = {b.name: b.category for b in arch.blocks}
    assert cats["Power"] == "power"
    assert cats["MCU"] == "mcu"
    assert all(b.category != "" for b in arch.blocks)


def test_mock_pcb_has_choices_and_zones():
    pcb = mock_run("x").pcb_readiness
    assert len(pcb.component_choices) >= 2
    for ch in pcb.component_choices:
        assert sum(1 for c in ch.candidates if c.recommended) == 1
    assert len(pcb.floorplan_zones) >= 2
    assert any(z.separation for z in pcb.floorplan_zones)


def test_mock_rework_keeps_smart_fields():
    pcb = mock_run_rework("x").pcb_readiness
    assert pcb is not None and pcb.component_choices
