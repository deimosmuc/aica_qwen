# Smart Diagrams & Component Candidates — Phase 1 (Backend + Report) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the engineering output read like a real hardware engineer's: category-coloured block diagram, honest component candidate cards, and an intelligent zone floorplan — all on the backend + report side, degrading gracefully and running keyless in Mock Mode.

**Architecture:** New schema fields (all defaulted) carry a `category` per block, `component_choices` and `floorplan_zones` on `PcbReadiness`, and a client `architecture_svg` on `GenerateRequest`. The Architect/PCB-Engineer prompts emit them; mock fixtures populate them; the Python report renderer gains a shared `CATEGORY_STYLE` palette, a clustered fallback block diagram, a zone floorplan, candidate cards, and a legend. The live ELK/visual upgrade in `index.html` is **explicitly Phase 2** (needs human visual review) — the report uses the Python fallback until then.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, Jinja2, WeasyPrint (lazy), pytest.

**Out of scope (Phase 2):** `app/static/index.html` ELK colour/clustering/legend + client SVG export & POST. The `GenerateRequest.architecture_svg` contract is wired now so Phase 2 only touches the client.

---

## File Structure

- `app/models/schemas.py` — `Block.category`; new `Candidate`, `ComponentChoice`, `FloorplanZone`; `PcbReadiness.component_choices` + `.floorplan_zones`; `GenerateRequest.architecture_svg`.
- `app/agents/architect.py` — prompt emits `category` per block (parse is automatic via `model_validate`).
- `app/agents/pcb_engineer.py` — prompt emits `component_choices` + `floorplan_zones`; `run()` parses them.
- `app/services/mock.py` — fixtures gain categories, component_choices, floorplan_zones.
- `app/generators/report.py` — `CATEGORY_STYLE` + helpers, clustered fallback block diagram, zone floorplan, candidate context, label-fit helper, `architecture_svg` pass-through.
- `app/templates/report.html.j2` — candidate cards replace package-hints table; category legend.
- `app/api/routes.py` — accept/validate/embed client `architecture_svg`.
- `tests/` — schema, palette, agent-parse, mock, renderer, candidate, endpoint tests.

---

## Task 1: Schema additions

**Files:**
- Modify: `app/models/schemas.py` (Block ~68-71; after PackageHint ~133; PcbReadiness ~136-143; GenerateRequest ~218-223)
- Test: `tests/test_pcb_schemas.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pcb_schemas.py — append
from app.models.schemas import (
    Block, Candidate, ComponentChoice, FloorplanZone, PcbReadiness,
    ConstraintSet, GenerateRequest, RunResponse,
)
from app.services.mock import mock_run


def test_block_category_defaults_to_other():
    assert Block(name="X", sheet="x.kicad_sch", purpose="p").category == "other"
    assert Block(name="M", sheet="m.kicad_sch", purpose="p", category="mcu").category == "mcu"


def test_candidate_and_choice_defaults():
    c = Candidate(part="STM32G0", package="LQFP-48")
    assert c.score == 0.0 and c.recommended is False and c.pros == [] and c.cons == []
    cc = ComponentChoice(component_type="MCU")
    assert cc.category == "other" and cc.candidates == []


def test_floorplan_zone_defaults():
    z = FloorplanZone(label="Power")
    assert z.category == "other" and z.placement == "center"
    assert z.blocks == [] and z.separation == []


def test_pcb_readiness_new_fields_default_empty():
    pcb = mock_run("x").pcb_readiness
    # mock provides them (Task 5); the schema itself defaults to empty lists:
    bare = PcbReadiness(
        layerstack="2-layer", layerstack_reason="r", netclasses=[],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                   via_drill_mm=0.3, via_annular_ring_mm=0.1),
        floorplan_text="", floorplan_ascii="", package_hints=[],
    )
    assert bare.component_choices == [] and bare.floorplan_zones == []


def test_generate_request_architecture_svg_optional():
    req = GenerateRequest(requirements_text="x", result=mock_run("x"))
    assert req.architecture_svg is None
```

- [ ] **Step 2: Run, expect failure** — `.venv/Scripts/python.exe -m pytest tests/test_pcb_schemas.py -q` → ImportError / AttributeError.

