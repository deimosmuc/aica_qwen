"""KiCad scaffold generator — the CAD Engineer's deterministic output stage.

This is NOT an LLM agent. Per the project spec we never synthesize KiCad syntax
from scratch or let a model write it: we fill proven, minimal KiCad v9
S-expression templates (see app/templates/*.j2, derived from a hand-verified
project that opens in KiCad 10). Output is fully deterministic — the same
approved architecture always produces byte-identical files — which keeps the
scaffold testable and reviewable.

The generator turns the orchestrator's approved plan into a project directory:

    <project>.kicad_pro      KiCad project file
    <project>.kicad_sch      root schematic, one hierarchical sheet per block
    sheets/<block>.kicad_sch one placeholder sheet per functional block
    architecture.md          the proposed architecture
    todo.md                  engineering TODOs + human-review items
    assumptions.md           accepted assumptions + open questions
    agent_trace.json         the multi-agent collaboration record
    README.md                how to use the scaffold
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.generators import diagram_embed as de
from app.generators.pcb_dru import generate_dru
from app.generators.report import _architecture_svg
from app.models.schemas import Arbitration, PcbReadiness, Requirements, RunResponse

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Fixed namespace so generated UUIDs are stable across runs (deterministic output).
_UUID_NS = uuid.UUID("a1c17ec7-0000-4000-8000-000000000000")

# Root sheet is A4 landscape in KiCad (297 x 210 mm).
_PAGE_W = 297.0

# Sheet placement grid on the A4 root sheet (mm).
_GRID_COLS = 3
_GRID_X0, _GRID_Y0 = 30.0, 40.0
_GRID_DX, _GRID_DY = 70.0, 55.0
_SHEET_W, _SHEET_H = 40, 30

# Embedded block-diagram image: bounding box (mm) and top margin on the root sheet.
# Both width and height are capped so a near-square ELK layout stays compact.
_DIAGRAM_W = 120.0
_DIAGRAM_H = 44.0
_DIAGRAM_TOP = 22.0

# Connection colours (KiCad stroke RGB) and labels, keyed by Connection.type.
_CONN_COLOR = {
    "power":   (217, 119, 6),     # amber  — mirrors the 'power' category
    "data":    (37, 99, 235),     # blue
    "control": (124, 58, 237),    # violet
    "debug":   (100, 116, 139),   # slate
}
_CONN_LABEL = {"power": "Power", "data": "Data", "control": "Control", "debug": "Debug"}
_CONN_ORDER = ["power", "data", "control", "debug"]


def _env() -> Environment:
    # autoescape only applies to html/xml; our templates are plain text, so it is
    # off here — we do KiCad/string escaping explicitly via _esc().
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        keep_trailing_newline=True,
    )


def _det_uuid(project_name: str, key: str) -> str:
    return str(uuid.uuid5(_UUID_NS, f"{project_name}:{key}"))


def _esc(text: str) -> str:
    """Escape a string for use inside a KiCad S-expression quoted string."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _trunc(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _route(s: dict, t: dict) -> list[tuple[float, float]]:
    """Orthogonal route between two sheet boxes, anchored on their edges.

    Returns a polyline that leaves the source box edge, travels through the gap
    between rows/columns (never across a box), and enters the target box edge.
    Coordinates use the box origin (``x``/``y``) and the fixed 40x30 box size.
    """
    def anchors(b: dict) -> dict:
        x, y = b["x"], b["y"]
        return {"cx": x + _SHEET_W / 2, "cy": y + _SHEET_H / 2,
                "top": y, "bottom": y + _SHEET_H, "left": x, "right": x + _SHEET_W}

    a, b = anchors(s), anchors(t)
    if abs(a["cy"] - b["cy"]) < 1.0:  # same row → straight horizontal in the column gap
        if a["cx"] <= b["cx"]:
            pts = [(a["right"], a["cy"]), (b["left"], b["cy"])]
        else:
            pts = [(a["left"], a["cy"]), (b["right"], b["cy"])]
    elif a["cy"] < b["cy"]:  # source above target → down through the row gap
        ymid = (a["bottom"] + b["top"]) / 2
        pts = [(a["cx"], a["bottom"]), (a["cx"], ymid), (b["cx"], ymid), (b["cx"], b["top"])]
    else:  # source below target → up through the row gap
        ymid = (b["bottom"] + a["top"]) / 2
        pts = [(a["cx"], a["top"]), (a["cx"], ymid), (b["cx"], ymid), (b["cx"], b["bottom"])]
    return [(round(x, 2), round(y, 2)) for x, y in pts]


