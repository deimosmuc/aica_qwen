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
    Candidate,
    ClarifyOption,
    ClarifyingQuestion,
    ComponentChoice,
    Connection,
    ConstraintSet,
    Critique,
    FloorplanZone,
    NetClass,
    PackageHint,
    PcbReadiness,
    Requirements,
    RunResponse,
    TraceStep,
)


def _mock_pcb() -> PcbReadiness:
    """Fixed PCB-readiness data for mock mode (keyless demo)."""
    return PcbReadiness(
        layerstack="4-layer",
        layerstack_reason=(
            "RS485 fieldbus and USB-C data lines require a solid GND plane for "
            "signal integrity. A 4-layer stackup (Signal / GND / PWR / Signal) "
            "provides proper reference planes for both differential pairs."
        ),
        netclasses=[
            NetClass(
                name="PWR",
                min_width_mm=0.5,
                clearance_mm=0.3,
                nets=["VIN_24V", "+5V", "+3V3", "GND"],
            ),
            NetClass(
                name="Signal",
                min_width_mm=0.2,
                clearance_mm=0.2,
                nets=["I2C_SCL", "I2C_SDA", "SWDIO", "SWCLK", "NRST"],
            ),
            NetClass(
                name="USB",
                min_width_mm=0.15,
                clearance_mm=0.15,
                nets=["USB_D+", "USB_D-"],
            ),
            NetClass(
                name="RS485",
                min_width_mm=0.2,
                clearance_mm=0.25,
                nets=["RS485_A", "RS485_B"],
            ),
        ],
        constraints=ConstraintSet(
            min_clearance_mm=0.2,
            min_track_width_mm=0.15,
            via_drill_mm=0.4,
            via_annular_ring_mm=0.15,
        ),
        floorplan_text=(
            "Power section (24 V input, LDOs) in the top-left corner, isolated from "
            "signal traces by a copper-free keepout. MCU placed centrally for short "
            "signal paths to all peripherals. USB-C connector on the bottom edge. "
            "RS485 transceiver near the screw-terminal connector on the right edge. "
            "SWD debug header in the top-right corner. Status LEDs along the front "
            "edge visible when installed in an enclosure."
        ),
        floorplan_ascii=(
            "+--[PWR]------[MCU]-------[DEBUG]--+\n"
            "|                                  |\n"
            "|             [MCU]                |\n"
            "|                                  |\n"
            "+--[USB-C]-------[RS485]---[LEDs]--+"
        ),
        package_hints=[
            PackageHint(
                component_type="STM32 MCU",
                recommended_package="LQFP-64",
                reason="Hand-solderable, good thermal path, widely available for prototyping",
            ),
            PackageHint(
                component_type="Resistors / Capacitors",
                recommended_package="0603",
                reason="Hand-solderable, compact, adequate for this power level",
            ),
            PackageHint(
                component_type="24V input LDO / Buck",
                recommended_package="SOT-223 or D-PAK",
                reason="Exposed pad for heat dissipation at 24 V input",
            ),
            PackageHint(
                component_type="RS485 Transceiver",
                recommended_package="SOIC-8",
                reason="Hand-solderable, standard footprint available in every EDA library",
            ),
            PackageHint(
                component_type="USB-C Connector",
                recommended_package="USB-C SMD mid-mount",
                reason="SMD pads withstand insertion forces with proper footprint; no THT needed",
            ),
            PackageHint(
                component_type="Power Input Screw Terminal",
                recommended_package="2.54 mm pitch screw terminal (THT)",
                reason="THT justified for high-current power connectors: superior mechanical retention",
            ),
        ],
        component_choices=[
            ComponentChoice(component_type="MCU", category="mcu", candidates=[
                Candidate(part="STM32G0B1", package="LQFP-48", score=4.5, recommended=True,
                          pros=["Enough UART/I²C for RS485 + sensors", "Mainstream, well-stocked"],
                          cons=["No integrated radio"]),
                Candidate(part="ESP32-C3", package="QFN-32", score=3.8,
                          pros=["Integrated WiFi/BLE"],
                          cons=["Radio unused here", "Tighter peripheral count"]),
            ]),
            ComponentChoice(component_type="RS485 transceiver", category="connectivity", candidates=[
                Candidate(part="Isolated MAX14937", package="SOIC-16W", score=4.6, recommended=True,
                          pros=["Galvanic isolation for a noisy fieldbus"],
                          cons=["Higher BOM cost"]),
                Candidate(part="THVD1450", package="SOIC-8", score=4.0,
                          pros=["Cheaper, smaller"], cons=["Non-isolated"]),
            ]),
        ],
        floorplan_zones=[
            FloorplanZone(label="Power Entry", category="power", blocks=["Power"],
                          placement="left", separation=["Sensor Front-End"]),
            FloorplanZone(label="MCU Core", category="mcu", blocks=["MCU"], placement="center"),
            FloorplanZone(label="Fieldbus", category="connectivity", blocks=["RS485", "USB Service"],
                          placement="right"),
            FloorplanZone(label="Sensor Front-End", category="sensor", blocks=["Sensor IO"],
                          placement="top", separation=["Power Entry"]),
        ],
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
        # No explicit `questions=` — the Requirements validator backfills the legacy
        # `questions` list from these clarifications' text (see schemas.py).
        clarifications=[
            ClarifyingQuestion(
                id="rs485-isolation",
                text="Is galvanic isolation required on the RS485 interface?",
                select="single",
                options=[
                    ClarifyOption(label="Isolated transceiver + isolated DC-DC",
                                  detail="robust on a noisy fieldbus, more parts/cost"),
                    ClarifyOption(label="Non-isolated transceiver",
                                  detail="cheaper and smaller, fine for short quiet links"),
                ],
                assumption="Non-isolated RS485",
            ),
            ClarifyingQuestion(
                id="status-indicators",
                text="Which status indications should the board expose?",
                select="multi",
                options=[
                    ClarifyOption(label="Power LED", detail="supply present"),
                    ClarifyOption(label="Fault LED", detail="error / brown-out"),
                    ClarifyOption(label="Bus-activity LED", detail="RS485 traffic"),
                ],
                assumption="A single status LED",
            ),
        ],
        assumptions=[
            "ASSUMPTION: 24 V -> 5 V -> 3V3 cascaded power architecture",
            "ASSUMPTION: SWD used for debug/programming",
        ],
        confidence=0.72,
    )

    architecture = Architecture(
        blocks=[
            Block(name="Power", sheet="power.kicad_sch", purpose="24 V input, 5 V and 3V3 rails",
                  category="power"),
            Block(name="MCU", sheet="mcu.kicad_sch", purpose="STM32 core, clock, reset, decoupling",
                  category="mcu"),
            Block(name="USB Service", sheet="usb_service.kicad_sch", purpose="USB-C connector and ESD",
                  category="connectivity"),
            Block(name="RS485", sheet="rs485.kicad_sch", purpose="RS485 transceiver and bus protection",
                  category="connectivity"),
            Block(name="Sensor IO", sheet="sensor_io.kicad_sch", purpose="Sensor front-end placeholders",
                  category="sensor"),
            Block(name="Debug", sheet="debug.kicad_sch", purpose="SWD header and status LEDs",
                  category="debug"),
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

    pcb = _mock_pcb()

    trace = [
        TraceStep(agent="Requirements Agent", role="Senior Systems Engineer", status="ok",
                  summary="Structured 5 requirements, raised 2 clarification questions."),
        TraceStep(agent="System Architect", role="Principal Hardware Architect", status="ok",
                  summary="Proposed 6 functional blocks across hierarchical sheets."),
        TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", status="warning",
                  summary="Flagged missing surge protection and RS485 isolation risk."),
        TraceStep(agent="Arbitration", role="Chief Engineer", status="ok",
                  summary="Approved architecture; logged 2 TODOs and 2 human-review items."),
        TraceStep(agent="PCB Engineer", role="PCB Layout Preparation Engineer", status="ok",
                  summary="4-layer stackup. 4 net classes (PWR 0.5 mm, USB 0.15 mm, RS485 0.2 mm). "
                          "Floorplan: PWR isolated top-left, MCU central, RS485 right edge."),
        TraceStep(agent="PCB Critic", role="Senior PCB Reviewer", status="ok",
                  summary="All PCB constraints validated. Via drill 0.4 mm adequate for current budget."),
    ]

    return RunResponse(
        mode="mock",
        requirements=requirements,
        architecture=architecture,
        critique=critique,
        arbitration=arbitration,
        pcb_readiness=pcb,
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

    # PCB rework: Round 1 has via_drill too small, Round 2 corrected
    pcb_round1 = _mock_pcb()
    # Simulate the via-drill error that the critic will catch
    pcb_round1 = pcb_round1.model_copy(
        update={"constraints": ConstraintSet(
            min_clearance_mm=pcb_round1.constraints.min_clearance_mm,
            min_track_width_mm=pcb_round1.constraints.min_track_width_mm,
            via_drill_mm=0.2,  # too small — critic will flag this
            via_annular_ring_mm=pcb_round1.constraints.via_annular_ring_mm,
        )}
    )
    pcb_round2 = _mock_pcb()  # corrected version

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
        TraceStep(agent="PCB Engineer", role="PCB Layout Preparation Engineer", status="ok", round=1,
                  summary="4-layer stackup. Via drill 0.2 mm proposed (error — too small for 500 mA PWR net)."),
        TraceStep(agent="PCB Critic", role="Senior PCB Reviewer", status="warning", round=1,
                  summary="Via drill 0.2 mm too small for 500 mA on VIN_24V. Must increase to ≥ 0.4 mm."),
        TraceStep(agent="PCB Engineer", role="PCB Layout Preparation Engineer", status="ok", round=2,
                  summary="Corrected: via drill increased to 0.4 mm. .kicad_dru and PCB_READINESS.md generated."),
        TraceStep(agent="PCB Critic", role="Senior PCB Reviewer", status="ok", round=2,
                  summary="Re-reviewed: all PCB constraints valid. Via drill 0.4 mm adequate."),
    ]

    return RunResponse(
        mode="mock",
        requirements=base.requirements,
        architecture=base.architecture,   # final = full design
        critique=round2_critique,
        arbitration=base.arbitration,
        pcb_readiness=pcb_round2,
        trace=trace,
        needs_approval=True,
    )