- [ ] **Step 3: Implement schema changes**

```python
# Block — add category
class Block(BaseModel):
    name: str
    sheet: str
    purpose: str
    category: Literal["mcu", "sensor", "power", "connectivity", "debug", "status", "other"] = "other"

# after PackageHint, before PcbReadiness
class Candidate(BaseModel):
    """One concrete part option for a decision-worthy component."""
    part: str
    package: str
    score: float = 0.0            # overall 0–5, one decimal
    recommended: bool = False
    pros: list[str] = []
    cons: list[str] = []


class ComponentChoice(BaseModel):
    component_type: str
    category: str = "other"
    candidates: list[Candidate] = []


class FloorplanZone(BaseModel):
    label: str
    category: str = "other"
    blocks: list[str] = []
    placement: str = "center"     # edge|center|corner|top|bottom|left|right
    separation: list[str] = []    # zone labels/categories to keep apart

# PcbReadiness — add two defaulted fields at the end
    component_choices: list[ComponentChoice] = []
    floorplan_zones: list[FloorplanZone] = []

# GenerateRequest — add
    architecture_svg: str | None = Field(
        default=None, description="Client-rendered light-themed ELK block diagram SVG."
    )
```

- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit** — `git add app/models/schemas.py tests/test_pcb_schemas.py && git commit -m "feat(schema): block category, component candidates, floorplan zones, client svg"`

---

## Task 2: CATEGORY_STYLE palette + legend helper

**Files:**
- Modify: `app/generators/report.py` (near top, after layout constants ~30)
- Test: `tests/test_report.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report.py — append
from app.generators.report import CATEGORY_STYLE, _category_style, _legend_entries


def test_category_style_covers_all_categories():
    for cat in ["mcu", "sensor", "power", "connectivity", "debug", "status", "other"]:
        s = CATEGORY_STYLE[cat]
        assert set(s) == {"fill", "stroke", "text"}
        assert all(v.startswith("#") for v in s.values())


def test_category_style_unknown_falls_back_to_other():
    assert _category_style("banana") == CATEGORY_STYLE["other"]


def test_legend_entries_lists_present_categories_in_order():
    result = mock_run("x")
    entries = _legend_entries(result)
    labels = [e["label"] for e in entries]
    # at least power + mcu present in the mock architecture (Task 5)
    assert "Power" in labels and "MCU" in labels
    # each entry carries display label + fill + stroke
    assert all({"label", "fill", "stroke"} <= set(e) for e in entries)
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement palette + helpers**

```python
# Single source of truth for category colours (light theme). Mirrors the design spec.
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
```

- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(report): shared CATEGORY_STYLE palette + legend entries"`

---

## Task 3: Architect emits block category

**Files:**
- Modify: `app/agents/architect.py` (SYSTEM_PROMPT)
- Test: `tests/test_architect_category.py` (new)

- [ ] **Step 1: Write failing test** (stub ChatClient — agents only need `chat_json`)

```python
# tests/test_architect_category.py
from app.agents.architect import SystemArchitectAgent, SYSTEM_PROMPT
from app.models.schemas import Requirements


class _StubClient:
    def __init__(self, payload): self._p = payload
    def chat_json(self, system, user): return self._p


def test_architect_prompt_requests_category():
    assert "category" in SYSTEM_PROMPT.lower()


def test_architect_parses_block_category():
    payload = {
        "blocks": [{"name": "MCU", "sheet": "mcu.kicad_sch", "purpose": "core", "category": "mcu"}],
        "interfaces": [], "signals": [], "power": [], "placeholder_components": [],
        "connections": [], "notes": [],
    }
    arch = SystemArchitectAgent().run(_StubClient(payload), Requirements())
    assert arch.blocks[0].category == "mcu"


def test_architect_missing_category_defaults_other():
    payload = {"blocks": [{"name": "X", "sheet": "x.kicad_sch", "purpose": "p"}],
               "interfaces": [], "signals": [], "power": [], "placeholder_components": [],
               "connections": [], "notes": []}
    arch = SystemArchitectAgent().run(_StubClient(payload), Requirements())
    assert arch.blocks[0].category == "other"
```

- [ ] **Step 2: Run, expect failure** (prompt assertion fails).

