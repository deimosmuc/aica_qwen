# PCB Specialists DFM/Test/Bring-up + Present Reviewers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The PCB specialists propose and review a Design-for-X checklist (testability / DFM / bring-up) that surfaces in the PDF report and the KiCad schematic top sheet, and the PCB Critic becomes a visible rail station + step-by-step stage.

**Architecture:** A new `DfxItem` list on `PcbReadiness` (Engineer-owned, `present`/`recommended`/`missing`); the PCB Critic flags gaps via its existing `missing_blocks`/`warnings` (drives the existing PCB rework loop). Report renders a grouped section; the schematic top sheet gets a compact text note. The PCB Critic is added as a 6th mission-control rail station and a `pcb_critic` step. Backend is TDD (pytest); frontend is browser-verified (Claude Preview MCP).

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, Jinja2, WeasyPrint (lazy), Alpine.js, pytest.

---

## Context the engineer needs

- **Pipeline order:** requirements → architecture → Design Critic → arbitration → PCB Engineer → PCB Critic (the PCB Critic + its rework loop run only in **auto-run** via the orchestrator; step mode currently stops at PCB Engineer — Phase 2 adds the PCB Critic step).
- **PCB Engineer** (`app/agents/pcb_engineer.py`) returns `PcbReadiness`; **PCB Critic** (`app/agents/pcb_critic.py`) returns `PcbCritique {missing_blocks, warnings, risks}`.
- **Agent test pattern:** stub client with `chat_json(system, user)` returning a dict (see `tests/test_pcb_engineer_choices.py`).
- **Run command:** `python -m pytest -q` (baseline today: 195 passed, 1 skipped).
- **Frontend** is `app/static/index.html` (Alpine). The mission-control rail (`railView()`, Run A) and the step flow (`STAGES`, `loadStage`, `approveStep`) already exist. Browser verification via `Alpine.$data(document.querySelector('[x-data]'))` and the running mock server (port 8012 may already be up; else `preview_start`).
- **English-only** output everywhere.

---

## File Structure

- `app/models/schemas.py` — `DfxItem`; `PcbReadiness.dfx_checklist`; `Stage += "pcb_critic"`; `StepRequest.pcb_readiness`; `StepResponse.pcb_critique`.
- `app/agents/pcb_engineer.py` — prompt key + parse `dfx_checklist`.
- `app/agents/pcb_critic.py` — prompt DFX review dimension.
- `app/services/mock.py` — `dfx_checklist` fixture, scripted DFX rework, step slice.
- `app/services/stepwise.py` — `pcb_critic` stage.
- `app/generators/report.py` + `app/templates/report.html.j2` — DFX section.
- `app/generators/kicad.py` + `app/templates/root.kicad_sch.j2` — DFX top-sheet note.
- `app/static/index.html` — 6th rail station + PCB rework packets; step-mode `pcb_critic` stage + pending render.
- `tests/` — `test_pcb_schemas.py`, `test_pcb_engineer_choices.py`, `test_pcb_critic.py`, `test_report.py`, `test_kicad_generator.py`, `test_stepwise_pcb.py`.

---

# PHASE 1 — Content

## Task 1: Schema

**Files:**
- Modify: `app/models/schemas.py` (after `PackageHint`/`Candidate` ~138; `PcbReadiness` ~169-178; `Stage` line 328; `StepRequest` ~331-343; `StepResponse` ~346-356)
- Test: `tests/test_pcb_schemas.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_pcb_schemas.py`:

```python
def test_dfx_item_defaults():
    from app.models.schemas import DfxItem
    d = DfxItem(category="testability", item="SWD test points")
    assert d.status == "recommended" and d.note == ""
    d2 = DfxItem(category="dfm", item="3 fiducials", status="present", note="corners")
    assert d2.status == "present" and d2.note == "corners"


def test_pcb_readiness_dfx_defaults_empty():
    from app.models.schemas import PcbReadiness, ConstraintSet
    pcb = PcbReadiness(
        layerstack="2-layer", layerstack_reason="r", netclasses=[],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                  via_drill_mm=0.3, via_annular_ring_mm=0.1),
        floorplan_text="", floorplan_ascii="", package_hints=[],
    )
    assert pcb.dfx_checklist == []


def test_step_request_response_pcb_critic_fields():
    from app.models.schemas import StepRequest, StepResponse, TraceStep
    req = StepRequest(stage="pcb_critic", requirements_text="x")
    assert req.pcb_readiness is None  # optional input for the pcb_critic stage
    resp = StepResponse(stage="pcb_critic", mode="mock",
                        trace_step=TraceStep(agent="PCB Critic", role="Senior PCB Reviewer", summary="s"))
    assert resp.pcb_critique is None
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_pcb_schemas.py -q` → ImportError / ValidationError (pcb_critic not a valid Stage).

