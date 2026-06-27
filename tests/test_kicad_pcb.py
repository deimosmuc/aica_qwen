"""Tests that generate_scaffold() writes PCB files when pcb_readiness is set."""
import json
from pathlib import Path

import pytest

from app.generators.kicad import generate_scaffold
from app.models.schemas import (
    Architecture, Arbitration, Block, ConstraintSet, Critique,
    NetClass, PackageHint, PcbReadiness, Requirements, RunResponse, TraceStep,
)


def _simple_result(with_pcb: bool) -> RunResponse:
    arch = Architecture(
        blocks=[Block(name="MCU", sheet="mcu.kicad_sch", purpose="Core")],
        interfaces=["SWD"],
        signals=["SWDIO"],
        power=["+3V3", "GND"],
    )
    pcb = (
        PcbReadiness(
            layerstack="2-layer",
            layerstack_reason="Simple low-frequency design.",
            netclasses=[
                NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3V3"]),
            ],
            constraints=ConstraintSet(
                min_clearance_mm=0.2, min_track_width_mm=0.2,
                via_drill_mm=0.4, via_annular_ring_mm=0.15,
            ),
            floorplan_text="MCU centered.",
            floorplan_ascii="[MCU]",
            package_hints=[
                PackageHint(component_type="MCU", recommended_package="LQFP-64", reason="hand-solderable"),
            ],
        )
        if with_pcb else None
    )
    return RunResponse(
        mode="mock",
        requirements=Requirements(requirements=["SWD"], constraints=[], clarifications=[]),
        architecture=arch,
        critique=Critique(),
        arbitration=Arbitration(
            approved_architecture=arch, todo=[], human_review=[], accepted_assumptions=[]
        ),
        pcb_readiness=pcb,
        trace=[TraceStep(agent="Test", role="Test", status="ok", summary="ok")],
    )


def test_pcb_files_written_when_present(tmp_path):
    generate_scaffold(_simple_result(with_pcb=True), "test req", tmp_path)
    assert (tmp_path / "PCB_READINESS.md").exists()
    assert (tmp_path / "pcb_constraints.kicad_dru").exists()


def test_pcb_readiness_md_content(tmp_path):
    generate_scaffold(_simple_result(with_pcb=True), "test req", tmp_path)
    content = (tmp_path / "PCB_READINESS.md").read_text()
    assert "2-layer" in content
    assert "PWR" in content
    assert "[MCU]" in content  # floorplan_ascii


def test_dru_content(tmp_path):
    generate_scaffold(_simple_result(with_pcb=True), "test req", tmp_path)
    content = (tmp_path / "pcb_constraints.kicad_dru").read_text()
    assert "(version 1)" in content
    assert "Board" in content
    assert "PWR" in content


def test_pcb_files_absent_when_no_pcb_readiness(tmp_path):
    generate_scaffold(_simple_result(with_pcb=False), "test req", tmp_path)
    assert not (tmp_path / "PCB_READINESS.md").exists()
    assert not (tmp_path / "pcb_constraints.kicad_dru").exists()