- [ ] **Step 3: Edit SYSTEM_PROMPT** — change the blocks bullet to require a category:

```
- "blocks": array of objects, each {"name": str, "sheet": str, "purpose": str,
  "category": one of "mcu" | "sensor" | "power" | "connectivity" | "debug" | "status" | "other"}
  where "sheet" is a lowercase filename ending in ".kicad_sch". Assign exactly one
  category per block; protection (fuse, reverse-polarity, TVS/ESD) counts as "power";
  use "other" only when nothing fits.
```

(No code change to `run()` — `Architecture.model_validate` already parses `category`.)

- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(architect): assign a functional category to each block"`

---

## Task 4: PCB Engineer emits component_choices + floorplan_zones

**Files:**
- Modify: `app/agents/pcb_engineer.py` (imports, SYSTEM_PROMPT, `run()` parse)
- Test: `tests/test_pcb_engineer_choices.py` (new)

- [ ] **Step 1: Write failing test**

```python
# tests/test_pcb_engineer_choices.py
from app.agents.pcb_engineer import PcbEngineerAgent, SYSTEM_PROMPT
from app.models.schemas import Arbitration, Architecture, Requirements


class _StubClient:
    def __init__(self, payload): self._p = payload
    def chat_json(self, system, user): return self._p


_BASE = {
    "layerstack": "4-layer", "layerstack_reason": "r",
    "netclasses": [], "constraints": {"min_clearance_mm": 0.2, "min_track_width_mm": 0.2,
        "via_drill_mm": 0.3, "via_annular_ring_mm": 0.1},
    "floorplan_text": "", "floorplan_ascii": "", "package_hints": [],
}


def test_prompt_requests_choices_and_zones():
    low = SYSTEM_PROMPT.lower()
    assert "component_choices" in low and "floorplan_zones" in low


def test_parses_component_choices_and_zones():
    payload = dict(_BASE,
        component_choices=[{
            "component_type": "MCU", "category": "mcu",
            "candidates": [
                {"part": "STM32G0", "package": "LQFP-48", "score": 4.5, "recommended": True,
                 "pros": ["enough UARTs"], "cons": ["no radio"]},
                {"part": "ESP32", "package": "module", "score": 4.0, "pros": ["WiFi"], "cons": ["bigger"]},
            ]}],
        floorplan_zones=[{"label": "Power", "category": "power", "blocks": ["Power"],
                          "placement": "edge", "separation": ["Sensor"]}],
    )
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(payload), Requirements(), Architecture(), arb)
    assert pcb.component_choices[0].component_type == "MCU"
    assert pcb.component_choices[0].candidates[0].recommended is True
    assert pcb.component_choices[0].candidates[0].score == 4.5
    assert pcb.floorplan_zones[0].placement == "edge"
    assert pcb.floorplan_zones[0].separation == ["Sensor"]


def test_missing_new_fields_default_empty():
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(dict(_BASE)), Requirements(), Architecture(), arb)
    assert pcb.component_choices == [] and pcb.floorplan_zones == []
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3a: Add imports** to `pcb_engineer.py`:

```python
from app.models.schemas import (
    Arbitration, Architecture, Candidate, ComponentChoice, ConstraintSet,
    FloorplanZone, NetClass, PackageHint, PcbReadiness, Requirements,
)
```

- [ ] **Step 3b: Append to SYSTEM_PROMPT** (extend the JSON-keys list + a guidance paragraph):

```
- "component_choices": array of objects for DECISION-WORTHY components only (MCU,
  sensors, comms/bridge chips, central connectors/converters). Skip no-brainers
  (passives, standard LEDs). Each: {"component_type": str, "category": one of the
  block categories, "candidates": array of {"part": str, "package": str,
  "score": number 0-5 one decimal, "recommended": bool (exactly one true),
  "pros": array of str, "cons": array of str}}. Emit 1 recommended + up to 2
  alternatives. Weigh TYPE-SPECIFIC criteria and name them in pros/cons (MCU:
  interface/peripheral fit, integrated radios, compute/memory, then size/price/
  availability; sensor: measurands/accuracy; power: efficiency/thermal). Package
  must be correct for the part (a WROOM module is a castellated PCB module, not a QFN).