def _sheet_filename(raw: str, index: int) -> str:
    """Sanitise an architect-proposed sheet name into a safe .kicad_sch filename."""
    base = Path(raw or "").name.strip() or f"sheet{index + 1}.kicad_sch"
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", base)
    if not base.endswith(".kicad_sch"):
        base = base.rsplit(".", 1)[0] + ".kicad_sch" if "." in base else base + ".kicad_sch"
    return base


def _pcb_readiness_md(pcb: PcbReadiness, project_name: str) -> str:
    """Build the PCB_READINESS.md markdown report from PcbReadiness data."""
    lines: list[str] = [
        f"# PCB-Readiness Report — {project_name}",
        "",
        "_Generated by AI Circuit Architect. Review all values with a qualified PCB designer._",
        "",
        "---",
        "",
        "## Layerstack Recommendation",
        "",
        f"**{pcb.layerstack}**",
        "",
        pcb.layerstack_reason,
        "",
        "---",
        "",
        "## Net Classes",
        "",
        "| Class | Min Width | Clearance | Nets |",
        "|---|---|---|---|",
    ]
    for nc in pcb.netclasses:
        nets_str = ", ".join(nc.nets) if nc.nets else "—"
        lines.append(f"| {nc.name} | {nc.min_width_mm} mm | {nc.clearance_mm} mm | {nets_str} |")

    lines += [
        "",
        "---",
        "",
        "## Design Rules (pcb_constraints.kicad_dru)",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Min clearance | {pcb.constraints.min_clearance_mm} mm |",
        f"| Min track width | {pcb.constraints.min_track_width_mm} mm |",
        f"| Via drill | {pcb.constraints.via_drill_mm} mm |",
        f"| Via annular ring | {pcb.constraints.via_annular_ring_mm} mm |",
        "",
        "---",
        "",
        "## Floorplan",
        "",
        pcb.floorplan_text,
        "",
        "```",
        pcb.floorplan_ascii,
        "```",
        "",
        "---",
        "",
        "## Package Hints",
        "",
        "| Component Type | Recommended Package | Reason |",
        "|---|---|---|",
    ]
    for hint in pcb.package_hints:
        lines.append(f"| {hint.component_type} | {hint.recommended_package} | {hint.reason} |")

    lines += [
        "",
        "---",
        "",
        "_Configure net class assignments in the KiCad PCB editor (not in the DRU file)._",
        "",
    ]
    return "\n".join(lines)


