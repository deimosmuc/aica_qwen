# Smart Diagrams & Component Candidates — Design Spec

**Date:** 2026-06-27
**Status:** Approved in brainstorming, pending written-spec review.
**Track:** Polish (results + report quality). One combined feature.

## Summary

Upgrade how the system presents its engineering output so it reads like work from a
real hardware engineer, not a dumb generator:

1. **Component candidates with ratings.** For decision-worthy components the PCB
   Engineer proposes a recommended part plus up to two alternatives, each with a star
   score and type-appropriate pros/cons. No-brainers (decoupling caps, 0603 LEDs) get
   no alternatives.
2. **Functionally clustered, colour-coded block diagram.** Blocks are grouped by
   functional category (MCU, sensor, power, connectivity, debug, status) with a shared
   colour palette and a legend. Routing is **orthogonal** (90°, crossing-minimised) via
   the ELK engine the webapp already uses — no diagonal "spaghetti".
3. **Intelligent floorplan.** The floorplan stops mindlessly copying the block-diagram
   grid. It renders the PCB Engineer's actual placement zones (grouped, coloured,
   placed, with keep-out separation between power/heat and sensitive sensors).

The same colour palette is the single standard across the **live webapp diagram**, the
**PDF block diagram**, the **floorplan**, and the **legend**.

## Goals

- Output that an electronics engineer trusts on first glance: clean orthogonal routing,
  sensible functional grouping, colour categories, honest component trade-offs.
- The PDF block diagram is **WYSIWYG** with the live webapp — same ELK layout, same
  colours.
- Everything degrades gracefully (defaults, fallbacks) and keeps running keyless in Mock
  Mode for the demo.

## Non-goals / out of scope

- No real PCB placement or routing (we still only *prepare*; a human decides).
- No new graph-layout engine on the Python server side. Orthogonal routing stays in ELK
  (client). The Python report renderer only provides a clustered fallback diagram.
- No per-dimension scoring matrix — one overall star score per candidate, plus prose
  pros/cons. (Type-specific criteria surface inside the pros/cons.)
- ELK floorplan routing — the floorplan has no edges, so no router is needed.

## Locked design decisions (from brainstorming)

- **Scope:** one combined feature (candidates + smart diagrams + floorplan).
- **Where the intelligence lives:** hybrid. The LLM assigns each block a category and
  proposes groups/placement; the renderer executes it, with category-based domain rules
  as a fallback safety net.
- **Category vocabulary (fixed):** `mcu`, `sensor`, `power`, `connectivity`, `debug`,
  `status`, plus `other` as the fallback. Protection (fuse, reverse-polarity, TVS/ESD)
  counts as `power`.
- **Routing:** reuse ELK (webapp), browser hands the finished light-themed SVG to the
  report; Python fallback for API-only generation.
- **Component candidates:** PCB Engineer (qwen-max capable); 1 recommended + up to 2
  alternatives; one overall star score (0–5); type-specific criteria in pros/cons; MCU
  interface-fit kept distinct from integration.

## Category palette (single source of truth)

A `CATEGORY_STYLE` table is defined once and consumed by the Python renderer, the webapp
diagram, and the legend. Light-theme stops (fill / stroke / text):

| Category       | Colour  | fill      | stroke    | text      |
|----------------|---------|-----------|-----------|-----------|
| `mcu`          | blue    | `#E6F1FB` | `#2563EB` | `#0C447C` |
| `sensor`       | purple  | `#F3E8FF` | `#7C3AED` | `#5B21B6` |
| `power`        | amber   | `#FEF3C7` | `#D97706` | `#92400E` |
| `connectivity` | petrol  | `#D7EEF2` | `#0E7490` | `#0B4A57` |
| `debug`        | gray    | `#F1F5F9` | `#64748B` | `#334155` |
| `status`       | green   | `#DCFCE7` | `#16A34A` | `#14532D` |
| `other`        | neutral | `#F8FAFC` | `#94A3B8` | `#475569` |

Connection (edge) colours stay typed as today (power/data/control/debug), tuned for
contrast on a light background in the report SVG.

