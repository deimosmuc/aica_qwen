# Feature D — PCB-Readiness Pack: Design Spec

**Date:** 2026-06-27  
**Status:** Approved for implementation  
**Scope:** 5th agent stage (PCB Engineer + PCB Critic rework loop) with KiCad-9-native output files and a markdown report. Does NOT include the beautiful PDF report (→ Feature E).

---

## 1. Goal

After the 4-agent design pipeline completes, a new **PCB Engineer** agent analyses the approved architecture and produces a ready-to-use PCB preparation package. The output travels in the existing ZIP download and is visible in the Agent Society chat. The jury sees a complete, professional hand-off from AI-generated schematic to PCB layout — without the AI overstepping into actual routing.

---

## 2. Content scope

The PCB-Readiness Pack covers all five areas agreed during brainstorming:

| Area | Output |
|---|---|
| Layerstack recommendation | 2/4/6-layer choice with reasoning |
| Net classes & trace widths | Per-class min width + clearance, calculated from current requirements |
| Design rules / constraints | `.kicad_dru` file, KiCad 9 native, generated from structured data (no LLM writes raw syntax) |
| Floorplan recommendation | Text description + ASCII block sketch of component group placement |
| Package & manufacturing strategy | Per-component-type package recommendation (SMD size, IC package, connector pitch, manufacturing target) |

---

## 3. Architecture

### 3.1 New Pydantic schemas (`app/models/schemas.py`)

```python
class NetClass(BaseModel):
    name: str                   # e.g. "PWR", "Signal", "USB"
    min_width_mm: float
    clearance_mm: float
    nets: list[str]             # net names that belong here

class ConstraintSet(BaseModel):
    min_clearance_mm: float
    min_track_width_mm: float
    via_drill_mm: float
    via_annular_ring_mm: float

class PackageHint(BaseModel):
    component_type: str         # e.g. "Resistor", "MCU", "Power connector"
    recommended_package: str    # e.g. "0603", "QFN-32", "2.54mm screw terminal"
    reason: str

class PcbReadiness(BaseModel):
    layerstack: str             # "2-layer" | "4-layer" | "6-layer"
    layerstack_reason: str
    netclasses: list[NetClass]
    constraints: ConstraintSet
    floorplan_text: str         # prose description
    floorplan_ascii: str        # ASCII block sketch
    package_hints: list[PackageHint]
    # kicad_dru_content generated deterministically in Python, not by LLM
```

`RunResponse` gains `pcb_readiness: PcbReadiness | None = None`.

### 3.2 Two-call internal pattern

Within the single `pcb_engineer` stage, two Qwen calls run sequentially:

1. **`pcb_engineer` call** (qwen-plus): receives `Requirements` + `Architecture` + `Arbitration` TODOs → returns `PcbReadiness` JSON (all fields except `.kicad_dru`)
2. **`pcb_critic` call** (qwen-max): reviews `PcbReadiness` for engineering correctness (via sizes vs. current, clearances vs. voltage, missing netclasses, implausible layerstack) → returns `missing_blocks: list[str]`
3. **Rework loop** (max 2 rounds): if `missing_blocks` non-empty → pcb_engineer revises → pcb_critic re-reviews, same as existing `_design_and_review` loop
4. **`.kicad_dru` generation**: after final approval, Python template builds the file from `ConstraintSet` values — no LLM writes raw KiCad syntax

### 3.3 Orchestrator changes (`app/services/orchestrator.py`)

- Add `_pcb_engineer_step()` and `_pcb_critic_step()` helper methods (mirror of `_arch_step` / `_critic_step`)
- Add `_pcb_design_and_review()` method encapsulating the two-call + rework loop
- Call it at the end of `run()` after arbitration
- Both calls routed via `self._client_for("pcb_engineer")` and `self._client_for("pcb_critique")`
- `STAGES` list in `app/services/stepwise.py` gains `"pcb_engineer"` as 5th stage