- "floorplan_zones": array of {"label": str, "category": one of the block
  categories, "blocks": array of block names, "placement": one of "edge"|"center"|
  "corner"|"top"|"bottom"|"left"|"right", "separation": array of zone labels/
  categories to keep apart}. Keep sensitive sensors away from power/heat; give
  airflow sensors a board edge; thermally isolate temperature/CO2 sensors.
```

- [ ] **Step 3c: Extend `run()` return**:

```python
        return PcbReadiness(
            layerstack=data["layerstack"],
            layerstack_reason=data["layerstack_reason"],
            netclasses=[NetClass(**nc) for nc in data.get("netclasses", [])],
            constraints=ConstraintSet(**data["constraints"]),
            floorplan_text=data.get("floorplan_text", ""),
            floorplan_ascii=data.get("floorplan_ascii", ""),
            package_hints=[PackageHint(**ph) for ph in data.get("package_hints", [])],
            component_choices=[
                ComponentChoice(
                    component_type=cc.get("component_type", ""),
                    category=cc.get("category", "other"),
                    candidates=[Candidate(**c) for c in cc.get("candidates", [])],
                )
                for cc in data.get("component_choices", [])
            ],
            floorplan_zones=[FloorplanZone(**fz) for fz in data.get("floorplan_zones", [])],
        )
```

- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(pcb-engineer): emit component candidates + floorplan zones"`

---

## Task 5: Mock fixtures

**Files:**
- Modify: `app/services/mock.py` (`_mock_pcb`, mock architecture blocks)
- Test: `tests/test_mock_smart.py` (new)

- [ ] **Step 1: Write failing test**

```python
# tests/test_mock_smart.py
from app.services.mock import mock_run, mock_run_rework


def test_mock_blocks_have_categories():
    arch = mock_run("x").architecture
    cats = {b.name: b.category for b in arch.blocks}
    assert cats["Power"] == "power"
    assert cats["MCU"] == "mcu"
    assert all(b.category != "" for b in arch.blocks)


def test_mock_pcb_has_choices_and_zones():
    pcb = mock_run("x").pcb_readiness
    assert len(pcb.component_choices) >= 2
    # exactly one recommended per choice
    for ch in pcb.component_choices:
        assert sum(1 for c in ch.candidates if c.recommended) == 1
    assert len(pcb.floorplan_zones) >= 2
    assert any(z.separation for z in pcb.floorplan_zones)


def test_mock_rework_keeps_smart_fields():
    pcb = mock_run_rework("x").pcb_readiness
    assert pcb is not None and pcb.component_choices  # rework builds on mock_run
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3a: Add categories** to the six mock blocks (`mock.py` ~166-173):
  Power→`power`, MCU→`mcu`, USB Service→`connectivity`, RS485→`connectivity`,
  Sensor IO→`sensor`, Debug→`debug`. (Add `category="..."` to each `Block(...)`.)

- [ ] **Step 3b: Extend `_mock_pcb()`** return with two fields (import `Candidate, ComponentChoice, FloorplanZone` at top of mock.py):

```python
        component_choices=[
            ComponentChoice(component_type="MCU", category="mcu", candidates=[
                Candidate(part="STM32G0B1", package="LQFP-48", score=4.5, recommended=True,
                          pros=["Enough UART/I²C for RS485+sensors", "Mainstream, well-stocked"],
                          cons=["No integrated radio"]),
                Candidate(part="ESP32-C3", package="QFN-32", score=3.8,
                          pros=["Integrated WiFi/BLE"],
                          cons=["Radio unused here", "Tighter peripheral count"]),
            ]),
            ComponentChoice(component_type="RS485 transceiver", category="connectivity", candidates=[
                Candidate(part="Isolated MAX14937", package="SOIC-16W", score=4.6, recommended=True,
                          pros=["Galvanic isolation for noisy fieldbus"],
                          cons=["Higher BOM cost"]),
                Candidate(part="THVD1450", package="SOIC-8", score=4.0,
                          pros=["Cheaper, smaller"], cons=["Non-isolated"]),
            ]),
        ],
        floorplan_zones=[
            FloorplanZone(label="Power Entry", category="power", blocks=["Power"],
                          placement="left", separation=["Sensor Front-End"]),
            FloorplanZone(label="MCU Core", category="mcu", blocks=["MCU"], placement="center"),
            FloorplanZone(label="Fieldbus", category="connectivity", blocks=["RS485", "USB Service"],
                          placement="right"),
            FloorplanZone(label="Sensor Front-End", category="sensor", blocks=["Sensor IO"],
                          placement="top", separation=["Power Entry"]),
        ],
