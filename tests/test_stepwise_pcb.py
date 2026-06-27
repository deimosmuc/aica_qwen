"""Tests for the pcb_engineer stage in the stepwise pipeline."""
from unittest.mock import MagicMock

from app.models.schemas import (
    Architecture, Arbitration, Block, ConstraintSet, Critique, NetClass,
    PackageHint, PcbReadiness, Requirements, StepRequest, StepResponse,
)
from app.services.stepwise import run_stage
from app.services.config import Settings


def _settings(mock_mode: bool = False) -> Settings:
    return Settings(qwen_api_key="" if mock_mode else "test")


def _requirements() -> Requirements:
    return Requirements(requirements=["RS485"], constraints=[], clarifications=[])


def _architecture() -> Architecture:
    return Architecture(
        blocks=[Block(name="MCU", sheet="main", purpose="Control")],
        interfaces=["RS485"],
        signals=["RS485_A"],
        power=["+3V3", "GND"],
    )


def _arbitration() -> Arbitration:
    return Arbitration(
        approved_architecture=_architecture(),
        todo=["TODO: add TVS"],
        human_review=[],
        accepted_assumptions=[],
    )


def _pcb_response() -> dict:
    return {
        "layerstack": "4-layer",
        "layerstack_reason": "RS485 needs GND plane.",
        "netclasses": [
            {"name": "PWR", "min_width_mm": 0.5, "clearance_mm": 0.3, "nets": ["GND", "+3V3"]},
        ],
        "constraints": {
            "min_clearance_mm": 0.2, "min_track_width_mm": 0.2,
            "via_drill_mm": 0.4, "via_annular_ring_mm": 0.15,
        },
        "floorplan_text": "MCU central.",
        "floorplan_ascii": "[MCU]",
        "package_hints": [
            {"component_type": "MCU", "recommended_package": "LQFP-64", "reason": "hand-solderable"},
        ],
    }


def test_pcb_engineer_stepwise_returns_pcb_readiness():
    client = MagicMock()
    client.chat_json.return_value = _pcb_response()

    req = StepRequest(
        stage="pcb_engineer",
        requirements_text="RS485 interface",
        requirements=_requirements(),
        architecture=_architecture(),
        arbitration=_arbitration(),
    )

    from app.services import stepwise
    import app.services.qwen_client as qc
    original = qc.QwenClient
    qc.QwenClient = MagicMock(return_value=client)
    try:
        result = run_stage(req, _settings())
    finally:
        qc.QwenClient = original

    assert isinstance(result, StepResponse)
    assert result.pcb_readiness is not None
    assert result.pcb_readiness.layerstack == "4-layer"


def test_pcb_engineer_stepwise_missing_arbitration():
    import pytest
    req = StepRequest(
        stage="pcb_engineer",
        requirements_text="RS485 interface",
        requirements=_requirements(),
        architecture=_architecture(),
        # deliberately omit arbitration
    )
    # In mock mode, the stage returns mock data without validating prior steps
    # In live mode, missing arbitration raises ValueError
    with pytest.raises(ValueError):
        run_stage(req, _settings(mock_mode=False))


def test_pcb_engineer_stepwise_mock_mode():
    req = StepRequest(
        stage="pcb_engineer",
        requirements_text="RS485 interface",
    )
    result = run_stage(req, _settings(mock_mode=True))
    assert isinstance(result, StepResponse)
    assert result.pcb_readiness is not None
    assert result.mode == "mock"
