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

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.schemas import RunResponse

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

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


# Leading instruction/filler words stripped so the report title reads like a
# project name rather than the raw imperative prompt ("erstelle mir ein
# grundgerüst für …"). German + English; acronyms keep their casing (F1).
_TITLE_STOPWORDS = {
    "erstelle", "erstell", "erstellen", "baue", "bau", "bauen", "entwirf",
    "entwerfe", "entwerfen", "entwickle", "mach", "mache", "machen", "generiere",
    "generier", "design", "create", "build", "make", "generate", "develop",
    "please", "bitte", "mir", "me", "uns", "us", "for", "für", "of", "to",
    "i", "ich", "need", "brauche", "möchte", "will", "want", "give", "gib",
    "a", "an", "the", "der", "die", "das", "ein", "eine", "einen", "einem", "einer",
    "grundgerüst", "gerüst", "scaffold", "schematic", "schaltplan",
}


def _derive_title(requirements_text: str) -> str:
    """A concise, project-name-like title derived from the request.

    Strips a leading run of instruction/filler words so the header reads like a
    project name instead of the raw imperative prompt. Acronyms (STM32, RS485,
    USB-C) keep their casing; falls back to a generic name when nothing
    meaningful remains.
    """
    first_line = next((ln.strip() for ln in requirements_text.splitlines() if ln.strip()), "")
    words = first_line.replace(",", " ").split()
    i = 0
    # Drop leading filler, but never strip the last remaining word.
    while i < len(words) - 1 and words[i].lower().strip(".:;-") in _TITLE_STOPWORDS:
        i += 1
    title = " ".join(words[i:]).strip(" .,:;-") or "Circuit Design"
    if len(title) > 70:
        title = title[:70].rsplit(" ", 1)[0] + "…"
    return title[:1].upper() + title[1:]


def _report_context(result: RunResponse, requirements_text: str, project_name: str) -> dict:
    """Flatten a RunResponse into a flat, template-ready dict.

    Everything the Jinja2 template needs is computed here so the template stays
    logic-free. Missing pcb_readiness degrades to safe placeholders.
    """
    arch = result.architecture
    pcb = result.pcb_readiness

    # Title: a project-name-like label; description: the full request on one line.
    title = _derive_title(requirements_text)
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


def _floorplan_svg(result: RunResponse) -> str:
    """Deterministic placement-zone sketch from architecture blocks.

    Blocks are packed into a board outline on a fixed grid. The first column is
    treated as the power/input edge; a dashed keepout line separates it from the
    rest to hint at isolation. This is an illustrative sketch, not a real layout.
    """
    blocks = result.architecture.blocks
    if not blocks:
        return _placeholder_svg("Floorplan sketch unavailable")

    cols = 3
    zone_w = 150
    zone_h = 70
    gap = 16
    pad = 20
    rows = (len(blocks) + cols - 1) // cols
    inner_w = cols * zone_w + (cols - 1) * gap
    inner_h = rows * zone_h + (rows - 1) * gap
    width = inner_w + pad * 2
    height = inner_h + pad * 2

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        # Board outline.
        f'<rect x="{pad / 2}" y="{pad / 2}" width="{width - pad}" '
        f'height="{height - pad}" rx="8" fill="none" stroke="#10b981" '
        f'stroke-width="1.5" stroke-dasharray="6,3"/>',
        # Isolation keepout between the first column and the rest.
        f'<line x1="{pad + zone_w + gap / 2:.0f}" y1="{pad / 2}" '
        f'x2="{pad + zone_w + gap / 2:.0f}" y2="{height - pad / 2}" '
        f'stroke="#fca5a5" stroke-width="1" stroke-dasharray="4,3"/>',
    ]

    for i, block in enumerate(blocks):
        row, col = divmod(i, cols)
        x = pad + col * (zone_w + gap)
        y = pad + row * (zone_h + gap)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{zone_w}" height="{zone_h}" rx="6" '
            f'fill="#f5f3ff" stroke="#c4b5fd" stroke-width="1.2"/>'
        )
        parts.append(
            f'<text x="{x + zone_w / 2:.0f}" y="{y + zone_h / 2 + 4:.0f}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="12" '
            f'fill="#5b21b6" font-weight="600">{escape(block.name)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def generate_report_pdf(
    result: RunResponse, requirements_text: str, project_name: str
) -> bytes:
    """Render the PCB Design Brief to PDF bytes.

    WeasyPrint is imported lazily so this module loads even where its system
    libraries are absent; callers that cannot tolerate failure should guard the
    call (the /generate handler does).
    """
    from weasyprint import HTML  # lazy import; needs Pango/Cairo at runtime

    context = _report_context(result, requirements_text, project_name)
    context["architecture_svg"] = _architecture_svg(result)
    context["floorplan_svg"] = _floorplan_svg(result)

    html = _jinja_env.get_template("report.html.j2").render(**context)
    return HTML(string=html).write_pdf()
