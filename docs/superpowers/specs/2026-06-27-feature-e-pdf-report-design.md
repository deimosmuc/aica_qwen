# Feature E: Professional PDF Report — Design

**Date:** 2026-06-27
**Status:** Approved (design)
**Track:** Agent Society / AI Circuit Architect

## Goal

Produce a polished, English-language PDF "PCB Design Brief" that summarises the full
multi-agent run — requirements, architecture, key findings, and the PCB-Readiness pack
— in a form that looks credible to a professional electronics company. The PDF is
downloadable from the Auto-Run result view and from the final step of the Step-by-Step
view.

## Design Decisions (locked during brainstorming)

- **Language:** English.
- **Style:** "Clean Tech" — white pages, teal (`#0d9488`) accent, blue logo, dense and
  professional. **No full-page dark cover.** Instead a slim branded header band with the
  logo and a teal underline; content flows immediately on white.
- **Length:** Two pages, densely packed (not four).
- **Logo:** The real AI Circuit Architect logo (stylised "A" with copper PCB traces),
  3D-gradient variant, supplied as **PNG**. Embedded as a raster image — no SVG
  reconstruction.
- **Renderer:** WeasyPrint (HTML + CSS → PDF) via a Jinja2 template.
- **Download placement:** Both the Auto-Run result view and Step-by-Step step 5.

## Page Layout

### Page 1 — Header · Summary · Architecture
1. **Header band:** logo (left) + product name + "PCB Design Brief · <date> · v1" (right),
   teal bottom border.
2. **Title block:** project title + one-line description.
3. **Stats strip:** inline 4-cell strip — Layerstack, Net Classes, Min Clearance, Open TODOs.
4. **Executive Summary:** 4–6 bullet lines with status glyphs (✓ done, ⚠ TODO, ! needs human review).
5. **System Architecture:** block diagram (deterministic SVG generated in Python) showing
   functional blocks and interfaces, with a power-rail caption.

### Page 2 — PCB Recommendations · Floorplan · Packages
1. **Slim running header:** small logo + product name (left), "PCB-Readiness Pack" (right).
2. **Net Class Constraints table:** class, track width, clearance, nets. (Global via
   drill/annular ring shown in the footer caption, since they live in the shared
   `ConstraintSet`, not per net class.)
3. **Floorplan Sketch:** deterministic SVG of placement zones with isolation keepout line.
4. **Package Hints table:** two-column component → package list.
5. **Disclaimer:** amber callout — AI-generated draft, requires qualified review.
6. **Footer:** "Constraints exported to pcb_constraints.kicad_dru" + page number.

## Architecture

### New module: `app/generators/report.py`
Single responsibility: turn a `RunResponse` (+ requirements text + project name) into PDF bytes.

```
generate_report_pdf(result: RunResponse, requirements_text: str, project_name: str) -> bytes
```

Internals (all pure, independently testable):
- `_report_context(result, requirements_text, project_name) -> dict` — flattens the
  `RunResponse` into a template-ready context. Exact source fields:
  - title/description: derived from `requirements_text` / `result.requirements`.
  - stats: `result.pcb_readiness.layerstack`; `len(result.pcb_readiness.netclasses)`;
    `result.pcb_readiness.constraints.min_clearance_mm`; open-TODO count =
    `len(result.arbitration.todo)`.
  - summary bullets: built from `result.arbitration.todo` (⚠) and
    `result.arbitration.human_review` (!), plus ✓ lines counting requirements,
    architecture blocks and interfaces.
  - net-class rows: from `result.pcb_readiness.netclasses` — `name`, `min_width_mm`,
    `clearance_mm`, `nets`. (Via drill/annular are **global**, in
    `result.pcb_readiness.constraints`, so they are shown once in the footer caption,
    not per row.)
  - package-hint rows: `result.pcb_readiness.package_hints` — `component_type`,
    `recommended_package`.
  - footer metadata + ISO date.
- `_architecture_svg(result) -> str` — deterministic block-diagram SVG string built from
  `result.architecture.blocks` (label = `Block.name`) with edges from
  `result.architecture.connections` (`source`/`target`/`type`); `type` drives the line
  style (power = dashed, data/control/debug = solid). No layout engine; a simple grid
  placement (max N per row) with straight connector lines. Returns inline `<svg>…</svg>`.
- `_floorplan_svg(result) -> str` — deterministic placement-zone SVG built from the same
  blocks, grouping power vs. logic and drawing an isolation keepout line when an isolated
  net class (e.g. RS-485, USB) is present. Returns inline `<svg>…</svg>`.