```

- [ ] **Step 3c:** Confirm `mock_run_rework` reuses `mock_run` for pcb (it calls `mock_run(...)` per spec ~259). If it rebuilds the architecture inline, add the same categories there too. (Read ~254-end first.)

- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(mock): categories, component candidates, floorplan zones fixtures"`

---

## Task 6: Report rendering — candidate context, clustered diagram, zone floorplan, label-fit

**Files:**
- Modify: `app/generators/report.py` (`_report_context`, `_architecture_svg`, `_floorplan_svg`, `generate_report_pdf`, new `_wrap_label`, `_candidate_cards`)
- Modify: `app/templates/report.html.j2` (candidate cards + legend, replace package-hints table)
- Test: `tests/test_report.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report.py — append
from app.generators.report import (
    _architecture_svg, _floorplan_svg, _wrap_label, _report_context,
)


def test_wrap_label_breaks_long_text():
    lines = _wrap_label("Sensor Front-End Conditioning Block", 14)
    assert len(lines) >= 2 and all(len(ln) <= 14 for ln in lines)
    assert _wrap_label("MCU", 14) == ["MCU"]


def test_architecture_svg_colours_by_category_no_diagonals():
    svg = _architecture_svg(mock_run("x"))
    # MCU category fill present:
    assert "#E6F1FB" in svg
    # power category fill present:
    assert "#FEF3C7" in svg
    # edges are orthogonal polylines, not diagonal <line> centre-to-centre:
    assert "<polyline" in svg


def test_floorplan_renders_zones_with_separation():
    svg = _floorplan_svg(mock_run("x"))
    # one labelled zone present:
    assert "Power Entry" in svg or "MCU Core" in svg
    # a dashed keep-out line is drawn for the separation pair:
    assert "stroke-dasharray" in svg


def test_floorplan_falls_back_without_zones():
    r = mock_run("x"); r.pcb_readiness.floorplan_zones = []
    svg = _floorplan_svg(r)
    assert svg.startswith("<svg")  # category-cluster fallback, no crash


def test_report_context_exposes_candidate_cards_and_legend():
    ctx = _report_context(mock_run("x"), "A board", "project")
    cards = ctx["component_choices"]
    assert cards and cards[0]["component_type"]
    rec = [c for c in cards[0]["candidates"] if c["recommended"]]
    assert len(rec) == 1 and 0 <= rec[0]["score"] <= 5
    assert rec[0]["stars"].count("★") >= 1     # score -> stars string
    assert ctx["legend"]                        # legend entries present
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3a: `_wrap_label`** (shared label-fit helper):

```python
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
            out.append(ln[:max_chars]); ln = ln[max_chars:]
        out.append(ln)
    return out
```

- [ ] **Step 3b: Rewrite `_architecture_svg`** to cluster by category, colour boxes, and draw orthogonal polyline edges. Approach:
  - Sort blocks by `_CATEGORY_ORDER` index (groups same-category together), MCU first so it lands centre-left.
  - Grid layout (reuse `_COLS`, `_BOX_W`, etc.); record centres by name.
  - Edges: for each connection with both ends known, emit an **orthogonal polyline** `(x1,y1)->(x1,ymid)->(x2,ymid)->(x2,y2)` where `ymid=(y1+y2)/2`; dashed when `type=="power"`. (No diagonal `<line>`.)
  - Boxes: fill/stroke/text from `_category_style(block.category)`; render label via `_wrap_label` as stacked `<tspan>` lines centred in the box.
  - Keep the `<defs>` arrow marker; apply `marker-end` to polylines.

- [ ] **Step 3c: Rewrite `_floorplan_svg`** to render `floorplan_zones` when present:
  - Map coarse `placement` keywords to grid cells on a 3×3 board (`left/right/top/bottom/center/corner/edge`), packing collisions to free cells.
  - One rounded rect per zone using `_category_style(zone.category)`; label via `_wrap_label`.
  - For each zone with `separation`, draw a dashed keep-out line between that zone's rect and each named target zone's rect (`stroke-dasharray="4,3"`, category-neutral `#fca5a5`), with a small side-label "keep-out".
  - **Fallback** when `floorplan_zones` empty: cluster the architecture blocks by category on the grid (same colours) — no blind 1:1 copy.