- [ ] **Step 3: Implement.** Add `DfxItem` after `Candidate` (before `ComponentChoice`, ~line 149):

```python
class DfxItem(BaseModel):
    """One Design-for-X provision: a testability / DFM / bring-up item."""

    category: Literal["testability", "dfm", "bringup"]
    item: str
    status: Literal["present", "recommended", "missing"] = "recommended"
    note: str = ""
```

In `PcbReadiness`, add at the end of the field list (after `floorplan_zones`):

```python
    dfx_checklist: list[DfxItem] = []
```

Change `Stage` (line 328) to include `pcb_critic`:

```python
Stage = Literal["requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critic"]
```

In `StepRequest`, add after `arbitration`:

```python
    pcb_readiness: PcbReadiness | None = None
```

In `StepResponse`, add after `pcb_readiness`:

```python
    pcb_critique: PcbCritique | None = None
```

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_pcb_schemas.py -q`.

- [ ] **Step 5: Commit** — `git add app/models/schemas.py tests/test_pcb_schemas.py && git commit -m "feat(schema): DfxItem + dfx_checklist; pcb_critic stage + step fields"`

---

## Task 2: PCB Engineer emits dfx_checklist

**Files:**
- Modify: `app/agents/pcb_engineer.py` (imports line 11-14; SYSTEM_PROMPT keys list ~60-70; `run()` return ~116-133)
- Test: `tests/test_pcb_engineer_choices.py`

- [ ] **Step 1: Write failing test** — append:

```python
def test_parses_dfx_checklist():
    payload = dict(_BASE, dfx_checklist=[
        {"category": "testability", "item": "SWD test points", "status": "recommended"},
        {"category": "dfm", "item": "3 fiducials", "status": "present", "note": "corners"},
        {"category": "bringup", "item": "PWR + STATUS LED", "status": "present"},
    ])
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(payload), Requirements(), Architecture(), arb)
    cats = [d.category for d in pcb.dfx_checklist]
    assert cats == ["testability", "dfm", "bringup"]
    assert pcb.dfx_checklist[0].status == "recommended"


def test_prompt_requests_dfx():
    low = SYSTEM_PROMPT.lower()
    assert "dfx_checklist" in low and "fiducial" in low and "test point" in low


def test_missing_dfx_defaults_empty():
    arb = Arbitration(approved_architecture=Architecture())
    pcb = PcbEngineerAgent().run(_StubClient(dict(_BASE)), Requirements(), Architecture(), arb)
    assert pcb.dfx_checklist == []
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_pcb_engineer_choices.py -q`.

- [ ] **Step 3a: Import `DfxItem`** — extend the import in `pcb_engineer.py`:

```python
from app.models.schemas import (
    Arbitration, Architecture, Candidate, ComponentChoice, ConstraintSet,
    DfxItem, FloorplanZone, NetClass, PackageHint, PcbReadiness, Requirements,
)
```

- [ ] **Step 3b: Append to SYSTEM_PROMPT** — add to the JSON-keys list (after the `floorplan_zones` key description):

```
- "dfx_checklist": array of Design-for-X provisions for fab + bring-up. Each:
  {"category": "testability" | "dfm" | "bringup", "item": short string,
   "status": "present" | "recommended" | "missing", "note": optional short string}.
  Cover: testability (test points on power rails + critical nets, SWD/JTAG debug access),
  dfm (fiducials, pin-1/polarity silkscreen, min feature sizes vs fab class, courtyard
  spacing), bringup (power/status LEDs, power-rail test points, power-up sequencing checks).
  Use "present" when the provision already follows from the architecture, "recommended"
  when it should be added, "missing" only when a recommended provision cannot be addressed.
```

- [ ] **Step 3c: Parse in `run()`** — add to the `PcbReadiness(...)` return (after `floorplan_zones=...`):

```python
            dfx_checklist=[DfxItem(**d) for d in data.get("dfx_checklist", [])],
