# Feature E: Professional PDF Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a polished 2-page English "PCB Design Brief" PDF from a pipeline run, embedded in the project ZIP and downloadable from the UI after approval.

**Architecture:** A new pure module `app/generators/report.py` flattens a `RunResponse` into a Jinja2 context, builds two deterministic SVG diagrams (architecture + floorplan), and renders `app/templates/report.html.j2` to PDF bytes via WeasyPrint. The PDF is written into `project_dir` inside the existing `POST /api/generate` handler (so it lands in the ZIP automatically), exposed via a new `GET /api/report/{id}` endpoint, and offered as a download button in the shared generate-result panel.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Jinja2, WeasyPrint, Alpine.js.

**Reference spec:** `docs/superpowers/specs/2026-06-27-feature-e-pdf-report-design.md`

---

## ⚠️ One-time setup before Task 2

The report header embeds the real logo. **Save the supplied logo PNG (3D-gradient "A" variant) to `app/static/assets/logo.png`** before running Task 2. If the file is absent the code degrades gracefully (header shows text only), but the report will not look finished without it. Create the directory first:

```bash
mkdir -p app/static/assets
# then copy the logo PNG to app/static/assets/logo.png
```

---

## Key facts the implementer needs (from the real codebase)

- `RunResponse` (`app/models/schemas.py:178`) fields used: `requirements`, `architecture`
  (`Architecture` with `blocks: list[Block]`, `connections: list[Connection]`,
  `interfaces: list[str]`, `power: list[str]`), `arbitration` (`Arbitration` with
  `todo: list[str]`, `human_review: list[str]`), `pcb_readiness: PcbReadiness | None`.
- `Block` = `{name, sheet, purpose}`. `Connection` = `{source, target, type}` where
  `type ∈ {"power","data","control","debug"}`.
- `PcbReadiness` = `{layerstack: "2-layer"|"4-layer"|"6-layer", layerstack_reason,
  netclasses: list[NetClass], constraints: ConstraintSet, floorplan_text,
  floorplan_ascii, package_hints: list[PackageHint]}`.
- `NetClass` = `{name, min_width_mm, clearance_mm, nets: list[str]}`.
- `ConstraintSet` = `{min_clearance_mm, min_track_width_mm, via_drill_mm, via_annular_ring_mm}`.
- `PackageHint` = `{component_type, recommended_package, reason}`.
- A ready-made fixture exists: `from app.services.mock import mock_run`; `mock_run("...")`
  returns a fully-populated `RunResponse` whose `pcb_readiness` has layerstack `"4-layer"`,
  4 net classes (`PWR`, `Signal`, `USB`, `RS485`), `min_clearance_mm == 0.2`, and package
  hints starting with `component_type == "STM32 MCU"`.
- `GenerateResponse` (`app/models/schemas.py:226`): `{project_id, validation,
  preview_svg_url, download_url, files}` — to be extended with `report_url`.
- `POST /api/generate` (`app/api/routes.py:74-112`) and `GET /api/download/{id}`
  (`app/api/routes.py:115-128`) are the patterns to follow.
- Tests live flat in `tests/` and run with `pytest`. Run a single test with
  `python -m pytest tests/test_x.py::test_y -v`.

---

## File Structure

- **Create** `app/generators/report.py` — PDF report generation (context flattening, SVG
  builders, logo embedding, WeasyPrint render). One responsibility: `RunResponse` → PDF bytes.
- **Create** `app/templates/report.html.j2` — self-contained HTML+CSS report document.
- **Create** `app/static/assets/logo.png` — bundled logo (manual setup, see above).
- **Create** `tests/test_report.py` — unit tests for the report module.
- **Modify** `requirements.txt` — add WeasyPrint.
- **Modify** `app/models/schemas.py` — add `report_url` to `GenerateResponse`.
- **Modify** `app/api/routes.py` — generate the PDF in `/generate`; add `/report/{id}`.
- **Modify** `tests/test_generate_endpoint.py` — assert `report_url` + PDF in ZIP.
- **Modify** `app/static/index.html` — add the "Download PDF Report" button.

---

## Task 1: Add WeasyPrint dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Add this line to `requirements.txt` directly after the `jinja2>=3.1,<4.0` line:

```
weasyprint>=62,<66
```

- [ ] **Step 2: Install it**

