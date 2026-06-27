"""Tests for the KiCad DRU generator."""
from app.generators.pcb_dru import generate_dru
from app.models.schemas import ConstraintSet, NetClass


def _constraints() -> ConstraintSet:
    return ConstraintSet(
        min_clearance_mm=0.2,
        min_track_width_mm=0.2,
        via_drill_mm=0.4,
        via_annular_ring_mm=0.15,
    )


def _netclasses() -> list[NetClass]:
    return [
        NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3.3V"]),
        NetClass(name="Signal", min_width_mm=0.2, clearance_mm=0.2, nets=["TX", "RX"]),
    ]


def test_dru_output_is_string():
    result = generate_dru(_constraints(), _netclasses())
    assert isinstance(result, str)
    assert len(result) > 0


def test_dru_contains_version_header():
    result = generate_dru(_constraints(), _netclasses())
    assert "(version 1)" in result


def test_dru_contains_board_constraints():
    result = generate_dru(_constraints(), _netclasses())
    assert "clearance" in result
    assert "0.2" in result  # min_clearance_mm
    assert "0.4" in result  # via_drill_mm


def test_dru_contains_netclass_rule():
    result = generate_dru(_constraints(), _netclasses())
    assert "PWR" in result
    assert "Signal" in result
    assert "0.5" in result   # PWR min_width_mm


def test_dru_nets_in_condition():
    result = generate_dru(_constraints(), _netclasses())
    # PWR nets should appear as conditions
    assert "GND" in result
    assert "+3.3V" in result