## Data model (app/models/schemas.py)

All new fields have defaults so old `RunResponse` payloads still validate and render.

- **`Block`** gains `category: Literal["mcu","sensor","power","connectivity","debug","status","other"] = "other"`.
- **Component candidates** (new):
  - `Candidate = {part: str, package: str, score: float, recommended: bool = False, pros: list[str] = [], cons: list[str] = []}` — `score` is 0–5, one decimal.
  - `ComponentChoice = {component_type: str, category: str = "other", candidates: list[Candidate] = []}`.
  - `PcbReadiness.component_choices: list[ComponentChoice] = []`.
- **Structured floorplan** (new):
  - `FloorplanZone = {label: str, category: str = "other", blocks: list[str] = [], placement: str = "center", separation: list[str] = []}`.
    - `placement` is a coarse keyword: `edge | center | corner | top | bottom | left | right`.
    - `separation` lists zone labels/categories to keep apart (drives keep-out lines).
  - `PcbReadiness.floorplan_zones: list[FloorplanZone] = []`.
- **`package_hints` stays unchanged** — still emitted, still written into `PCB_READINESS.md`
  in the ZIP. The PDF's old "Package Hints" table is replaced by candidate cards; the flat
  package list lives on in the ZIP doc, so nothing downstream breaks.
- **Transport:** `GenerateRequest` gains `architecture_svg: str | None = None` — the
  client-rendered, light-themed, ELK-routed, coloured block diagram. Validated as a
  non-empty string starting with `<svg` and under a size cap; otherwise ignored.

## Agents

### Architect (app/agents/architect.py)
Prompt addition: for every block, assign exactly one `category` from the fixed
vocabulary. Output schema gains `category` per block. Unknown/missing → `other`.

### PCB Engineer (app/agents/pcb_engineer.py)
Prompt additions (qwen-max capable), keeping all existing outputs:

- **`component_choices`:** for each *decision-worthy* component (MCU, sensors, comms/
  bridge chips, central connectors/converters) emit 1 recommended + up to 2 alternatives.
  Each candidate: `part`, `package`, `score` (0–5), `recommended` (exactly one true per
  component), `pros`, `cons`. Skip no-brainers (passives, standard LEDs). Weigh
  **type-specific criteria** and name them in pros/cons:
  - MCU: interface/peripheral fit (UART/I²C/SPI/ADC counts), integrated radios (WiFi/BT),
    compute/memory, then size/price/availability. *Interface-fit is distinct from
    integration.*
  - Sensor: measurands/integration, accuracy, then size/price/availability.
  - Power: efficiency/thermal, then size/price/availability.
  - Connector/bridge: robustness/compatibility, then size/price/availability.
  - **Package correctness matters:** e.g. a WROOM module is a castellated-edge PCB module,
    not a QFN. (The live run mislabelled this — candidate cards + human review are exactly
    the guard.)
- **`floorplan_zones`:** group blocks into labelled zones with a `category`, a coarse
  `placement`, and `separation` intent (keep sensitive sensors away from power/heat;
  PMS5003 airflow; SCD41 thermal isolation).

## Rendering

### Webapp block diagram (app/static/index.html)
The existing ELK diagram is upgraded, and becomes the source for the report SVG:
- Apply the `CATEGORY_STYLE` palette to nodes (fill/stroke/text by `block.category`).
- **Functional clustering** via ELK grouping/partitioning so same-category blocks sit
  together and MCU-adjacent categories (debug/connectivity/status) render near the MCU.
- Add a **legend** (category → colour) to the diagram panel.
- Provide a function that emits a **light-themed** variant of the routed SVG for the
  report (geometry from ELK, report styling applied), posted to `/api/generate` as
  `architecture_svg` at generate time.

### Report block diagram (app/generators/report.py)
- Embed the client `architecture_svg` when present.
- **Fallback** `_architecture_svg(result)` when absent: cluster blocks by category
  (shared palette), lay categories out with MCU-central arrangement, route edges as
  simple orthogonal L/Z segments (best effort — no diagonals), wrap/shrink long labels so
  they fit their boxes (fixes the earlier text-overflow).