Run: `python -m pip install "weasyprint>=62,<66"`
Expected: installs WeasyPrint and its Python deps. On Windows it needs the GTK/Pango
libraries; if `import weasyprint` later fails with an OSError about `libgobject`, that is
the known "no system libs" case the code handles gracefully — note it and continue.

- [ ] **Step 3: Check import (best-effort)**

Run: `python -c "import weasyprint; print(weasyprint.__version__)"`
Expected: prints a version like `62.3`. If it raises OSError (missing system libs), that is
acceptable for local dev — the production Docker image has Pango/Cairo via KiCad. Record the
outcome and proceed.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build(report): add WeasyPrint dependency for PDF report"
```

---

## Task 2: Logo embedding — `_logo_data_uri()`

**Files:**
- Create: `app/generators/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_report.py`:

```python
"""Feature E: PDF report generation."""
from app.generators.report import _logo_data_uri


def test_logo_data_uri_returns_png_data_uri_or_empty():
    uri = _logo_data_uri()
    # Either the bundled logo resolves to a base64 PNG data URI, or (if the asset
    # is absent in this checkout) an empty string so the header degrades to text.
    assert uri == "" or uri.startswith("data:image/png;base64,")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py::test_logo_data_uri_returns_png_data_uri_or_empty -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.generators.report'`.

- [ ] **Step 3: Write minimal implementation**

Create `app/generators/report.py`:

```python
"""Generate a professional PDF 'PCB Design Brief' from a pipeline RunResponse.

Pure, dependency-light helpers plus a single WeasyPrint render entry point. All
helpers are independently testable; WeasyPrint is imported lazily so the rest of
the module (and its tests) work even where the system libraries are absent.
"""
from __future__ import annotations

import base64
from pathlib import Path

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report.py::test_logo_data_uri_returns_png_data_uri_or_empty -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/generators/report.py tests/test_report.py
git commit -m "feat(report): logo data-URI embedding helper"
```

---

## Task 3: Flatten the run into a template context — `_report_context()`

**Files:**
- Modify: `app/generators/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report.py`:

```python
from app.generators.report import _report_context
from app.services.mock import mock_run


def test_report_context_core_fields():
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    ctx = _report_context(result, "A 24V industrial board with an STM32 and RS485.", "project")

    # Stats come straight from pcb_readiness.
    assert ctx["layerstack"] == "4-layer"
    assert ctx["net_class_count"] == 4
    assert ctx["min_clearance_mm"] == 0.2
    assert ctx["open_todo_count"] == len(result.arbitration.todo)

    # Net-class rows preserve order and key fields.
    assert [r["name"] for r in ctx["net_classes"]] == ["PWR", "Signal", "USB", "RS485"]
    assert ctx["net_classes"][0]["nets"]  # non-empty

    # Package hints are flattened to component -> package.
    assert ctx["package_hints"][0]["component_type"] == "STM32 MCU"

    # Global via constraints surface for the footer caption.
    assert ctx["via_drill_mm"] == 0.4
    assert ctx["via_annular_ring_mm"] == 0.15

    # Summary bullets include the human-review and todo items.
    bullet_text = " ".join(ctx["summary_bullets"])
    for item in result.arbitration.human_review:
        assert item in bullet_text


def test_report_context_handles_missing_pcb():
    result = mock_run("x")
    result.pcb_readiness = None
    ctx = _report_context(result, "x", "project")
    # Degrades to safe defaults instead of raising.
    assert ctx["layerstack"] == "—"
    assert ctx["net_class_count"] == 0
    assert ctx["net_classes"] == []
    assert ctx["package_hints"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py::test_report_context_core_fields tests/test_report.py::test_report_context_handles_missing_pcb -v`
Expected: FAIL with `ImportError: cannot import name '_report_context'`.

- [ ] **Step 3: Write minimal implementation**

Add to `app/generators/report.py` (imports at top, function below `_logo_data_uri`):

```python
from datetime import date

from app.models.schemas import RunResponse
```

```python
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
```

> NOTE: `result.requirements.requirements` is the structured requirements list on the
> `Requirements` model (verified against `app/models/schemas.py:48`). The test does not pin
> its exact count — it only asserts the human-review items appear in the bullet text.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/generators/report.py tests/test_report.py
git commit -m "feat(report): flatten RunResponse into PDF template context"
```

---

## Task 4: Architecture block diagram — `_architecture_svg()`

**Files:**
- Modify: `app/generators/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report.py`:

```python
from app.generators.report import _architecture_svg