- [ ] **Step 3d: `_candidate_cards(result)`** + extend `_report_context`:

```python
def _stars(score: float) -> str:
    full = int(round(score))
    full = max(0, min(5, full))
    return "★" * full + "☆" * (5 - full)


def _candidate_cards(result: RunResponse) -> list[dict]:
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
```

  In `_report_context` return dict add: `"component_choices": _candidate_cards(result),` and `"legend": _legend_entries(result),`. (Keep `package_hints` in the context — it still feeds the ZIP doc, but the template stops using it.)

- [ ] **Step 3e: `generate_report_pdf`** — accept the client SVG and prefer it:

```python
def generate_report_pdf(
    result: RunResponse, requirements_text: str, project_name: str,
    architecture_svg: str | None = None,
) -> bytes:
    from weasyprint import HTML
    context = _report_context(result, requirements_text, project_name)
    context["architecture_svg"] = architecture_svg or _architecture_svg(result)
    context["floorplan_svg"] = _floorplan_svg(result)
    html = _jinja_env.get_template("report.html.j2").render(**context)
    return HTML(string=html).write_pdf()
```

- [ ] **Step 3f: Template** (`report.html.j2`) — add a legend row under the architecture diagram, and replace the **Package Hints** section (lines ~99-107) with candidate cards (WeasyPrint-safe: tables/blocks, no flex gap reliance):

```html
  <div class="section"><div class="bar"></div><div class="t">System Architecture</div></div>
  <div class="diagram">{{ architecture_svg|safe }}</div>
  {% if legend %}
  <div class="legend">
    {% for e in legend %}<span class="lg"><span class="sw" style="background:{{ e.fill }};
      border-color:{{ e.stroke }}"></span>{{ e.label }}</span>{% endfor %}
  </div>
  {% endif %}
  ...
  <div class="section"><div class="bar"></div><div class="t">Component Candidates</div></div>
  {% if component_choices %}
    {% for ch in component_choices %}
    <div class="cc">
      <div class="cc-h">{{ ch.component_type }}</div>
      {% for c in ch.candidates %}
      <div class="cand {% if c.recommended %}rec{% endif %}">
        <div class="cand-top"><b>{{ c.part }}</b> · {{ c.package }}
          <span class="stars">{{ c.stars }}</span>
          {% if c.recommended %}<span class="badge">Empfehlung</span>{% endif %}</div>
        {% if c.pros %}<div class="pro">+ {{ c.pros|join("; ") }}</div>{% endif %}
        {% if c.cons %}<div class="con">– {{ c.cons|join("; ") }}</div>{% endif %}
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  {% else %}
    <table><thead><tr><th>Component</th><th>Recommended Package</th></tr></thead>
      <tbody>{% for ph in package_hints %}<tr><td>{{ ph.component_type }}</td>
        <td>{{ ph.recommended_package }}</td></tr>{% endfor %}</tbody></table>
  {% endif %}
```

  Add CSS (in the `<style>` block): `.legend{margin:4px 0 0;font-size:8px;color:#475569}`
  `.legend .lg{margin-right:10px}` `.legend .sw{display:inline-block;width:8px;height:8px;`
  `border:1px solid;border-radius:2px;margin-right:3px;vertical-align:middle}`
  `.cc{border:1px solid #e2e8f0;border-radius:5px;margin-bottom:6px;padding:5px 7px}`
  `.cc-h{font-size:9px;font-weight:700;color:#0f766e;margin-bottom:3px}`
  `.cand{padding:3px 0;border-top:1px solid #f1f5f9}` `.cand.rec{background:#f0fdfa}`
  `.cand-top{font-size:8.5px}` `.stars{color:#d97706;margin-left:4px}`
  `.badge{background:#0d9488;color:#fff;border-radius:3px;padding:0 4px;font-size:7px;margin-left:4px}`
  `.pro{font-size:8px;color:#15803d}` `.con{font-size:8px;color:#b91c1c}`