- `_logo_data_uri() -> str` — reads the bundled PNG and returns a `data:image/png;base64,…`
  URI so the template is fully self-contained (no external file resolution at render time).
- The HTML is rendered from a Jinja2 template, then `weasyprint.HTML(string=...).write_pdf()`
  returns the bytes.

Both SVG builders degrade gracefully: if `result.architecture` is `None` or has no blocks,
they return a small "diagram unavailable" placeholder rather than raising.

### New template: `app/templates/report.html.j2`
Self-contained HTML document with an embedded `<style>` block (print CSS: `@page` size A4,
margins, the header band, section rules, tables, the teal accent, the amber disclaimer).
SVG diagrams and the logo data-URI are injected as pre-rendered strings (marked safe).
No external assets, no `mix-blend-mode` needed since there is no dark background.

### Logo asset
`app/static/assets/logo.png` — the supplied 3D-gradient PNG, committed to the repo and read
by `_logo_data_uri()`.

### Wiring into the existing flow
The PDF is produced inside the existing `POST /api/generate` handler, which already has the
approved `RunResponse`, the requirements text, and a `project_dir`:
- After `generate_scaffold(...)`, call `generate_report_pdf(...)` and write the bytes to
  `project_dir / "AI_Circuit_Architect_Report.pdf"`.
- Because the report file lives in `project_dir` **before** `create_project_zip(project_dir)`,
  it is automatically included in the downloadable ZIP as well.
- Extend `GenerateResponse` with `report_url: str | None`. Populate it with
  `/api/report/{project_id}`.
- Add `GET /api/report/{project_id}` — mirrors the existing `download` endpoint: validates
  the id is alphanumeric (path-traversal guard), 404s if the PDF is missing, returns a
  `FileResponse` with `media_type="application/pdf"` and a friendly filename.

Report generation is best-effort: if WeasyPrint raises, log and continue (the ZIP and
validation still succeed); `report_url` is left `None` and the button is hidden.

### Frontend (`app/static/index.html`)
- Auto-Run result view: add a "Download PDF Report" button next to the existing ZIP
  download, shown only when `report_url` is present.
- Step-by-Step view: after step 5 (PCB Engineer), the same button, bound to the same
  `report_url` from the generate response.
- Both reuse the existing download styling; the button is an `<a :href="report_url">` so the
  browser handles the download directly.

## Data Flow

```
/run  → RunResponse (architecture + pcb_readiness + trace)   [no files]
  │  user approves
  ▼
/generate
  ├─ generate_scaffold(...)            → KiCad files in project_dir
  ├─ generate_report_pdf(...)          → project_dir/AI_Circuit_Architect_Report.pdf
  ├─ create_project_zip(project_dir)   → ZIP now contains the PDF too
  └─ GenerateResponse{ download_url, report_url, ... }
  ▼
Frontend shows "Download ZIP" + "Download PDF Report"
/report/{id} → FileResponse(application/pdf)
```

## Error Handling
- `generate_report_pdf` never raises out of `/generate`; failures are caught, logged, and
  `report_url` stays `None`.
- SVG builders return placeholders instead of raising on missing/empty architecture.
- `/report/{id}` validates the id (alphanumeric only) and 404s on a missing file.
- WeasyPrint system libs (Pango/Cairo) are already present in the Docker image (KiCad pulls
  them in); for local dev without them, the caught failure path keeps the app working.

## Testing Strategy
- `_report_context`: given a known `RunResponse` (reuse mock fixtures), assert title,
  stat counts (net-class count, open-TODO count, min clearance), and summary bullet contents.
- `_architecture_svg` / `_floorplan_svg`: assert returned string starts with `<svg`, contains
  each block label, and returns the placeholder for empty architecture.
- `_logo_data_uri`: asserts it returns a `data:image/png;base64,` prefix.
- `generate_report_pdf`: asserts the returned bytes start with `%PDF-` (skips with a clear
  message if WeasyPrint isn't importable, so CI without system libs still passes).
- Endpoint: `GET /api/report/{id}` returns 400 for non-alphanumeric id, 404 for unknown id.
- `/generate` integration: with mock mode, `report_url` is populated and the PDF exists in
  `project_dir` and inside the ZIP.

## Dependencies
- Add `weasyprint>=62,<66` to `requirements.txt`.

## Out of Scope (YAGNI)
- No configurable templates/themes, no multi-language, no charts beyond the two SVG diagrams,
  no per-section page-break tuning beyond what the two-page layout needs.