def test_architecture_svg_contains_block_labels():
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    svg = _architecture_svg(result)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # Every block name should appear as a label.
    for block in result.architecture.blocks:
        assert block.name in svg


def test_architecture_svg_placeholder_when_empty():
    result = mock_run("x")
    result.architecture.blocks = []
    svg = _architecture_svg(result)
    assert svg.startswith("<svg")
    assert "unavailable" in svg.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py::test_architecture_svg_contains_block_labels tests/test_report.py::test_architecture_svg_placeholder_when_empty -v`
Expected: FAIL with `ImportError: cannot import name '_architecture_svg'`.

- [ ] **Step 3: Write minimal implementation**

Add to `app/generators/report.py`:

```python
from xml.sax.saxutils import escape

# Layout constants for the deterministic diagrams (viewBox units).
_COLS = 3
_BOX_W = 150
_BOX_H = 56
_GAP_X = 30
_GAP_Y = 40
_PAD = 12


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/generators/report.py tests/test_report.py
git commit -m "feat(report): deterministic architecture block-diagram SVG"
```

---

## Task 5: Floorplan sketch — `_floorplan_svg()`

**Files:**
- Modify: `app/generators/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report.py`:

```python
from app.generators.report import _floorplan_svg


def test_floorplan_svg_has_outline_and_zones():
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    svg = _floorplan_svg(result)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # Board outline rect present.
    assert "<rect" in svg
    # At least the first few block names are placed as zone labels.
    assert result.architecture.blocks[0].name in svg


def test_floorplan_svg_placeholder_when_empty():
    result = mock_run("x")
    result.architecture.blocks = []
    svg = _floorplan_svg(result)
    assert svg.startswith("<svg")
    assert "unavailable" in svg.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py::test_floorplan_svg_has_outline_and_zones tests/test_report.py::test_floorplan_svg_placeholder_when_empty -v`
Expected: FAIL with `ImportError: cannot import name '_floorplan_svg'`.

- [ ] **Step 3: Write minimal implementation**

Add to `app/generators/report.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add app/generators/report.py tests/test_report.py
git commit -m "feat(report): deterministic floorplan sketch SVG"
```

---

## Task 6: HTML template + `generate_report_pdf()`

**Files:**
- Create: `app/templates/report.html.j2`
- Modify: `app/generators/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Create the Jinja2 template**