- [ ] **Step 4: Run `tests/test_report.py`, expect pass.** Also run full suite.
- [ ] **Step 5: Commit** — `git commit -am "feat(report): category diagram, candidate cards, zone floorplan, legend"`

---

## Task 7: routes.py accepts/validates client architecture_svg

**Files:**
- Modify: `app/api/routes.py` (`generate` handler ~102-104)
- Test: `tests/test_generate_svg.py` (new)

- [ ] **Step 1: Write failing test**

```python
# tests/test_generate_svg.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.config import Settings
from app.services.mock import mock_run

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    monkeypatch.setattr("app.api.routes.get_settings", lambda: Settings(qwen_api_key=""))


def _body(svg=None):
    return {"requirements_text": "24V board", "result": mock_run("x").model_dump(),
            "architecture_svg": svg}


def test_generate_accepts_valid_client_svg(monkeypatch):
    seen = {}
    import app.api.routes as r
    def fake_pdf(result, text, name, architecture_svg=None):
        seen["svg"] = architecture_svg; return b"%PDF-1.4 fake"
    monkeypatch.setattr(r, "generate_report_pdf", fake_pdf)
    ok_svg = "<svg viewBox='0 0 10 10'></svg>"
    resp = client.post("/api/generate", json=_body(ok_svg))
    assert resp.status_code == 200
    assert seen["svg"] == ok_svg


def test_generate_ignores_malformed_svg(monkeypatch):
    seen = {}
    import app.api.routes as r
    def fake_pdf(result, text, name, architecture_svg=None):
        seen["svg"] = architecture_svg; return b"%PDF-1.4 fake"
    monkeypatch.setattr(r, "generate_report_pdf", fake_pdf)
    resp = client.post("/api/generate", json=_body("<script>nope</script>"))
    assert resp.status_code == 200
    assert seen["svg"] is None       # malformed -> dropped, falls back server-side
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement validation + pass-through** in `generate`:

```python
# near top of routes.py
_MAX_CLIENT_SVG = 200_000

def _safe_client_svg(svg: str | None) -> str | None:
    if not svg or not isinstance(svg, str):
        return None
    s = svg.strip()
    if not s.startswith("<svg") or len(s) > _MAX_CLIENT_SVG:
        return None
    return s

# in generate(), replace the report block call:
        pdf_bytes = generate_report_pdf(
            req.result, req.requirements_text, _PROJECT_NAME,
            architecture_svg=_safe_client_svg(req.architecture_svg),
        )
```

- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(api): accept + validate client-rendered architecture SVG for the report"`

---

## Final verification

- [ ] Run full suite: `.venv/Scripts/python.exe -m pytest -q` → all green (the WeasyPrint render test stays skipped on Windows).
- [ ] Browser smoke (mock mode, port 8011): run a pipeline, confirm no console errors and the result view still renders (the report data is exercised by `/api/generate`; PDF stays unrenderable locally).
- [ ] Update `docs/.../2026-06-27-live-run-findings.md`: mark F5/F6 addressed by this feature (floorplan zones + candidate placement reasoning live in the data now); note Phase 2 (client ELK) still open.

---

## Self-review notes

- **Spec coverage:** candidates (T4/T5/T6), category block diagram + palette + legend (T2/T6), zone floorplan (T6), schema+defaults (T1), mock fixtures (T5), client-SVG contract (T1/T7), graceful fallbacks (T6 floorplan/diagram fallbacks, T7 malformed-SVG drop). **Deferred (Phase 2, documented):** ELK client colours/clustering/legend + SVG export in `index.html`.
- **Type consistency:** `category` Literal identical in Block; `ComponentChoice.candidates: list[Candidate]`; `_category_style`/`_legend_entries`/`_wrap_label`/`_candidate_cards`/`_stars` names used consistently across T2/T6; `generate_report_pdf(..., architecture_svg=None)` matches the T7 call.
- **No placeholders:** every code step carries real code; SVG geometry steps (3b/3c) describe exact construction + are pinned by property tests (colours present, `<polyline>` not diagonal `<line>`, dashed keep-out, zone labels).
