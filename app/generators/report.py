"""Generate a professional PDF 'PCB Design Brief' from a pipeline RunResponse.

Pure, dependency-light helpers plus a single WeasyPrint render entry point. All
helpers are independently testable; WeasyPrint is imported lazily so the rest of
the module (and its tests) work even where the system libraries are absent.
"""
from __future__ import annotations

import base64
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from app.models.schemas import RunResponse

# Layout constants for the deterministic diagrams (viewBox units).
_COLS = 3
_BOX_W = 150
_BOX_H = 56
_GAP_X = 30
_GAP_Y = 40
_PAD = 12

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


def _placeholder_svg(message: str) -> str:
    return (
        '<svg viewBox="0 0 400 80" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="2" y="2" width="396" height="76" rx="6" fill="#f8fafc" '
        'stroke="#e2e8f0"/>'
        f'<text x="200" y="44" text-anchor="middle" font-family="sans-serif" '
        f'font-size="13" fill="#94a3b8">{escape(message)}</text></svg>'
    )


def _architecture_svg(result: RunResponse) -> str:
    """Deterministic block-diagram SVG from architecture blocks + connections.

    Blocks are laid out on a fixed grid (``_COLS`` per row). Connections are drawn
    as straight lines between block centres; ``type == "power"`` renders dashed.
    """
    blocks = result.architecture.blocks
    if not blocks:
        return _placeholder_svg("Architecture diagram unavailable")

    # Assign each block a grid cell and remember its centre by name.
    centres: dict[str, tuple[float, float]] = {}
    cells = []
    for i, block in enumerate(blocks):
        row, col = divmod(i, _COLS)
        x = _PAD + col * (_BOX_W + _GAP_X)
        y = _PAD + row * (_BOX_H + _GAP_Y)
        centres[block.name] = (x + _BOX_W / 2, y + _BOX_H / 2)
        cells.append((x, y, block.name))

    rows = (len(blocks) + _COLS - 1) // _COLS
    width = _PAD * 2 + _COLS * _BOX_W + (_COLS - 1) * _GAP_X
    height = _PAD * 2 + rows * _BOX_H + (rows - 1) * _GAP_Y

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" '
        'orient="auto"><path d="M0,0 L8,3 L0,6 z" fill="#94a3b8"/></marker></defs>',
    ]

    # Connections first (so boxes paint over the line ends).
    for conn in result.architecture.connections:
        if conn.source not in centres or conn.target not in centres:
            continue
        x1, y1 = centres[conn.source]
        x2, y2 = centres[conn.target]
        dash = ' stroke-dasharray="6,3"' if conn.type == "power" else ""
        parts.append(
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="#94a3b8" stroke-width="1.2"{dash} marker-end="url(#arr)"/>'
        )

    # Boxes + labels.
    for x, y, name in cells:
        parts.append(
            f'<rect x="{x}" y="{y}" width="{_BOX_W}" height="{_BOX_H}" rx="6" '
            f'fill="#eff6ff" stroke="#93c5fd" stroke-width="1.2"/>'
        )
        parts.append(
            f'<text x="{x + _BOX_W / 2:.0f}" y="{y + _BOX_H / 2 + 4:.0f}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="13" '
            f'fill="#1e40af" font-weight="600">{escape(name)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