Create `app/templates/report.html.j2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 14mm 14mm 12mm 14mm; }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
         color: #0f172a; font-size: 10px; margin: 0; }
  .header { display: flex; align-items: center; justify-content: space-between;
            padding-bottom: 8px; border-bottom: 2px solid #0d9488; }
  .brand { display: flex; align-items: center; gap: 10px; }
  .brand img { height: 26px; }
  .brand .name { font-size: 13px; font-weight: 700; }
  .brand .tag { font-size: 7px; color: #64748b; letter-spacing: .04em; }
  .header .meta { text-align: right; }
  .header .meta .kind { font-size: 8px; font-weight: 700; color: #0d9488;
                        text-transform: uppercase; }
  .header .meta .date { font-size: 8px; color: #94a3b8; }
  h1 { font-size: 19px; margin: 12px 0 2px; }
  .desc { font-size: 9px; color: #64748b; margin: 0 0 12px; }
  .stats { display: flex; border: 1px solid #e2e8f0; border-radius: 5px;
           overflow: hidden; margin-bottom: 14px; }
  .stats .cell { flex: 1; padding: 7px 9px; border-right: 1px solid #e2e8f0; }
  .stats .cell:last-child { border-right: none; }
  .stats .k { font-size: 7px; color: #64748b; text-transform: uppercase; }
  .stats .v { font-size: 15px; font-weight: 700; color: #0d9488; }
  .stats .v.warn { color: #f59e0b; }
  .section { display: flex; align-items: center; gap: 6px; margin: 14px 0 6px; }
  .section .bar { width: 3px; height: 14px; background: #0d9488; border-radius: 2px; }
  .section .t { font-size: 10px; font-weight: 700; text-transform: uppercase;
                letter-spacing: .05em; }
  ul.bullets { margin: 0; padding-left: 4px; list-style: none; }
  ul.bullets li { font-size: 9px; line-height: 1.6; color: #374151; }
  .diagram { border: 1px solid #f1f5f9; border-radius: 5px; background: #fcfdff;
             padding: 6px; }
  .diagram svg { width: 100%; height: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 8.5px; }
  th { background: #f0fdfa; color: #0f766e; text-align: left; padding: 4px 6px; }
  td { padding: 4px 6px; border-bottom: 1px solid #f1f5f9; }
  .disclaimer { margin-top: 12px; padding: 7px 9px; background: #fff7ed;
                border-left: 3px solid #f59e0b; border-radius: 3px;
                font-size: 8px; color: #92400e; line-height: 1.5; }
  .footer { margin-top: 10px; padding-top: 6px; border-top: 1px solid #f1f5f9;
            display: flex; justify-content: space-between; font-size: 7px;
            color: #94a3b8; }
  .page-break { page-break-before: always; }
</style>
</head>
<body>
  <div class="header">
    <div class="brand">
      {% if logo_data_uri %}<img src="{{ logo_data_uri }}" alt="logo">{% endif %}
      <div>
        <div class="name">AI Circuit Architect</div>
        <div class="tag">MULTI-AGENT ELECTRONICS ASSISTANT</div>
      </div>
    </div>
    <div class="meta">
      <div class="kind">PCB Design Brief</div>
      <div class="date">{{ iso_date }} · v1</div>
    </div>
  </div>

  <h1>{{ title }}</h1>
  <p class="desc">{{ description }}</p>

  <div class="stats">
    <div class="cell"><div class="k">Layerstack</div><div class="v">{{ layerstack }}</div></div>
    <div class="cell"><div class="k">Net Classes</div><div class="v">{{ net_class_count }}</div></div>
    <div class="cell"><div class="k">Min Clearance</div><div class="v">{{ "%.2f"|format(min_clearance_mm) }} mm</div></div>
    <div class="cell"><div class="k">Open TODOs</div><div class="v warn">{{ open_todo_count }}</div></div>
  </div>

  <div class="section"><div class="bar"></div><div class="t">Executive Summary</div></div>
  <ul class="bullets">
    {% for b in summary_bullets %}<li>{{ b }}</li>{% endfor %}
  </ul>

  <div class="section"><div class="bar"></div><div class="t">System Architecture</div></div>
  <div class="diagram">{{ architecture_svg|safe }}</div>

  <div class="page-break"></div>

  <div class="section"><div class="bar"></div><div class="t">Net Class Constraints</div></div>
  <table>
    <thead><tr><th>Class</th><th>Track (mm)</th><th>Clearance (mm)</th><th>Nets</th></tr></thead>
    <tbody>
      {% for nc in net_classes %}
      <tr><td>{{ nc.name }}</td><td>{{ "%.2f"|format(nc.min_width_mm) }}</td>
          <td>{{ "%.2f"|format(nc.clearance_mm) }}</td><td>{{ nc.nets }}</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="section"><div class="bar"></div><div class="t">Floorplan Sketch</div></div>
  <div class="diagram">{{ floorplan_svg|safe }}</div>

  <div class="section"><div class="bar"></div><div class="t">Package Hints</div></div>
  <table>
    <thead><tr><th>Component</th><th>Recommended Package</th></tr></thead>
    <tbody>
      {% for ph in package_hints %}
      <tr><td>{{ ph.component_type }}</td><td>{{ ph.recommended_package }}</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="disclaimer">⚠ AI-generated draft. All constraints and placements require
    review and sign-off by a qualified PCB designer before manufacturing.</div>

  <div class="footer">
    <div>Via drill {{ "%.2f"|format(via_drill_mm) }} mm · annular ring
      {{ "%.2f"|format(via_annular_ring_mm) }} mm · constraints exported to
      pcb_constraints.kicad_dru</div>
    <div>AI Circuit Architect</div>
  </div>
</body>
</html>
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_report.py`:

```python
import pytest

from app.generators.report import generate_report_pdf


def test_generate_report_pdf_returns_pdf_bytes():
    weasyprint = pytest.importorskip(
        "weasyprint", reason="WeasyPrint system libs not installed in this environment"
    )
    assert weasyprint  # silence unused-var linters
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    pdf = generate_report_pdf(result, "A 24V industrial board with an STM32 and RS485.", "project")
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py::test_generate_report_pdf_returns_pdf_bytes -v`
Expected: FAIL with `ImportError: cannot import name 'generate_report_pdf'` (or SKIP if
WeasyPrint is not importable — in that case the import failure still surfaces first because
the import is at module top; if you see a collection error, move the function in now and the
test will SKIP cleanly).