### Report floorplan (app/generators/report.py)
- `_floorplan_svg(result)` renders `floorplan_zones`: one coloured rounded rect per zone
  (category palette), positioned per `placement` on a coarse board grid, with dashed
  keep-out lines between zones named in `separation`.
- **Fallback** when `floorplan_zones` is empty: the same category-clustered grid as the
  block-diagram fallback (no more blind 1:1 copy).

### Shared renderer pieces
- `CATEGORY_STYLE` dict + `_category_legend_svg()` (or HTML legend) used by both diagrams
  and the report.
- Long-label fit helper (wrap or auto-shrink) shared by the SVG builders.

## Report template (app/templates/report.html.j2)
- Replace the "Package Hints" table with **component candidate cards**: per component, the
  recommended candidate highlighted (star score + "Empfehlung" badge), alternatives below
  with their star score and pros/cons. Use **WeasyPrint-safe layout** (tables/blocks,
  minimal flex) so it renders identically in WeasyPrint and Chrome.
- Add the **category legend** near the diagrams.
- Diagrams: embedded ELK block SVG (or fallback) + floorplan SVG.

## Mock fixtures (app/services/mock.py)
Extend `mock_run` and `mock_run_rework` so the new fields are populated for the keyless
demo and deterministic tests:
- `Block.category` on every block.
- `component_choices` with a couple of multi-candidate examples (e.g. MCU module vs.
  alternative; all-in-one sensor vs. split sensors) including scores + pros/cons.
- `floorplan_zones` with placement + a separation example.

## Graceful degradation
- Missing `block.category` → `other` (neutral). Missing `component_choices` → the PDF
  simply omits the cards section (or shows package_hints as a minimal reference). Missing
  `floorplan_zones` → category-cluster fallback. Missing/invalid client `architecture_svg`
  → Python fallback diagram. None of these raise.

## Testing strategy
- **Schema:** new fields default correctly; an old-style `RunResponse` (no category /
  choices / zones) still constructs and renders.
- **Palette:** `CATEGORY_STYLE` covers every category incl. `other`; legend lists all.
- **Block diagram fallback:** groups same-category blocks; colours by category; no diagonal
  edges; long labels stay within boxes.
- **Floorplan:** renders zones when present (rect per zone, separation lines); falls back
  to category grid when absent.
- **Candidates:** context flattening exposes recommended + alternatives; star rendering
  maps score→stars; no-brainer components absent.
- **Endpoint:** `/api/generate` accepts and embeds a valid client `architecture_svg`;
  ignores/falls back on missing or malformed SVG (size cap, `<svg` prefix).
- WeasyPrint PDF-render test stays skip-on-missing-libs (Windows), as in Feature E.

## Risks
- **LLM category quality** — mitigated by `other` fallback; a future critic check could
  enforce it.
- **Client-SVG handoff fragility** — mitigated by the Python fallback; report still
  generates without a browser.
- **ELK clustering tuning** — grouping/partitioning params need iteration; the layered
  orthogonal routing already works in the webapp.
- **WeasyPrint vs Chrome layout drift** on the candidate cards — mitigated by
  WeasyPrint-safe CSS and verifying the real WeasyPrint render (Docker) before the demo.

## Affected files
- `app/models/schemas.py` — Block.category, Candidate, ComponentChoice, FloorplanZone,
  PcbReadiness fields, GenerateRequest.architecture_svg.
- `app/agents/architect.py` — category emission.
- `app/agents/pcb_engineer.py` — component_choices + floorplan_zones.
- `app/services/mock.py` — fixtures.
- `app/static/index.html` — ELK colours, clustering, legend, report-SVG export + post.
- `app/api/routes.py` — accept/validate/embed client SVG; pass to report.
- `app/generators/report.py` — CATEGORY_STYLE, legend, clustered fallback diagram,
  zone floorplan, candidate context, label-fit helper.
- `app/templates/report.html.j2` — candidate cards, legend.
- `tests/` — schema, renderer, candidate, endpoint tests; updated fixtures.
