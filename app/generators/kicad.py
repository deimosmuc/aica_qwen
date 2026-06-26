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

from app.models.schemas import Arbitration, Requirements, RunResponse

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Fixed namespace so generated UUIDs are stable across runs (deterministic output).
_UUID_NS = uuid.UUID("a1c17ec7-0000-4000-8000-000000000000")

# Sheet placement grid on the A4 root sheet (mm).
_GRID_COLS = 3
_GRID_X0, _GRID_Y0 = 30.0, 40.0
_GRID_DX, _GRID_DY = 70.0, 55.0
_SHEET_W, _SHEET_H = 40, 30


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


def _sheet_filename(raw: str, index: int) -> str:
    """Sanitise an architect-proposed sheet name into a safe .kicad_sch filename."""
    base = Path(raw or "").name.strip() or f"sheet{index + 1}.kicad_sch"
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", base)
    if not base.endswith(".kicad_sch"):
        base = base.rsplit(".", 1)[0] + ".kicad_sch" if "." in base else base + ".kicad_sch"
    return base


def generate_scaffold(
    result: RunResponse,
    requirements_text: str,
    out_dir: str | Path,
    project_name: str = "project",
) -> Path:
    """Generate the full KiCad project scaffold from an approved pipeline result.

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
        y = _GRID_Y0 + row * _GRID_DY
        sheets.append(
            {
                "name": _esc(block.name),
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

    # --- Root schematic -------------------------------------------------------
    root_sch = env.get_template("root.kicad_sch.j2").render(
        root_uuid=root_uuid,
        title=_esc(f"{project_name} — AI Circuit Architect scaffold"),
        subtitle=_esc("Placeholder hierarchy — complete in KiCad. NOT production-ready."),
        title_uuid=_det_uuid(project_name, "root-title"),
        project_name=_esc(project_name),
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

    return project_dir
