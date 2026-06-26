"""Validation stage — role: Quality Engineer.

Deterministic consistency checks on a generated scaffold (no LLM involved, like
the generator). Two layers:

1. Structural checks (always run): the files exist, the hierarchy is internally
   consistent, power rails and placeholders are present, the required reports
   exist, and nothing makes a dishonest "production-ready" claim.
2. Real KiCad checks (when kicad-cli is available): the project actually opens /
   exports in KiCad, and ERC runs. These are skipped gracefully otherwise.

Writes ``validation_report.md`` into the project directory and returns a
``Validation`` object for the API/UI.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.schemas import Check, RunResponse, Validation
from app.services.kicad_cli import KiCadCli, KiCadCliError

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_REQUIRED_REPORTS = ("README.md", "todo.md", "assumptions.md", "architecture.md", "agent_trace.json")
_PRODUCTION_READY = re.compile(r"production[ -]ready", re.IGNORECASE)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        keep_trailing_newline=True,
    )


def _has_unqualified_claim(text: str) -> bool:
    """True if 'production-ready' appears as an affirmative (non-negated) claim."""
    for m in _PRODUCTION_READY.finditer(text):
        window = text[max(0, m.start() - 12) : m.start()].lower()
        if "not" not in window:
            return True
    return False


def validate_project(
    project_dir: str | Path,
    result: RunResponse,
    kicad: KiCadCli,
    project_name: str = "project",
) -> Validation:
    project_dir = Path(project_dir)
    architecture = result.arbitration.approved_architecture
    checks: list[Check] = []
    notes: list[str] = []

    # --- Structural checks ----------------------------------------------------
    root_sch = project_dir / f"{project_name}.kicad_sch"
    root_text = root_sch.read_text(encoding="utf-8") if root_sch.is_file() else ""
    checks.append(
        Check(
            name="Root schematic present",
            passed=root_text.startswith("(kicad_sch"),
            detail=f"{project_name}.kicad_sch",
        )
    )

    pro_path = project_dir / f"{project_name}.kicad_pro"
    n_blocks = len(architecture.blocks)
    pro_ok = False
    pro_detail = "missing"
    if pro_path.is_file():
        try:
            pro = json.loads(pro_path.read_text(encoding="utf-8"))
            listed = len(pro.get("sheets", []))
            pro_ok = listed == 1 + n_blocks
            pro_detail = f"lists {listed} sheets (root + {n_blocks} blocks)"
        except json.JSONDecodeError:
            pro_detail = "invalid JSON"
    checks.append(Check(name="KiCad project file complete", passed=pro_ok, detail=pro_detail))

    sheets_dir = project_dir / "sheets"
    missing = []
    unreferenced = []
    for f in sheets_dir.glob("*.kicad_sch"):
        if f"sheets/{f.name}" not in root_text:
            unreferenced.append(f.name)
    present = sorted(p.name for p in sheets_dir.glob("*.kicad_sch"))
    if len(present) != n_blocks:
        missing.append(f"expected {n_blocks}, found {len(present)}")
    sheets_ok = not missing and not unreferenced
    checks.append(
        Check(
            name="All hierarchical sheets present and referenced",
            passed=sheets_ok,
            detail=(f"{len(present)} sheets"
                    + (f"; count: {', '.join(missing)}" if missing else "")
                    + (f"; unreferenced: {', '.join(unreferenced)}" if unreferenced else "")),
        )
    )

    checks.append(
        Check(
            name="Power rails defined",
            passed=bool(architecture.power),
            detail=", ".join(architecture.power) or "none",
        )
    )

    placeholders = architecture.placeholder_components
    marked = [c for c in placeholders if "DUMMY" in c.upper()]
    checks.append(
        Check(
            name="Placeholder components marked",
            passed=bool(placeholders) and len(marked) == len(placeholders),
            detail=f"{len(marked)}/{len(placeholders)} marked DUMMY_*",
        )
    )

    missing_reports = [r for r in _REQUIRED_REPORTS if not (project_dir / r).is_file()]
    checks.append(
        Check(
            name="Required reports present",
            passed=not missing_reports,
            detail="all present" if not missing_reports else f"missing: {', '.join(missing_reports)}",
        )
    )

    claim_files = [
        p for p in project_dir.glob("*.md") if _has_unqualified_claim(p.read_text(encoding="utf-8"))
    ]
    checks.append(
        Check(
            name="No unqualified production-ready claims",
            passed=not claim_files,
            detail="honest scaffold labelling"
            if not claim_files
            else f"claim found in: {', '.join(p.name for p in claim_files)}",
        )
    )

    # --- Real KiCad checks ----------------------------------------------------
    kicad_opens: bool | None = None
    erc_violations: int | None = None
    erc_by_severity: dict[str, int] = {}
    if kicad.available:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            try:
                kicad.export_pdf(root_sch, tmp_dir / "open_check.pdf")
                kicad_opens = True
            except KiCadCliError as e:
                kicad_opens = False
                notes.append(f"KiCad could not open/export the project: {e}")
            checks.append(
                Check(
                    name="KiCad opens & exports the project",
                    passed=bool(kicad_opens),
                    detail="kicad-cli sch export pdf succeeded" if kicad_opens else "export failed",
                )
            )
            if kicad_opens:
                try:
                    report = kicad.run_erc(root_sch, tmp_dir / "erc.json")
                    for sheet in report.get("sheets", []):
                        for v in sheet.get("violations", []):
                            sev = v.get("severity", "unknown")
                            erc_by_severity[sev] = erc_by_severity.get(sev, 0) + 1
                    erc_violations = sum(erc_by_severity.values())
                except KiCadCliError as e:
                    notes.append(f"ERC could not be run: {e}")
    else:
        notes.append("kicad-cli not available — real KiCad validation skipped.")

    validation = Validation(
        ok=all(c.passed for c in checks),
        checks=checks,
        kicad_cli_available=kicad.available,
        kicad_opens=kicad_opens,
        erc_violations=erc_violations,
        erc_by_severity=erc_by_severity,
        notes=notes,
    )

    # --- Report ---------------------------------------------------------------
    (project_dir / "validation_report.md").write_text(
        _env().get_template("validation_report.md.j2").render(validation=validation),
        encoding="utf-8",
    )
    return validation