- [ ] **Step 4: Write minimal implementation**

Add to `app/generators/report.py`. Imports at top:

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)
```

Function (public entry point):

```python
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
```

- [ ] **Step 5: Run test to verify it passes (or skips)**

Run: `python -m pytest tests/test_report.py -v`
Expected: all prior tests PASS; `test_generate_report_pdf_returns_pdf_bytes` PASSES if
WeasyPrint imports, otherwise SKIPS with the configured reason.

- [ ] **Step 6: Commit**

```bash
git add app/generators/report.py app/templates/report.html.j2 tests/test_report.py
git commit -m "feat(report): HTML template + WeasyPrint PDF render entry point"
```

---

## Task 7: Wire into `/generate`, add `report_url` + `/report/{id}` endpoint

**Files:**
- Modify: `app/models/schemas.py:226-231`
- Modify: `app/api/routes.py`
- Test: `tests/test_generate_endpoint.py`

- [ ] **Step 1: Add `report_url` to `GenerateResponse`**

In `app/models/schemas.py`, change the `GenerateResponse` class to add one field:

```python
class GenerateResponse(BaseModel):
    project_id: str
    validation: Validation
    preview_svg_url: str | None = None
    download_url: str | None = None
    report_url: str | None = None
    files: list[str] = []
```

- [ ] **Step 2: Write the failing endpoint test**

Append to `tests/test_generate_endpoint.py`:

```python
def test_generate_includes_pdf_report(monkeypatch, tmp_path):
    settings = Settings(kicad_enabled=False, output_dir=str(tmp_path), qwen_api_key="")
    monkeypatch.setattr(routes, "get_settings", lambda: settings)

    client = TestClient(app)
    text = "A 24V industrial board with an STM32 and RS485."
    payload = {"requirements_text": text, "result": mock_run(text).model_dump()}
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # When WeasyPrint is available the PDF is generated, listed, and downloadable.
    try:
        import weasyprint  # noqa: F401
    except Exception:
        # No system libs: report generation is best-effort, so report_url is null.
        assert data["report_url"] is None
        return

    assert data["report_url"] == f"/api/report/{data['project_id']}"
    assert "AI_Circuit_Architect_Report.pdf" in data["files"]
    pdf = client.get(data["report_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")


def test_report_endpoint_guards(monkeypatch, tmp_path):
    settings = Settings(kicad_enabled=False, output_dir=str(tmp_path), qwen_api_key="")
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    client = TestClient(app)
    assert client.get("/api/report/deadbeef").status_code == 404
    assert client.get("/api/report/bad..id").status_code == 400
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_generate_endpoint.py::test_generate_includes_pdf_report tests/test_generate_endpoint.py::test_report_endpoint_guards -v`
Expected: FAIL — `report_url` missing from response / `/api/report/...` returns 404 for the
guard test's `bad..id` case as 404 instead of 400 (route not defined yet).

- [ ] **Step 4: Implement in `app/api/routes.py`**

At the top of `app/api/routes.py`, add the import next to the other generator import:

```python
from app.generators.report import generate_report_pdf
```

Define the report filename constant near the top of the module (after imports):

```python
_REPORT_NAME = "AI_Circuit_Architect_Report.pdf"
```

In the `generate()` handler, insert PDF generation **after** `generate_scaffold(...)` and
**before** `create_project_zip(project_dir)` (so the PDF is in the ZIP). Replace this block:

```python
    create_project_zip(project_dir)
```

with:

```python
    report_url: str | None = None
    try:
        pdf_bytes = generate_report_pdf(req.result, req.requirements_text, _PROJECT_NAME)
        (project_dir / _REPORT_NAME).write_bytes(pdf_bytes)
        report_url = f"/api/report/{project_id}"
    except Exception:
        # Report is best-effort: missing WeasyPrint system libs must not break
        # scaffold generation or the ZIP. The button is simply hidden.
        report_url = None

    create_project_zip(project_dir)
```

Add `report_url=report_url,` to the `GenerateResponse(...)` constructor:

```python
    return GenerateResponse(
        project_id=project_id,
        validation=validation,
        preview_svg_url=preview_url,
        download_url=f"/api/download/{project_id}",
        report_url=report_url,
        files=files,
    )
```

Add a new endpoint directly below the existing `download()` function:

```python
@router.get("/report/{project_id}")
def report(project_id: str) -> FileResponse:
    """Download the generated PDF design brief."""
    if not project_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid project id.")
    pdf_path = Path(get_settings().output_dir) / project_id / _REPORT_NAME
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"ai-circuit-architect-{project_id}.pdf",
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate_endpoint.py -v`
Expected: PASS. `test_generate_includes_pdf_report` asserts the PDF path when WeasyPrint is
present and the `report_url is None` fallback otherwise; `test_report_endpoint_guards` passes
(400 for `bad..id`, 404 for unknown).

- [ ] **Step 6: Commit**

```bash
git add app/models/schemas.py app/api/routes.py tests/test_generate_endpoint.py
git commit -m "feat(report): generate PDF in /generate, add /report download endpoint"
```

---

## Task 8: Frontend — "Download PDF Report" button

**Files:**
- Modify: `app/static/index.html:656`

> CONTEXT: The generate-result panel (with the `⬇ Download ZIP` button at line 656) is the
> single shared result view reached after approval in **both** the Auto-Run and Step-by-Step
> flows — `gen` is one Alpine state object. Adding the button here therefore satisfies the
> "both places" requirement with one anchor.

- [ ] **Step 1: Add the PDF button next to the ZIP button**

In `app/static/index.html`, find this line (around line 656):

```html
              <a class="dl" :href="gen.download_url"><button class="approve">⬇ Download ZIP</button></a>
```

Replace it with:

```html
              <a class="dl" :href="gen.download_url"><button class="approve">⬇ Download ZIP</button></a>
              <a class="dl" :href="gen.report_url" x-show="gen.report_url"><button class="approve">📄 Download PDF Report</button></a>
```

- [ ] **Step 2: Verify in the browser**

Run the app and exercise a full run → approve → generate. Use the preview tooling:
start the server, reload, then `preview_snapshot` to confirm both buttons render and the
PDF button is hidden when `gen.report_url` is null. Click the PDF button and confirm a
`%PDF` download (or, if WeasyPrint libs are absent locally, confirm the button is correctly
hidden).

Expected: With WeasyPrint present, "📄 Download PDF Report" appears beside "⬇ Download ZIP"
and downloads a valid PDF. Without it, only the ZIP button shows.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "feat(report): Download PDF Report button in result view"
```

---

## Final verification

- [ ] **Run the full test suite**

Run: `python -m pytest -q`
Expected: all tests pass (report tests SKIP cleanly if WeasyPrint system libs are absent).

- [ ] **Manual smoke (if WeasyPrint installed)**

Generate a project end-to-end and open `AI_Circuit_Architect_Report.pdf` from the ZIP.
Confirm: branded header with logo, stats strip, executive summary bullets, architecture
diagram on page 1; net-class table, floorplan, package hints, disclaimer, footer on page 2.

- [ ] **Finish the branch**

Use superpowers:finishing-a-development-branch.

---

## Self-Review Notes (filled in by plan author)

- **Spec coverage:** header band + logo (T2/T6), 2-page white layout (T6 template),
  stats strip + summary + architecture (T3/T4/T6), net-class table + floorplan + packages +
  disclaimer + footer (T5/T6), generate-in-`/generate` + ZIP inclusion + `/report` endpoint +
  `report_url` (T7), button in both flows via shared panel (T8), WeasyPrint dep (T1),
  best-effort failure handling (T7), tests incl. skip-on-missing-libs (T6/T7). All covered.
- **Via-per-row correction** from the spec is honoured: net-class table has no via column;
  via drill/annular ring appear once in the footer caption (T6 template + T3 context).
- **Type consistency:** `generate_report_pdf`, `_report_context`, `_architecture_svg`,
  `_floorplan_svg`, `_logo_data_uri`, `_placeholder_svg` names are used identically across
  tasks. `report_url` field name consistent across schema/route/frontend.
- **Field names verified against the live schema:** `result.requirements.requirements`
  (schemas.py:48), `pcb_readiness.constraints.{min_clearance_mm,via_drill_mm,via_annular_ring_mm}`,
  `netclasses[].{name,min_width_mm,clearance_mm,nets}`, `package_hints[].{component_type,recommended_package}`,
  `architecture.{blocks,connections,interfaces}`, `arbitration.{todo,human_review}`.
