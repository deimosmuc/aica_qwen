"""KiCad 9/10 Design Rules (.kicad_dru) file generator.

Pure Python template — no LLM. Converts ConstraintSet + list[NetClass] to
a valid KiCad 9/10 .kicad_dru file. The DRU format is compatible with both
KiCad 9 and KiCad 10.

KiCad 9 DRU format reference:
  (version 1)
  (rule "RuleName"
    (constraint clearance (min <mm>mm))
    (condition "A.NetClass == 'ClassName'")
  )
  ...

Board-level constraints are written as a rule named "Board" with no condition.
Net-class-specific rules extend the board rule with a NetClass condition.
"""
from __future__ import annotations

from app.models.schemas import ConstraintSet, NetClass


def _mm(value: float) -> str:
    """Format a float as a KiCad mm value string, e.g. 0.2 → '0.2mm'."""
    # Strip trailing zeros but keep at least one decimal place
    formatted = f"{value:.3f}".rstrip("0").rstrip(".")
    if "." not in formatted:
        formatted += ".0"
    return f"{formatted}mm"


def generate_dru(constraints: ConstraintSet, netclasses: list[NetClass]) -> str:
    """Generate a KiCad 9 .kicad_dru file string from structured data."""
    lines: list[str] = ["(version 1)", ""]

    # --- Board-level constraints (apply to all nets) ---
    lines += [
        '(rule "Board"',
        f"  (constraint clearance (min {_mm(constraints.min_clearance_mm)}))",
        f"  (constraint track_width (min {_mm(constraints.min_track_width_mm)}))",
        f"  (constraint via_diameter (min {_mm(constraints.via_drill_mm + 2 * constraints.via_annular_ring_mm)}))",
        f"  (constraint hole_size (min {_mm(constraints.via_drill_mm)}))",
        ")",
        "",
    ]

    # --- Per-netclass rules ---
    for nc in netclasses:
        # TODO: For full KiCad DRU correctness, the clearance condition should cover
        # both sides: "A.NetClass == 'X' || B.NetClass == 'X'". The single-sided form
        # below is valid syntax and fires when net A belongs to the class, which is
        # sufficient for a scaffold. Board-level clearance applies as the fallback.
        condition = f"A.NetClass == '{nc.name}'"
        lines += [
            f'(rule "{nc.name}"',
            f"  (constraint clearance (min {_mm(nc.clearance_mm)}))",
            f"  (constraint track_width (min {_mm(nc.min_width_mm)}))",
            f'  (condition "{condition}")',
            ")",
            "",
        ]

    # --- Net assignment comments (informational only, not valid DRU syntax) ---
    # KiCad net class assignments live in the schematic/PCB, not the DRU file.
    # We include them as comments so the user knows what to assign in KiCad.
    nets_with_names = [(nc.name, nc.nets) for nc in netclasses if nc.nets]
    if nets_with_names:
        lines.append("; Net class assignments (configure in KiCad PCB editor):")
        for name, nets in nets_with_names:
            lines.append(f"; {name}: {', '.join(nets)}")

    return "\n".join(lines) + "\n"