### 3.4 KiCad DRU template (`app/generators/pcb_dru.py`)

New module. `generate_dru(constraints: ConstraintSet, netclasses: list[NetClass]) -> str` returns a valid KiCad 9 `.kicad_dru` file as a string. Pure Python, deterministic, tested against KiCad 9 schema.

### 3.5 ZIP integration (`app/generators/kicad.py`)

Two new files added to the ZIP:
- `pcb_constraints.kicad_dru` — from `generate_dru()`
- `PCB_READINESS.md` — markdown report built from `PcbReadiness` fields (layerstack table, netclass table, floorplan ASCII sketch, package hints table)

---

## 4. UI integration

### 4.1 Step-by-step flow

- `STAGES` array extended: `['requirements', 'architecture', 'critique', 'arbitration', 'pcb_engineer']`
- After Arbitration approve, a new stage card appears: **PCB Engineer** / role "PCB Layout Preparation"
- Uses existing `loadStage()` → `POST /api/step` — no new endpoint
- Approve button triggers `/api/step` with `stage: 'pcb_engineer'`

### 4.2 Auto-run

- PCB Engineer runs automatically as 5th stage in `orchestrator.run()`
- Result included in `RunResponse.pcb_readiness`
- No UI change needed beyond displaying new trace steps

### 4.3 Agent Society chat

- PCB Engineer and PCB Critic emit `TraceStep` entries with `round` labels — automatically appear in Society chat via existing `playSociety()`
- `avatarColor()` map in `index.html` gains entries for `"PCB Engineer"` (teal `#0d9488`) and keeps `"Design Critic"` for PCB Critic bubbles (same agent, same colour)
- A phase divider "PCB-Readiness Phase" appears between Arbitration and PCB Engineer bubbles (small HTML addition to the Society chat template)
- ZIP completion shown as final bubble with file list

---

## 5. Profile integration

| Profile | pcb_engineer | pcb_critique |
|---|---|---|
| Senior Review Team | qwen-plus | qwen-max |
| Uniform qwen-max | qwen-max | qwen-max |
| Budget Turbo | qwen-turbo | qwen-turbo |

---

## 6. Mock mode

- `mock_run()` returns a fixed `PcbReadiness` block (4-layer, 3 netclasses, plausible RS-485 constraints) with `PCB_READINESS.md` and `.kicad_dru` content included in the ZIP — fully keyless
- `mock_run_rework()` shows PCB rework: Round 1 via-drill too small (0.2mm), Critic flags it, Round 2 corrected (0.4mm) — demonstrates the rework loop in Mock Mode

---

## 7. Testing

| Test file | What it covers |
|---|---|
| `tests/test_pcb_engineer.py` | `PcbEngineerAgent.run()` with mock client, schema validation |
| `tests/test_pcb_critic.py` | Critic finds `missing_blocks`, clean pass case |
| `tests/test_pcb_dru.py` | `generate_dru()` output is valid KiCad 9 DRU syntax |
| `tests/test_orchestrator_pcb.py` | Full mock run: 5+ TraceSteps, ZIP contains new files |

All 110 existing tests remain green. Target: ~125 tests after D.

---

## 8. Out of scope (Feature E)

- Beautiful PDF report with logo, SVG block diagram, professional layout → Feature E (WeasyPrint-based, separate implementation cycle)
- User persona input (Professional/Student/Maker) → Polish phase

---

## 9. Open questions (none — all resolved)

| Question | Decision |
|---|---|
| Output format | Report (MD) + KiCad files |
| Content scope | All 5 areas + ASCII floorplan sketch |
| UI placement | Step-by-step 5th stage + auto-run |
| KiCad format | KiCad 9 native |
| Architecture | Two internal calls + Critic rework loop (max 2 rounds) |
| KiCad syntax generation | Python template (not LLM) |
| Beautiful PDF | Feature E, not D |