```

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_pcb_engineer_choices.py -q`.

- [ ] **Step 5: Commit** — `git add app/agents/pcb_engineer.py tests/test_pcb_engineer_choices.py && git commit -m "feat(pcb-engineer): emit Design-for-X checklist"`

---

## Task 3: PCB Critic reviews DFX

**Files:**
- Modify: `app/agents/pcb_critic.py` (SYSTEM_PROMPT review list ~21-28)
- Test: `tests/test_pcb_critic.py`

- [ ] **Step 1: Write failing test** — append to `tests/test_pcb_critic.py`:

```python
def test_pcb_critic_prompt_covers_dfx():
    from app.agents.pcb_critic import SYSTEM_PROMPT
    low = SYSTEM_PROMPT.lower()
    assert "test point" in low and "fiducial" in low and "dfx_checklist" in low


def test_pcb_critic_flags_dfx_gap_in_missing_blocks():
    from app.agents.pcb_critic import PcbCriticAgent
    from app.models.schemas import PcbReadiness, ConstraintSet, Requirements

    class _Stub:
        def __init__(self, p): self._p = p
        def chat_json(self, s, u): return self._p

    pcb = PcbReadiness(layerstack="2-layer", layerstack_reason="r", netclasses=[],
                       constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                                 via_drill_mm=0.3, via_annular_ring_mm=0.1),
                       floorplan_text="", floorplan_ascii="", package_hints=[])
    payload = {"missing_blocks": ["No SWD test points on the debug net — add them for bring-up."],
               "warnings": [], "risks": []}
    crit = PcbCriticAgent().run(_Stub(payload), Requirements(), pcb)
    assert any("test point" in m.lower() for m in crit.missing_blocks)
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_pcb_critic.py -q` (the prompt assertion fails).

- [ ] **Step 3: Edit SYSTEM_PROMPT** — add to the "Review for:" bullet list in `pcb_critic.py`:

```
- Design-for-X: review the dfx_checklist — missing test points on power rails / critical
  nets, no SWD/JTAG debug access, no fiducials, no power/status indication, missing pin-1 /
  polarity silkscreen. Put must-fix DFX gaps in missing_blocks, nice-to-have ones in warnings.
```

(No code change to `run()` — `missing_blocks`/`warnings` already carry it and feed the rework loop.)

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_pcb_critic.py -q`.

- [ ] **Step 5: Commit** — `git add app/agents/pcb_critic.py tests/test_pcb_critic.py && git commit -m "feat(pcb-critic): review the Design-for-X checklist for gaps"`

---

## Task 4: Mock fixtures

**Files:**
- Modify: `app/services/mock.py` (`_mock_pcb()` ~31-159; `mock_run_rework()` ~302-end — read first)
- Test: `tests/test_mock_smart.py`

- [ ] **Step 1: Write failing test** — append to `tests/test_mock_smart.py`:

```python
def test_mock_pcb_has_dfx_checklist():
    pcb = mock_run("x").pcb_readiness
    cats = {d.category for d in pcb.dfx_checklist}
    assert {"testability", "dfm", "bringup"} <= cats
    assert any(d.status == "present" for d in pcb.dfx_checklist)
    assert any(d.status == "recommended" for d in pcb.dfx_checklist)


def test_mock_rework_pcb_critic_flags_dfx():
    r = mock_run_rework("x")
    # the PCB Critic round-1 trace step warns; a DFX gap is among its findings
    pcb_warn = [t for t in r.trace if t.agent == "PCB Critic" and t.status == "warning"]
    assert pcb_warn, "expected a warning PCB Critic step in the rework mock"
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_mock_smart.py -q`.

- [ ] **Step 3a: Add the import** at the top of `mock.py` (extend the existing schema import):

```python
from app.models.schemas import DfxItem
```

(Add `DfxItem` to whichever schema import block is already present; if a single combined import, append it alphabetically.)

- [ ] **Step 3b: Add `dfx_checklist` to `_mock_pcb()`** — inside the `PcbReadiness(...)` return, after `floorplan_zones=[...]`:

```python
        dfx_checklist=[
            DfxItem(category="bringup", item="PWR + STATUS LEDs", status="present",
                    note="Power-good and heartbeat indication for bring-up."),
            DfxItem(category="testability", item="SWD/JTAG debug header", status="present"),
            DfxItem(category="testability", item="Test points on +3V3, +5V, VIN_24V, GND",
                    status="recommended", note="Probe access for power-up checks."),
            DfxItem(category="dfm", item="3 fiducials (board corners)", status="recommended"),
            DfxItem(category="dfm", item="Pin-1 / polarity silkscreen on all ICs and connectors",
                    status="recommended"),
            DfxItem(category="bringup", item="Series-resistor option on first power rail",
                    status="recommended", note="Current-limit for first power-on."),
        ],
