"""Prepared example pipeline used in Mock Mode.

This lets the whole app run end-to-end with no API key, so the demo always
works. The data mirrors the real JSON contracts exactly, so the UI built on
top of it does not change when the real Qwen agents come online.
"""
from __future__ import annotations

from app.models.schemas import (
    Arbitration,
    Architecture,
    Block,
    Connection,
    Critique,
    Requirements,
    RunResponse,
    TraceStep,
)


def mock_run(requirements_text: str) -> RunResponse:
    requirements = Requirements(
        requirements=[
            "24 V industrial supply input",
            "STM32 microcontroller as main processor",
            "USB-C interface for configuration",
            "RS485 fieldbus interface",
            "Status LEDs",
        ],
        constraints=[
            "Industrial environment (ESD / surge exposure on the 24 V rail)",
            "Single-board design",
        ],
        questions=[
            "Is galvanic isolation required on the RS485 interface?",
            "What is the maximum current budget on the 5 V rail?",
        ],
        assumptions=[
            "ASSUMPTION: 24 V -> 5 V -> 3V3 cascaded power architecture",
            "ASSUMPTION: SWD used for debug/programming",
        ],
        confidence=0.72,
    )

    architecture = Architecture(
        blocks=[
            Block(name="Power", sheet="power.kicad_sch", purpose="24 V input, 5 V and 3V3 rails"),
            Block(name="MCU", sheet="mcu.kicad_sch", purpose="STM32 core, clock, reset, decoupling"),
            Block(name="USB Service", sheet="usb_service.kicad_sch", purpose="USB-C connector and ESD"),
            Block(name="RS485", sheet="rs485.kicad_sch", purpose="RS485 transceiver and bus protection"),
            Block(name="Sensor IO", sheet="sensor_io.kicad_sch", purpose="Sensor front-end placeholders"),
            Block(name="Debug", sheet="debug.kicad_sch", purpose="SWD header and status LEDs"),
        ],
        interfaces=["USB-C", "RS485", "SWD"],
        signals=["USB_D+", "USB_D-", "RS485_A", "RS485_B", "I2C_SCL", "I2C_SDA", "SWDIO", "SWCLK", "NRST"],
        power=["VIN_24V", "+5V", "+3V3", "GND"],
        placeholder_components=[
            "DUMMY_MCU",
            "DUMMY_USB_C",
            "DUMMY_RS485",
            "DUMMY_POWER_STAGE",
            "DUMMY_ESD",
            "DUMMY_DEBUG",
        ],
        connections=[
            Connection(source="Power", target="MCU", type="power"),
            Connection(source="Power", target="USB Service", type="power"),
            Connection(source="Power", target="RS485", type="power"),
            Connection(source="Power", target="Sensor IO", type="power"),
            Connection(source="USB Service", target="MCU", type="data"),
            Connection(source="RS485", target="MCU", type="data"),
            Connection(source="Sensor IO", target="MCU", type="data"),
            Connection(source="Debug", target="MCU", type="debug"),
        ],
        notes=["Hierarchical design with one sheet per functional block."],
    )

    critique = Critique(
        warnings=["No explicit surge protection shown on the 24 V input."],
        risks=["RS485 without isolation may be insufficient for a noisy fieldbus."],
        missing_blocks=["DUMMY_CLOCK not yet placed in the MCU block."],
        recommendations=[
            "Add TVS / surge protection placeholder on VIN_24V.",
            "Confirm whether isolated RS485 is required.",
        ],
    )

    arbitration = Arbitration(
        approved_architecture=architecture,
        todo=[
            "TODO: Add DUMMY_TVS surge protection on VIN_24V.",
            "TODO: Place DUMMY_CLOCK in MCU block.",
        ],
        human_review=[
            "NEEDS HUMAN REVIEW: RS485 isolation decision.",
            "NEEDS HUMAN REVIEW: 5 V rail current budget.",
        ],
        accepted_assumptions=[
            "24 V -> 5 V -> 3V3 cascaded power architecture",
            "SWD used for debug/programming",
        ],
    )

    trace = [
        TraceStep(agent="Requirements Agent", role="Senior Systems Engineer", status="ok",
                  summary="Structured 5 requirements, raised 2 clarification questions."),
        TraceStep(agent="System Architect", role="Principal Hardware Architect", status="ok",
                  summary="Proposed 6 functional blocks across hierarchical sheets."),
        TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", status="warning",
                  summary="Flagged missing surge protection and RS485 isolation risk."),
        TraceStep(agent="Arbitration", role="Chief Engineer", status="ok",
                  summary="Approved architecture; logged 2 TODOs and 2 human-review items."),
    ]

    return RunResponse(
        mode="mock",
        requirements=requirements,
        architecture=architecture,
        critique=critique,
        arbitration=arbitration,
        trace=trace,
        needs_approval=True,
    )


def mock_run_rework(requirements_text: str) -> RunResponse:
    """Scripted two-round example for rework-enabled profiles, so the demo shows
    self-correction without an API key. Round 1 omits the Debug/LED block and the
    Critic flags it; round 2 adds it and the Critic is clean. The returned
    architecture/critique are the final (round-2) state."""
    base = mock_run(requirements_text)

    # Round-1 architecture: the same design minus the Debug block (the gap).
    round1_arch = base.architecture.model_copy(
        update={"blocks": [b for b in base.architecture.blocks if b.name != "Debug"]}
    )
    # Round-2: the full architecture, Critic now clean.
    round2_critique = Critique(
        warnings=base.critique.warnings,
        risks=base.critique.risks,
        missing_blocks=[],
        recommendations=base.critique.recommendations,
    )

    trace = [
        TraceStep(agent="Requirements Agent", role="Senior Systems Engineer", status="ok", round=1,
                  summary="Structured 5 requirements, raised 2 clarification questions."),
        TraceStep(agent="System Architect", role="Principal Hardware Architect", status="ok", round=1,
                  summary=f"Proposed {len(round1_arch.blocks)} functional blocks across hierarchical sheets."),
        TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", status="warning", round=1,
                  summary="Flagged 1 missing block (Debug/SWD + status LEDs)."),
        TraceStep(agent="System Architect", role="Principal Hardware Architect", status="ok", round=2,
                  summary=f"Revised: added the Debug block — now {len(base.architecture.blocks)} blocks."),
        TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", status="ok", round=2,
                  summary="Re-reviewed: no missing blocks remain."),
        TraceStep(agent="Arbitration", role="Chief Engineer", status="ok", round=2,
                  summary="Approved architecture; logged 2 TODOs and 2 human-review items."),
    ]

    return RunResponse(
        mode="mock",
        requirements=base.requirements,
        architecture=base.architecture,   # final = full design
        critique=round2_critique,
        arbitration=base.arbitration,
        trace=trace,
        needs_approval=True,
    )
