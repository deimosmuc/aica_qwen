"""Generate a professional PDF 'PCB Design Brief' from a pipeline RunResponse.

Pure, dependency-light helpers plus a single WeasyPrint render entry point. All
helpers are independently testable; WeasyPrint is imported lazily so the rest of
the module (and its tests) work even where the system libraries are absent.
"""
from __future__ import annotations

import base64
from datetime import date
from pathlib import Path

from app.models.schemas import RunResponse

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "static" / "assets"
_LOGO_PATH = _ASSETS_DIR / "logo.png"


def _logo_data_uri() -> str:
    """Return the bundled logo as a base64 PNG data URI, or "" if it is missing.

    Embedding as a data URI keeps the rendered HTML fully self-contained so
    WeasyPrint needs no external file resolution.
    """
    if not _LOGO_PATH.is_file():
        return ""
    encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _report_context(result: RunResponse, requirements_text: str, project_name: str) -> dict:
    """Flatten a RunResponse into a flat, template-ready dict.

    Everything the Jinja2 template needs is computed here so the template stays
    logic-free. Missing pcb_readiness degrades to safe placeholders.
    """
    arch = result.architecture
    pcb = result.pcb_readiness

    # Title: first non-empty line of the request, trimmed; description: the rest.
    first_line = next((ln.strip() for ln in requirements_text.splitlines() if ln.strip()), "")
    title = (first_line[:80] or "Circuit Design").rstrip(".")
    description = requirements_text.strip().replace("\n", " ")
    if len(description) > 160:
        description = description[:157].rstrip() + "…"

    # Summary bullets: ✓ facts, then ⚠ todos, then ! human-review items.
    bullets: list[str] = [
        f"✓ {len(result.requirements.requirements)} requirements structured",
        f"✓ Architecture: {len(arch.blocks)} blocks across "
        f"{len(arch.interfaces)} interfaces",
    ]
    for todo in result.arbitration.todo:
        bullets.append(f"⚠ TODO — {todo}")
    for hr in result.arbitration.human_review:
        bullets.append(f"! NEEDS HUMAN REVIEW — {hr}")

    if pcb is not None:
        net_classes = [
            {
                "name": nc.name,
                "min_width_mm": nc.min_width_mm,
                "clearance_mm": nc.clearance_mm,
                "nets": ", ".join(nc.nets),
            }
            for nc in pcb.netclasses
        ]
        package_hints = [
            {"component_type": ph.component_type, "recommended_package": ph.recommended_package}
            for ph in pcb.package_hints
        ]
        layerstack = pcb.layerstack
        min_clearance_mm = pcb.constraints.min_clearance_mm
        via_drill_mm = pcb.constraints.via_drill_mm
        via_annular_ring_mm = pcb.constraints.via_annular_ring_mm
    else:
        net_classes = []
        package_hints = []
        layerstack = "—"
        min_clearance_mm = 0.0
        via_drill_mm = 0.0
        via_annular_ring_mm = 0.0

    return {
        "title": title,
        "description": description,
        "project_name": project_name,
        "iso_date": date.today().isoformat(),
        "layerstack": layerstack,
        "net_class_count": len(net_classes),
        "min_clearance_mm": min_clearance_mm,
        "open_todo_count": len(result.arbitration.todo),
        "summary_bullets": bullets,
        "net_classes": net_classes,
        "package_hints": package_hints,
        "via_drill_mm": via_drill_mm,
        "via_annular_ring_mm": via_annular_ring_mm,
        "logo_data_uri": _logo_data_uri(),
    }