```

- [ ] **Step 3c: Make the rework mock flag a DFX gap.** Read `mock_run_rework()` (~302-end) first. It scripts a PCB Critic that warns in round 1 (`missing_blocks` non-empty) and is clean in round 2. Ensure the round-1 PCB Critic `missing_blocks` includes a DFX gap and the trace step has `status="warning"`. If the existing round-1 PCB critique already warns, append a DFX gap to its `missing_blocks`, e.g.:

```python
            "No SWD test points on the debug net — add them for bring-up.",
```

If `mock_run_rework` builds its PCB readiness via `_mock_pcb()`, the `dfx_checklist` is already present; only ensure the round-1 PCB Critic warning exists (the test asserts a warning PCB Critic trace step).

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_mock_smart.py -q`.

- [ ] **Step 5: Commit** — `git add app/services/mock.py tests/test_mock_smart.py && git commit -m "feat(mock): Design-for-X checklist fixture + DFX-driven PCB rework"`

---

## Task 5: Report DFX section

**Files:**
- Modify: `app/generators/report.py` (`_report_context` ~175-247)
- Modify: `app/templates/report.html.j2` (after the net-class / candidate sections)
- Test: `tests/test_report.py`

- [ ] **Step 1: Write failing test** — append to `tests/test_report.py`:

```python
def test_report_context_groups_dfx():
    ctx = _report_context(mock_run("x"), "A board", "project")
    groups = ctx["dfx_groups"]
    keys = [g["key"] for g in groups]
    assert keys == ["testability", "dfm", "bringup"]   # fixed display order
    # every item carries a status marker
    for g in groups:
        for it in g["items"]:
            assert it["marker"] in ("✓", "➜", "⚠")


def test_report_template_renders_dfx_section():
    from app.generators.report import _jinja_env
    ctx = _report_context(mock_run("x"), "A 24V board", "project")
    ctx["architecture_svg"] = "<svg/>"; ctx["floorplan_svg"] = "<svg/>"
    html = _jinja_env.get_template("report.html.j2").render(**ctx)
    assert "Design for Test" in html
    assert "Fiducials" in html or "fiducials" in html
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_report.py -q`.

- [ ] **Step 3a: Add the grouping helper + context** in `report.py`. Add this helper near the other private helpers:

```python
_DFX_ORDER = ["testability", "dfm", "bringup"]
_DFX_LABELS = {"testability": "Design for Test", "dfm": "Design for Manufacturing",
               "bringup": "Bring-up"}
_DFX_MARKERS = {"present": "✓", "recommended": "➜", "missing": "⚠"}


def _dfx_groups(result: RunResponse) -> list[dict]:
    pcb = result.pcb_readiness
    if pcb is None or not pcb.dfx_checklist:
        return []
    groups = []
    for key in _DFX_ORDER:
        items = [
            {"item": d.item, "status": d.status, "marker": _DFX_MARKERS.get(d.status, "➜"),
             "note": d.note}
            for d in pcb.dfx_checklist if d.category == key
        ]
        if items:
            groups.append({"key": key, "label": _DFX_LABELS[key], "items": items})
    return groups
```

In `_report_context`, add to the returned dict:

```python
        "dfx_groups": _dfx_groups(result),
```

- [ ] **Step 3b: Template section** — in `report.html.j2`, after the Component Candidates / Net Class section (before the disclaimer/footer), add:

```html
  {% if dfx_groups %}
  <div class="section"><div class="bar"></div><div class="t">Design for Test · Manufacturing · Bring-up</div></div>
  {% for g in dfx_groups %}
  <div class="dfx-grp">
    <div class="dfx-h">{{ g.label }}</div>
    <ul class="dfx-list">
      {% for it in g.items %}
      <li><span class="dfx-mark {{ it.status }}">{{ it.marker }}</span> {{ it.item }}
        {% if it.note %}<span class="dfx-note">— {{ it.note }}</span>{% endif %}</li>
      {% endfor %}
    </ul>
  </div>
  {% endfor %}
  {% endif %}
```

