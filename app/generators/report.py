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

# Single source of truth for category colours (light theme). Mirrors the design
# spec; shared by the block diagram, the floorplan and the legend.
CATEGORY_STYLE = {
    "mcu":          {"fill": "#E6F1FB", "stroke": "#2563EB", "text": "#0C447C"},
    "sensor":       {"fill": "#F3E8FF", "stroke": "#7C3AED", "text": "#5B21B6"},
    "power":        {"fill": "#FEF3C7", "stroke": "#D97706", "text": "#92400E"},
    "connectivity": {"fill": "#D7EEF2", "stroke": "#0E7490", "text": "#0B4A57"},
    "debug":        {"fill": "#F1F5F9", "stroke": "#64748B", "text": "#334155"},
    "status":       {"fill": "#DCFCE7", "stroke": "#16A34A", "text": "#14532D"},
    "other":        {"fill": "#F8FAFC", "stroke": "#94A3B8", "text": "#475569"},
}
_CATEGORY_LABELS = {
    "mcu": "MCU", "sensor": "Sensor", "power": "Power", "connectivity": "Connectivity",
    "debug": "Debug", "status": "Status", "other": "Other",
}
_CATEGORY_ORDER = ["mcu", "sensor", "power", "connectivity", "debug", "status", "other"]


def _category_style(category: str) -> dict:
    return CATEGORY_STYLE.get(category, CATEGORY_STYLE["other"])


def _legend_entries(result: RunResponse) -> list[dict]:
    """Category legend rows for the categories actually present in the design."""
    present = {b.category for b in result.architecture.blocks}
    out = []
    for cat in _CATEGORY_ORDER:
        if cat in present:
            s = _category_style(cat)
            out.append({"label": _CATEGORY_LABELS[cat], "fill": s["fill"], "stroke": s["stroke"]})
    return out