def generate_scaffold(
    result: RunResponse,
    requirements_text: str,
    out_dir: str | Path,
    project_name: str = "project",
    generated_date: str | None = None,
    architecture_svg: str | None = None,
) -> Path:
    """Generate the full KiCad project scaffold from an approved pipeline result.

    ``generated_date`` (ISO string) only fills the title block; it is omitted by
    default so output stays byte-deterministic for the same approved plan.

    ``architecture_svg`` is the client-rendered light-themed ELK block diagram;
    when given it is embedded as the on-sheet bitmap, otherwise the Python
    fallback diagram is used.

    Returns the project directory path.
    """
    arbitration: Arbitration = result.arbitration
    architecture = arbitration.approved_architecture
    requirements: Requirements = result.requirements

    project_dir = Path(out_dir)
    sheets_dir = project_dir / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    env = _env()
    root_uuid = _det_uuid(project_name, "root")

    title_block = {
        "title": _esc(project_name),
        "company": _esc("AI Circuit Architect"),
        "rev": "DRAFT",
        "date": _esc(generated_date or ""),
        "comment": _esc("Generated scaffold — NOT production-ready, review required"),
    }

    # --- Block-diagram image (best-effort) ------------------------------------
    # Rasterise the same architecture diagram the report uses and embed it as a
    # native KiCad bitmap above the sheet hierarchy. If rasterising is unavailable
    # the image is simply omitted and the grid sits at its normal position.
    diagram_png = de.svg_to_png(architecture_svg or _architecture_svg(result))
    diagram_image = ""
    grid_y0 = _GRID_Y0
    title_y = 20.0
    if diagram_png:
        _, img_h, scale = de.fit_box(diagram_png, _DIAGRAM_W, _DIAGRAM_H)
        diagram_image = de.kicad_image_element(
            diagram_png,
            at_x=_PAGE_W / 2,
            at_y=_DIAGRAM_TOP + img_h / 2,
            scale=scale,
            uuid=_det_uuid(project_name, "diagram"),
        )
        grid_y0 = _DIAGRAM_TOP + img_h + 10.0

    # --- Plan the hierarchical sheets (unique filenames, grid placement) ------
    sheets: list[dict] = []
    used: set[str] = set()
    for i, block in enumerate(architecture.blocks):
        fname = _sheet_filename(block.sheet, i)
        if fname in used:  # avoid collisions if two blocks propose the same file
            fname = f"{fname[:-len('.kicad_sch')]}_{i + 1}.kicad_sch"
        used.add(fname)

        col, row = i % _GRID_COLS, i // _GRID_COLS
        x = _GRID_X0 + col * _GRID_DX
        y = grid_y0 + row * _GRID_DY
        sheets.append(
            {
                "name": _esc(block.name),
                "raw_name": block.name,
                "file": _esc(f"sheets/{fname}"),
                "fname": fname,
                "purpose": block.purpose,
                "x": round(x, 2),
                "y": round(y, 2),
                "y_name": round(y - 0.8, 2),
                "y_file": round(y + _SHEET_H + 0.6, 2),
                "page": i + 2,  # root is page 1
                "block_uuid": _det_uuid(project_name, f"sheet:{fname}"),
                "file_uuid": _det_uuid(project_name, f"file:{fname}"),
            }
        )

    # --- Inter-block connections (colour-coded graphic polylines) -------------
    by_name = {s["raw_name"]: s for s in sheets}
    connections: list[dict] = []
    for i, conn in enumerate(architecture.connections):
        s, t = by_name.get(conn.source), by_name.get(conn.target)
        if not s or not t or s is t:
            continue
        r, g, b = _CONN_COLOR.get(conn.type, _CONN_COLOR["data"])
        connections.append(
            {
                "pts": _route(s, t),
                "color": f"{r} {g} {b} 1",
                "uuid": _det_uuid(project_name, f"conn:{i}"),
            }
        )

    # --- Legend + notes (right gutter) ----------------------------------------
    present = [c.type for c in architecture.connections
               if c.source in by_name and c.target in by_name]
    legend: list[dict] = []
    lx, ly = 240.0, 22.0
    for j, t in enumerate(ty for ty in _CONN_ORDER if ty in present):
        y = ly + j * 6.0
        r, g, b = _CONN_COLOR[t]
        legend.append(
            {
                "x1": lx, "y1": y, "x2": lx + 7, "y2": y,
                "color": f"{r} {g} {b} 1",
                "uuid": _det_uuid(project_name, f"legend:{t}"),
                "label": _esc(_CONN_LABEL[t]),
                "label_x": lx + 9, "label_y": round(y + 0.6, 2),
                "label_uuid": _det_uuid(project_name, f"legendtext:{t}"),
            }
        )

    note_lines = ["NOTES — not production-ready"]
    note_lines += ["- " + _esc(_trunc(a, 40)) for a in arbitration.accepted_assumptions[:3]]
    note_lines += ["! " + _esc(_trunc(h, 40)) for h in arbitration.human_review[:2]]
    notes = {
        "text": "\\n".join(note_lines),
        "x": lx,
        "y": round(ly + max(len(legend), 1) * 6.0 + 8.0, 2),
        "uuid": _det_uuid(project_name, "notes"),
    }

    # Controlled-impedance interfaces anchored on the schematic (KiCad's stroke
    # font has no Ω glyph, so spell it "ohm" here; the report keeps the symbol).
    impedance_note = None
    if result.pcb_readiness is not None:
        controlled = [nc for nc in result.pcb_readiness.netclasses if nc.impedance]
        if controlled:
            imp_lines = ["CONTROLLED IMPEDANCE"]
            imp_lines += [
                _esc(f"{_trunc(nc.name, 14)}: {nc.impedance}".replace("Ω", "ohm"))
                for nc in controlled
            ]
            impedance_note = {
                "text": "\\n".join(imp_lines),
                "x": lx,
                "y": round(notes["y"] + len(note_lines) * 2.0 + 7.0, 2),
                "uuid": _det_uuid(project_name, "impedance-note"),
            }

    # Compact Design-for-X note (actionable items only; ASCII for the KiCad stroke font).
    dfx_note = None
    if result.pcb_readiness is not None:
        actionable = [d for d in result.pcb_readiness.dfx_checklist
                      if d.status in ("recommended", "missing")]
        if actionable:
            dfx_lines = ["DFT / DFM / BRING-UP"]
            dfx_lines += [_esc(_trunc(f"- {d.item}", 34)) for d in actionable[:6]]
            base_y = (impedance_note["y"] if impedance_note else notes["y"]) + 16.0
            dfx_note = {
                "text": "\\n".join(dfx_lines),
                "x": lx,
                "y": round(base_y, 2),
                "uuid": _det_uuid(project_name, "dfx-note"),
            }

    # --- Root schematic -------------------------------------------------------
    root_sch = env.get_template("root.kicad_sch.j2").render(
        root_uuid=root_uuid,
        title=_esc(f"{project_name} — AI Circuit Architect scaffold"),
        subtitle=_esc("Placeholder hierarchy — complete in KiCad. NOT production-ready."),
        title_uuid=_det_uuid(project_name, "root-title"),
        title_x=25.4,
        title_y=title_y,
        project_name=_esc(project_name),
        title_block=title_block,
        diagram_image=diagram_image,
        connections=connections,
        legend=legend,
        notes=notes,
        impedance_note=impedance_note,
        dfx_note=dfx_note,
        sheets=sheets,
    )
    (project_dir / f"{project_name}.kicad_sch").write_text(root_sch, encoding="utf-8")

    # --- Per-block subsheets --------------------------------------------------
    sheet_tpl = env.get_template("sheet.kicad_sch.j2")
    for s in sheets:
        annotation = "\\n".join(
            _esc(line)
            for line in (
                f"{s['fname'][:-len('.kicad_sch')]} (placeholder block)",
                s["purpose"],
                "TODO: replace DUMMY_* with real parts — NEEDS HUMAN REVIEW",
            )
        )
        sheet_sch = sheet_tpl.render(
            file_uuid=s["file_uuid"],
            text_uuid=_det_uuid(project_name, f"text:{s['fname']}"),
            annotation=annotation,
            title_block={
                "title": s["name"],
                "company": title_block["company"],
                "rev": title_block["rev"],
                "date": title_block["date"],
                "comment": _esc(f"{project_name} — placeholder block, NOT production-ready"),
            },
        )
        (sheets_dir / s["fname"]).write_text(sheet_sch, encoding="utf-8")

    # --- KiCad project file ---------------------------------------------------
    pro = {
        "meta": {"filename": f"{project_name}.kicad_pro", "version": 1},
        "sheets": [[root_uuid, "Root"]] + [[s["block_uuid"], s["name"]] for s in sheets],
        "text_variables": {},
    }
    (project_dir / f"{project_name}.kicad_pro").write_text(
        json.dumps(pro, indent=2), encoding="utf-8"
    )

    # --- Markdown reports + agent trace --------------------------------------
    (project_dir / "architecture.md").write_text(
        env.get_template("architecture.md.j2").render(
            blocks=architecture.blocks,
            interfaces=architecture.interfaces,
            signals=architecture.signals,
            power=architecture.power,
            placeholder_components=architecture.placeholder_components,
            notes=architecture.notes,
        ),
        encoding="utf-8",
    )
    (project_dir / "todo.md").write_text(
        env.get_template("todo.md.j2").render(
            todo=arbitration.todo, human_review=arbitration.human_review
        ),
        encoding="utf-8",
    )
    (project_dir / "assumptions.md").write_text(
        env.get_template("assumptions.md.j2").render(
            accepted_assumptions=arbitration.accepted_assumptions,
            questions=requirements.questions,
        ),
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text(
        env.get_template("README.md.j2").render(
            project_name=project_name,
            requirements_text=requirements_text.strip(),
            trace=result.trace,
        ),
        encoding="utf-8",
    )
    (project_dir / "agent_trace.json").write_text(
        json.dumps(
            {
                "project": project_name,
                "mode": result.mode,
                "request": requirements_text.strip(),
                "needs_approval": result.needs_approval,
                "steps": [step.model_dump() for step in result.trace],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --- PCB-readiness files (Feature D) -------------------------------------
    if result.pcb_readiness is not None:
        pcb = result.pcb_readiness
        (project_dir / "pcb_constraints.kicad_dru").write_text(
            generate_dru(pcb.constraints, pcb.netclasses),
            encoding="utf-8",
        )
        (project_dir / "PCB_READINESS.md").write_text(
            _pcb_readiness_md(pcb, project_name),
            encoding="utf-8",
        )

    return project_dir
