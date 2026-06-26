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