def _wrap_label(text: str, max_chars: int = 14) -> list[str]:
    """Greedy word-wrap so a block label fits its box; never returns empty."""
    words = text.split()
    if not words:
        return [text]
    lines, cur = [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    # hard-split any single word still too long
    out: list[str] = []
    for ln in lines:
        while len(ln) > max_chars:
            out.append(ln[:max_chars])
            ln = ln[max_chars:]
        out.append(ln)
    return out


def _stars(score: float) -> str:
    full = max(0, min(5, int(round(score))))
    return "★" * full + "☆" * (5 - full)


def _candidate_cards(result: RunResponse) -> list[dict]:
    """Flatten component_choices into template-ready cards (recommended first)."""
    pcb = result.pcb_readiness
    if pcb is None:
        return []
    cards = []
    for ch in pcb.component_choices:
        cands = sorted(ch.candidates, key=lambda c: (not c.recommended, -c.score))
        cards.append({
            "component_type": ch.component_type,
            "category": ch.category,
            "candidates": [
                {"part": c.part, "package": c.package, "score": round(c.score, 1),
                 "stars": _stars(c.score), "recommended": c.recommended,
                 "pros": c.pros, "cons": c.cons}
                for c in cands
            ],
        })
    return cards


def _label_tspans(text: str, cx: float, cy: float, max_chars: int, line_h: int) -> str:
    """Centred, word-wrapped <tspan> lines for an SVG box label."""
    lines = _wrap_label(text, max_chars)
    start_y = cy - (len(lines) - 1) * line_h / 2 + 4
    return "".join(
        f'<tspan x="{cx:.0f}" y="{start_y + k * line_h:.0f}">{escape(ln)}</tspan>'
        for k, ln in enumerate(lines)
    )


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
        "component_choices": _candidate_cards(result),
        "legend": _legend_entries(result),
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
    """Category-clustered block-diagram SVG (Python fallback for the report).

    Blocks are grouped by functional category and laid out on a fixed grid.
    Connections route as orthogonal polylines (no diagonals); ``type == "power"``
    renders dashed. Boxes are coloured by category via ``CATEGORY_STYLE``.
    """
    blocks = result.architecture.blocks
    if not blocks:
        return _placeholder_svg("Architecture diagram unavailable")

    # Cluster: same-category blocks sit together; MCU first (lands centre-left).
    def _cat_key(b):
        return _CATEGORY_ORDER.index(b.category) if b.category in _CATEGORY_ORDER else len(_CATEGORY_ORDER)

    ordered = sorted(blocks, key=_cat_key)

    centres: dict[str, tuple[float, float]] = {}
    cells = []
    for i, block in enumerate(ordered):
        row, col = divmod(i, _COLS)
        x = _PAD + col * (_BOX_W + _GAP_X)
        y = _PAD + row * (_BOX_H + _GAP_Y)
        centres[block.name] = (x + _BOX_W / 2, y + _BOX_H / 2)
        cells.append((x, y, block))

    rows = (len(ordered) + _COLS - 1) // _COLS
    width = _PAD * 2 + _COLS * _BOX_W + (_COLS - 1) * _GAP_X
    height = _PAD * 2 + rows * _BOX_H + (rows - 1) * _GAP_Y

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" '
        'orient="auto"><path d="M0,0 L8,3 L0,6 z" fill="#94a3b8"/></marker></defs>',
    ]

    # Orthogonal edges first (so boxes paint over the line ends).
    for conn in result.architecture.connections:
        if conn.source not in centres or conn.target not in centres:
            continue
        x1, y1 = centres[conn.source]
        x2, y2 = centres[conn.target]
        ymid = (y1 + y2) / 2
        dash = ' stroke-dasharray="6,3"' if conn.type == "power" else ""
        pts = f"{x1:.0f},{y1:.0f} {x1:.0f},{ymid:.0f} {x2:.0f},{ymid:.0f} {x2:.0f},{y2:.0f}"
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="#94a3b8" '
            f'stroke-width="1.2"{dash} marker-end="url(#arr)"/>'
        )

    # Boxes + wrapped labels, coloured by category.
    for x, y, block in cells:
        s = _category_style(block.category)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{_BOX_W}" height="{_BOX_H}" rx="6" '
            f'fill="{s["fill"]}" stroke="{s["stroke"]}" stroke-width="1.2"/>'
        )
        spans = _label_tspans(block.name, x + _BOX_W / 2, y + _BOX_H / 2, 16, 14)
        parts.append(
            f'<text text-anchor="middle" font-family="sans-serif" font-size="12" '
            f'fill="{s["text"]}" font-weight="600">{spans}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


_FP_COLS = 3
_FP_ROWS = 3
_FP_ZW = 150
_FP_ZH = 70
_FP_GAP = 18
_FP_PAD = 20
_PLACEMENT_CELL = {
    "left": (0, 1), "right": (2, 1), "top": (1, 0), "bottom": (1, 2),
    "center": (1, 1), "corner": (0, 0), "edge": (0, 0),
}


def _fp_cell_xy(col: int, row: int) -> tuple[float, float]:
    return _FP_PAD + col * (_FP_ZW + _FP_GAP), _FP_PAD + row * (_FP_ZH + _FP_GAP)


def _floorplan_svg(result: RunResponse) -> str:
    """Intelligent floorplan from the PCB Engineer's placement zones.

    Each zone is a coloured rounded rect placed per its coarse ``placement``
    keyword on a 3x3 board grid; ``separation`` draws a dashed keep-out line to
    the zones it must stay apart from. Falls back to a category-clustered grid of
    the architecture blocks when no zones are present (no blind 1:1 copy).
    """
    pcb = result.pcb_readiness
    zones = pcb.floorplan_zones if pcb else []
    if not zones:
        return _floorplan_fallback_svg(result)

    width = _FP_COLS * _FP_ZW + (_FP_COLS - 1) * _FP_GAP + _FP_PAD * 2
    height = _FP_ROWS * _FP_ZH + (_FP_ROWS - 1) * _FP_GAP + _FP_PAD * 2

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        '<defs><marker id="vent" markerWidth="9" markerHeight="9" refX="7" refY="3" '
        'orient="auto"><path d="M0,0 L8,3 L0,6 z" fill="#0e7490"/></marker></defs>',
        f'<rect x="{_FP_PAD / 2}" y="{_FP_PAD / 2}" width="{width - _FP_PAD}" '
        f'height="{height - _FP_PAD}" rx="8" fill="none" stroke="#10b981" '
        f'stroke-width="1.5" stroke-dasharray="6,3"/>',
    ]

    # Assign each zone a grid cell, packing collisions to the next free cell.
    used: set[tuple[int, int]] = set()
    zone_pos: dict[str, tuple[int, int]] = {}
    for z in zones:
        cell = _PLACEMENT_CELL.get(z.placement, (1, 1))
        if cell in used:
            for idx in range(_FP_COLS * _FP_ROWS):
                cand = (idx % _FP_COLS, idx // _FP_COLS)
                if cand not in used:
                    cell = cand
                    break
        used.add(cell)
        zone_pos[z.label] = cell

    # Thermal keep-out: fence the heat-sensitive sensor zone(s) — those that
    # declare a separation — with an enclosing dashed boundary (far clearer than a
    # diagonal between centres). Drawn under the rects so the fence hugs the zone.
    bx0, by0 = _FP_PAD / 2, _FP_PAD / 2
    bx1, by1 = width - _FP_PAD / 2, height - _FP_PAD / 2
    fenced: list = []  # zones that got a keep-out fence → candidates for an airflow arrow
    for z in zones:
        if z.category != "sensor" or not z.separation or z.label not in zone_pos:
            continue
        x, y = _fp_cell_xy(*zone_pos[z.label])
        m = 6.0
        parts.append(
            f'<rect x="{x - m:.0f}" y="{y - m:.0f}" width="{_FP_ZW + 2 * m:.0f}" '
            f'height="{_FP_ZH + 2 * m:.0f}" rx="10" fill="none" stroke="#dc2626" '
            f'stroke-width="1.4" stroke-dasharray="5,3"/>'
        )
        parts.append(
            f'<text x="{x + _FP_ZW / 2:.0f}" y="{y + _FP_ZH + m + 11:.0f}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="9" '
            f'fill="#dc2626">thermal keep-out</text>'
        )
        fenced.append((z, x, y))

    # Zone rects + wrapped labels, coloured by category.
    for z in zones:
        x, y = _fp_cell_xy(*zone_pos[z.label])
        s = _category_style(z.category)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{_FP_ZW}" height="{_FP_ZH}" rx="8" '
            f'fill="{s["fill"]}" stroke="{s["stroke"]}" stroke-width="1.4"/>'
        )
        spans = _label_tspans(z.label, x + _FP_ZW / 2, y + _FP_ZH / 2, 18, 15)
        parts.append(
            f'<text text-anchor="middle" font-family="sans-serif" font-size="12" '
            f'fill="{s["text"]}" font-weight="600">{spans}</text>'
        )

    # One airflow arrow + "vent clearance" toward the nearest board edge for any
    # fenced sensor placed at an edge (e.g. a PM sensor that needs intake airflow).
    _EDGE = {"edge", "top", "bottom", "left", "right", "corner"}
    for z, x, y in fenced:
        if z.placement not in _EDGE:
            continue
        cx, cy = x + _FP_ZW / 2, y + _FP_ZH / 2
        edge = min(
            {"top": cy - by0, "bottom": by1 - cy, "left": cx - bx0, "right": bx1 - cx}.items(),
            key=lambda kv: kv[1],
        )[0]
        # Start at the zone edge facing the board boundary and vent just past it,
        # so the arrow never crosses the zone label.
        if edge == "top":
            arrow, lx, ly, anchor = (cx, y, cx, by0 - 6), cx + 12, (y + by0) / 2, "start"
        elif edge == "bottom":
            arrow, lx, ly, anchor = (cx, y + _FP_ZH, cx, by1 + 6), cx + 12, (y + _FP_ZH + by1) / 2, "start"
        elif edge == "left":
            arrow, lx, ly, anchor = (x, cy, bx0 - 6, cy), (x + bx0) / 2, cy - 5, "middle"
        else:
            arrow, lx, ly, anchor = (x + _FP_ZW, cy, bx1 + 6, cy), (x + _FP_ZW + bx1) / 2, cy - 5, "middle"
        parts.append(
            f'<line x1="{arrow[0]:.0f}" y1="{arrow[1]:.0f}" x2="{arrow[2]:.0f}" '
            f'y2="{arrow[3]:.0f}" stroke="#0e7490" stroke-width="1.6" marker-end="url(#vent)"/>'
        )
        parts.append(
            f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="{anchor}" '
            f'font-family="sans-serif" font-size="9" fill="#0e7490">vent clearance</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _floorplan_fallback_svg(result: RunResponse) -> str:
    """Category-clustered grid of the architecture blocks (no zones available)."""
    blocks = result.architecture.blocks
    if not blocks:
        return _placeholder_svg("Floorplan sketch unavailable")

    def _cat_key(b):
        return _CATEGORY_ORDER.index(b.category) if b.category in _CATEGORY_ORDER else len(_CATEGORY_ORDER)

    ordered = sorted(blocks, key=_cat_key)
    cols = 3
    rows = (len(ordered) + cols - 1) // cols
    width = cols * _FP_ZW + (cols - 1) * _FP_GAP + _FP_PAD * 2
    height = rows * _FP_ZH + (rows - 1) * _FP_GAP + _FP_PAD * 2

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="{_FP_PAD / 2}" y="{_FP_PAD / 2}" width="{width - _FP_PAD}" '
        f'height="{height - _FP_PAD}" rx="8" fill="none" stroke="#10b981" '
        f'stroke-width="1.5" stroke-dasharray="6,3"/>',
    ]
    for i, b in enumerate(ordered):
        row, col = divmod(i, cols)
        x = _FP_PAD + col * (_FP_ZW + _FP_GAP)
        y = _FP_PAD + row * (_FP_ZH + _FP_GAP)
        s = _category_style(b.category)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{_FP_ZW}" height="{_FP_ZH}" rx="6" '
            f'fill="{s["fill"]}" stroke="{s["stroke"]}" stroke-width="1.2"/>'
        )
        spans = _label_tspans(b.name, x + _FP_ZW / 2, y + _FP_ZH / 2, 18, 15)
        parts.append(
            f'<text text-anchor="middle" font-family="sans-serif" font-size="12" '
            f'fill="{s["text"]}" font-weight="600">{spans}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def generate_report_pdf(
    result: RunResponse, requirements_text: str, project_name: str,
    architecture_svg: str | None = None,
) -> bytes:
    """Render the PCB Design Brief to PDF bytes.

    WeasyPrint is imported lazily so this module loads even where its system
    libraries are absent; callers that cannot tolerate failure should guard the
    call (the /generate handler does). When the client passes its ELK-routed
    ``architecture_svg`` it is embedded as-is; otherwise the Python fallback
    diagram is rendered.
    """
    from weasyprint import HTML  # lazy import; needs Pango/Cairo at runtime

    context = _report_context(result, requirements_text, project_name)
    context["architecture_svg"] = architecture_svg or _architecture_svg(result)
    # The client ELK export carries its own legend (also needed by the standalone
    # KiCad bitmap); only the Python fallback relies on the separate HTML legend.
    context["diagram_has_legend"] = architecture_svg is not None
    context["floorplan_svg"] = _floorplan_svg(result)

    html = _jinja_env.get_template("report.html.j2").render(**context)
    return HTML(string=html).write_pdf()