Add CSS to the report `<style>` block:

```css
  .dfx-grp { margin: 4px 0 8px; }
  .dfx-h { font-size: 9px; font-weight: 700; color: #0f766e; margin-bottom: 2px; }
  .dfx-list { margin: 0; padding-left: 4px; list-style: none; font-size: 8.5px; }
  .dfx-list li { padding: 1px 0; }
  .dfx-mark { font-weight: 700; margin-right: 4px; }
  .dfx-mark.present { color: #15803d; } .dfx-mark.recommended { color: #0f766e; }
  .dfx-mark.missing { color: #b91c1c; }
  .dfx-note { color: #64748b; }
```

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_report.py -q`.

- [ ] **Step 5: Commit** — `git add app/generators/report.py app/templates/report.html.j2 tests/test_report.py && git commit -m "feat(report): Design for Test/Manufacturing/Bring-up section"`

---

## Task 6: Schematic top-sheet DFX note

**Files:**
- Modify: `app/generators/kicad.py` (near the `impedance_note` block, ~326-342; render call ~355-358)
- Modify: `app/templates/root.kicad_sch.j2` (after the `impedance_note` block)
- Test: `tests/test_kicad_generator.py`

- [ ] **Step 1: Write failing test** — append to `tests/test_kicad_generator.py`:

```python
def test_schematic_has_dfx_note(tmp_path):
    from app.services.mock import mock_run
    from app.generators.kicad import generate_scaffold
    r = mock_run("usb can board")
    generate_scaffold(r, "usb can board", tmp_path, "TestBoard")
    sch = (tmp_path / "TestBoard.kicad_sch").read_text(encoding="utf-8")
    assert "DFT / DFM / BRING-UP" in sch
    # actionable items only (recommended/missing), ASCII-safe (no stray unicode markers)
    assert "fiducial" in sch.lower()
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_kicad_generator.py::test_schematic_has_dfx_note -q`.

- [ ] **Step 3a: Build the note in `kicad.py`** — after the `impedance_note` block, add:

```python
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
```

- [ ] **Step 3b: Pass it to the template render** — in the `root_sch = env.get_template(...).render(...)` call, add the kwarg:

```python
        impedance_note=impedance_note,
        dfx_note=dfx_note,
```

- [ ] **Step 3c: Template** — in `root.kicad_sch.j2`, after the `{% if impedance_note %}...{% endif %}` block, add a parallel block:

```jinja
{% endif %}{% if dfx_note %}	(text "{{ dfx_note.text }}"
		(at {{ dfx_note.x }} {{ dfx_note.y }} 0)
		(effects (font (size 1 1)) (justify left top))
		(uuid "{{ dfx_note.uuid }}")
	)
{% endif %}	(sheet_instances
```

(Replace the existing `{% endif %}\t(sheet_instances` opener so the new block chains correctly — verify the surrounding `{% if %}` chain after editing.)

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_kicad_generator.py -q` (all, to confirm paren-balance + determinism tests still pass).

- [ ] **Step 5: Commit** — `git add app/generators/kicad.py app/templates/root.kicad_sch.j2 tests/test_kicad_generator.py && git commit -m "feat(schematic): compact DFT/DFM/bring-up note on the top sheet"`

- [ ] **Step 6: Phase-1 full suite** — `python -m pytest -q` → all green. Commit nothing (verification only).

---

# PHASE 2 — Visibility

## Task 7: PCB Critic step (backend)

**Files:**
- Modify: `app/services/stepwise.py` (`_STAGE_ORDER` line 39; `_mock_step` ~42-50; add a `pcb_critic` branch ~152)
- Test: `tests/test_stepwise_pcb.py`

- [ ] **Step 1: Write failing test** — append to `tests/test_stepwise_pcb.py`:

```python
def test_step_pcb_critic_mock_returns_critique():
    from app.services.stepwise import run_stage
    from app.models.schemas import StepRequest
    from app.services.config import Settings
    resp = run_stage(StepRequest(stage="pcb_critic", requirements_text="x"),
                     Settings(qwen_api_key=""))
    assert resp.stage == "pcb_critic"
    assert resp.pcb_critique is not None
    assert resp.trace_step.agent == "PCB Critic"
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_stepwise_pcb.py::test_step_pcb_critic_mock_returns_critique -q`.

- [ ] **Step 3a: Add `pcb_critic` to `_STAGE_ORDER`** (line 39):

```python
_STAGE_ORDER = ["requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critic"]
```

- [ ] **Step 3b: Map the field in `_mock_step`** — the helper sets `field = "pcb_readiness" if stage == "pcb_engineer" else stage`. Replace with a mapping that also handles `pcb_critic`:

```python
    field = {"pcb_engineer": "pcb_readiness", "pcb_critic": "pcb_critique"}.get(stage, stage)
    setattr(resp, field, getattr(mock, field, None))
```

Note: `mock_run` has no top-level `pcb_critique`; for the `pcb_critic` mock slice, build it from the rework mock instead. Replace the `_mock_step` body's mock source for this stage:

```python
def _mock_step(stage: str, notice: str | None = None) -> StepResponse:
    mock = mock_run("")
    trace_step = mock.trace[_STAGE_ORDER.index(stage)] if _STAGE_ORDER.index(stage) < len(mock.trace) \
        else TraceStep(agent="PCB Critic", role="Senior PCB Reviewer", status="ok",
                       summary="Reviewed PCB readiness; no blocking issues.")
    resp = StepResponse(stage=stage, mode="mock", trace_step=trace_step, notice=notice)
    if stage == "pcb_critic":
        from app.models.schemas import PcbCritique
        resp.pcb_critique = PcbCritique(
            warnings=["Consider adding test points on the primary power rail."])
    else:
        field = "pcb_readiness" if stage == "pcb_engineer" else stage
        setattr(resp, field, getattr(mock, field))
    return resp
```

(Keep the `TraceStep` import at the top of `stepwise.py` — it is already imported.)

- [ ] **Step 3c: Add the live `pcb_critic` branch** in `run_stage` after the `pcb_engineer` branch:

```python
        if req.stage == "pcb_critic":
            if req.pcb_readiness is None:
                raise ValueError("The pcb_critic stage needs the approved pcb_readiness.")
            t = perf_counter()
            crit: PcbCritique = PcbCriticAgent().run(client, req.requirements, req.pcb_readiness, req.guidance)
            ms = int((perf_counter() - t) * 1000)
            n = len(crit.missing_blocks) + len(crit.warnings)
            step = _trace(PcbCriticAgent, "warning" if crit.missing_blocks else "ok",
                          f"Reviewed PCB readiness: {len(crit.missing_blocks)} must-fix, "
                          f"{len(crit.warnings)} warnings.", ms)
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, pcb_critique=crit)
```

(`PcbCriticAgent` and `PcbCritique` are already imported in `stepwise.py`.)

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_stepwise_pcb.py -q`.

- [ ] **Step 5: Commit** — `git add app/services/stepwise.py tests/test_stepwise_pcb.py && git commit -m "feat(stepwise): PCB Critic as a step-by-step stage"`

---

## Task 8: PCB Critic rail station + PCB rework packets (frontend)

**Files:**
- Modify: `app/static/index.html` (`railView()` STATIONS + packet logic; the `@keyframes rl-flow` rule; the packet markup in both rail copies; the `.rail-phase` left%)

- [ ] **Step 1: Add the PCB Critic station + generalised packet positions in `railView()`**

In the `STATIONS` array, add after the `pcb_engineer` entry:

```js
            { key: 'pcb_critic',   label: 'PCB Critic',   agent: 'PCB Critic',         color: '#ef4444' },
```

Replace the rework block in `railView()` with one that also handles the PCB rework and computes packet start/end percentages from station positions:

```js
          let addressed = null, packetFrom = null, packetTo = null;
          if (!pendingStage && last && !settled) {
            if ((last.agent === 'Design Critic' && last.status === 'warning') ||
                (last.agent === 'System Architect' && last.round > 1)) {
              addressed = 'System Architect'; packetFrom = 'critique'; packetTo = 'architecture';
            } else if ((last.agent === 'PCB Critic' && last.status === 'warning') ||
                       (last.agent === 'PCB Engineer' && last.round > 1)) {
              addressed = 'PCB Engineer'; packetFrom = 'pcb_critic'; packetTo = 'pcb_engineer';
            }
          }
          const N = STATIONS.length;
          const pct = key => {
            const i = STATIONS.findIndex(s => s.key === key);
            return N > 1 ? Math.round((6 + 88 * i / (N - 1)) * 10) / 10 : 50;  // track 6%..94%
          };
```

And extend the returned object with the packet percentages (only when a packet flow is active):

```js
          return { stations, fillPct: Math.max(0, fillPct), packetFrom, packetTo,
                   packetStart: packetFrom ? pct(packetFrom) : null,
                   packetEnd: packetTo ? pct(packetTo) : null,
                   active: this.isPlaying() || !!pendingStage };
```

- [ ] **Step 2: Make the flow keyframe use CSS variables**

Replace the `@keyframes rl-flow` rule (from Run A) with:

```css
    @keyframes rl-flow { 0%   { left: var(--s); opacity: 0; transform: scale(.6) }
                         12%  { opacity: 1; transform: scale(1) }
                         88%  { left: var(--e); opacity: 1; transform: scale(1) }
                         100% { left: var(--e); opacity: 0; transform: scale(.6) } }
```

- [ ] **Step 3: Update the packet markup in BOTH rail copies**

Replace each packet template (the `<template x-if="railView().packetFrom === 'critique'">` block) with a generalised one driven by the computed percentages:

```html
            <template x-if="railView().packetFrom">
              <div :style="`--s:${railView().packetStart}%; --e:${railView().packetEnd}%`">
                <div class="rail-pkt p1"></div><div class="rail-pkt p2"></div><div class="rail-pkt p3"></div>
              </div>
            </template>
```

- [ ] **Step 4: Fix the phase divider position for 6 stations**

The phase boundary sits between Arbitration (index 3) and PCB Eng. (index 4). For 6 stations the midpoint is ≈ `6 + 88*3.5/5 = 67.6%`. In BOTH rail copies, change `style="left:81.5%"` on `.rail-phase` to `style="left:67.6%"`.

- [ ] **Step 5: Verify in the browser**

Start/confirm the mock server. Run auto with the rework profile and confirm the PCB station + both rework flows:

```js
// preview_eval
(async () => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  d.selectedProfile = "Senior Review Team";
  d.input = "24V sensor board, STM32, USB-C, RS485, status LEDs."; d.auto = true;
  await d.runAuto();
  const seen = new Set();
  for (let i = 0; i < 60; i++) {
    const v = d.railView();
    if (v.packetFrom) seen.add(v.packetFrom + '->' + v.packetTo);
    const a = v.stations.find(s => s.addressed); if (a) seen.add('glow:' + a.key);
    await new Promise(r => setTimeout(r, 150));
    if (!d.isPlaying()) break;
  }
  return { stations: d.railView().stations.map(s => s.key), flows: [...seen] };
})()
```

Expected: `stations` includes `pcb_critic` (6 total); `flows` contains `critique->architecture`, `pcb_critic->pcb_engineer`, `glow:architecture`, `glow:pcb_engineer`. Check `preview_console_logs` (error) → none.

- [ ] **Step 6: Commit** — `git add app/static/index.html && git commit -m "feat(ui): PCB Critic rail station + PCB Critic->Engineer rework packets"`

---

## Task 9: PCB Critic step in the step-by-step flow (frontend)

**Files:**
- Modify: `app/static/index.html` (`STAGES`; `STAGE_META`; `loadStage` body; `approveStep` field map; acc init; pending render block)

- [ ] **Step 1: Add the stage + meta**

Change `STAGES`:

```js
        auto: false, STAGES: ["requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critic"],
```

Add to `STAGE_META` after `pcb_engineer`:

```js
          pcb_critic:   { agent: 'PCB Critic',       role: 'Senior PCB Reviewer' },
```

- [ ] **Step 2: Send `pcb_readiness` to the step endpoint**

In `loadStage`'s POST body, add `pcb_readiness`:

```js
                arbitration: this.acc.arbitration,
                pcb_readiness: this.acc.pcb_readiness,
                profile: this.selectedProfile
```

- [ ] **Step 3: Map the field on approve + acc init**

In `runStep`, the acc init already includes `pcb_readiness: null`; add `pcb_critique: null`:

```js
          this.acc = { mode: "mock", requirements: null, architecture: null,
            critique: null, arbitration: null, pcb_readiness: null, pcb_critique: null, trace: [], guidance: this.parseConstraints() };
```

In `approveStep`, the field map already handles `pcb_engineer -> pcb_readiness`; extend it:

```js
          const field = stage === "pcb_engineer" ? "pcb_readiness"
                      : stage === "pcb_critic" ? "pcb_critique" : stage;
          this.acc[field] = this.pending[field];
```

In the final-result object built at the end of `approveStep`, add `pcb_critique`:

```js
            pcb_readiness: this.acc.pcb_readiness,
            pcb_critique: this.acc.pcb_critique,
            trace: this.acc.trace, needs_approval: true, notice: null
```

- [ ] **Step 4: Pending render block for the PCB Critic**

In the stepwise pending `.out` area, after the `pending.pcb_readiness` block, add:

```html
                <template x-if="pending.pcb_critique">
                  <div>
                    <div class="out-grp" x-show="pending.pcb_critique.missing_blocks.length"><b>Must fix</b><ul><template x-for="x in pending.pcb_critique.missing_blocks" :key="x"><li x-text="x"></li></template></ul></div>
                    <div class="out-grp" x-show="pending.pcb_critique.warnings.length"><b>Warnings</b><ul><template x-for="x in pending.pcb_critique.warnings" :key="x"><li x-text="x"></li></template></ul></div>
                    <div class="out-grp" x-show="pending.pcb_critique.risks.length"><b>Risks</b><ul><template x-for="x in pending.pcb_critique.risks" :key="x"><li x-text="x"></li></template></ul></div>
                  </div>
                </template>
```

- [ ] **Step 5: Verify the step flow walks 6 stages**

```js
// preview_eval
(async () => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const settle = async () => { for (let i=0;i<40 && (d.stepBusy || (!d.pending && !d.result));i++) await sleep(60); };
  d._resetRun(); d.input = "24V sensor board"; d.auto = false; d.selectedProfile = "Uniform qwen-plus";
  await d.runStep(); await settle();
  const stages = [];
  while (!d.result) { stages.push(d.STAGES[d.stepIdx]); d.approveStep(); await settle(); }
  return { stages, hadPcbCritique: !!d.result.pcb_critique };
})()
```

Expected: `stages` = `["requirements","architecture","critique","arbitration","pcb_engineer","pcb_critic"]`; `hadPcbCritique` true. On the `pcb_critic` step the pending block shows the critique findings. Console errors → none.

- [ ] **Step 6: Final full suite + commit**

Run: `python -m pytest -q` → all green (frontend changes don't affect pytest count; expect the Phase-1 additions, e.g. ~205 passed).
`git add app/static/index.html && git commit -m "feat(ui): PCB Critic step in the step-by-step flow"`

---

## Self-Review

**Spec coverage:**
- DfxItem + dfx_checklist data model → Task 1. ✓
- PCB Engineer proposes checklist → Task 2. ✓
- PCB Critic reviews via missing_blocks/warnings → Task 3. ✓
- Mock fixture + DFX-driven rework → Task 4. ✓
- Report DFX section grouped by category w/ status markers → Task 5. ✓
- Schematic compact key-items note (actionable only, ASCII) → Task 6. ✓
- PCB Critic rail station + PCB rework packets → Task 8. ✓
- PCB Critic step-by-step stage + pending render → Tasks 7 (backend) + 9 (frontend). ✓
- English-only → all new strings English. ✓
- Graceful degradation (empty checklist → no section/note; step mock slice) → Tasks 5/6/7. ✓

**Placeholder scan:** every step has concrete code + commands + expected results. No TBD/TODO. The only "read first" is Task 4 Step 3c (`mock_run_rework` shape) with concrete fallback instructions. ✓

**Type/name consistency:** `DfxItem(category,item,status,note)`; `PcbReadiness.dfx_checklist`; `StepRequest.pcb_readiness`; `StepResponse.pcb_critique`; `Stage` includes `pcb_critic`; rail station key `pcb_critic` matches `STAGES`/`STAGE_META`/`_STAGE_ORDER`/`railView` packet logic; `_dfx_groups`/`dfx_groups`/`_DFX_ORDER`/`_DFX_MARKERS` consistent; report markers `✓/➜/⚠` match `_DFX_MARKERS`. ✓

**Nuance:** the schematic `dfx_note` y-position and the rail `.rail-phase` left% / packet percentages are visual approximations — verify in the browser/render and adjust during Tasks 6/8.
