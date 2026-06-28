# PCB Specialists: DFM / Testability / Bring-up + Present Reviewers (Design Spec)

**Date:** 2026-06-28
**Status:** Approved in brainstorming, pending written-spec review.
**Track:** Polish / Agent-Society depth. Builds directly on Run A (mission-control rail).

## Summary

Enrich the existing PCB specialist roles so they also cover **manufacturability (DFM)**,
**testability**, and **bring-up**, and surface those findings where an engineer expects
them. The PCB Engineer proposes a **Design-for-X checklist** (test points, SWD/JTAG
access, fiducials, status LEDs, …); the PCB Critic reviews it and flags gaps through the
existing rework loop. The checklist flows into the **PDF report** (a full section) and the
**KiCad schematic top sheet** (a compact text note). The **PCB Critic is made more
present**: a sixth station on the mission-control rail and a step in the step-by-step flow.

No new agent, no new graph engine, and **no real placed test-point/fiducial symbols**
(that is Schematic Stage 2 — `lib_symbols`/ERC — explicitly out of scope). The output
stays a scaffold a human completes. All user-facing text is English.

## Goals

- The PCB readiness output reads like a real EE prepared it for fab + bring-up: concrete
  DFM/test/bring-up provisions, not just net classes and a floorplan.
- Findings surface in the report **and** the schematic top sheet (where sensible).
- Reuse the Run A rework choreography: the PCB Critic flagging a DFX gap drives the
  PCB-rework loop, now visible on the rail.
- Degrades gracefully and stays deterministic in Mock Mode for the demo video.
- English-only output (project directive).

## Non-goals / out of scope

- Real placed schematic symbols for test points / fiducials (Schematic Stage 2).
- A separate DFM agent (concerns live in the existing PCB Engineer + PCB Critic).
- Persona selector (Run B), DRU impedance, light theme.

## Locked design decisions (from brainstorming)

- **Data model:** one structured **Design-for-X checklist** on `PcbReadiness` (chosen over
  rigid typed fields or loose category-tagged free text).
- **Producer/reviewer split:** the **PCB Engineer owns the checklist** (`present` /
  `recommended`); the **PCB Critic flags gaps via its existing `missing_blocks` /
  `warnings`**, which triggers the PCB rework loop → the Engineer fills the gaps in round
  2. A gap still open after rework is marked `missing` by the Engineer. (No new field on
  `PcbCritique`; no checklist-merge logic.)
- **Schematic surfacing:** a **compact key-items text note** on the top sheet (not the full
  list, not real symbols).
- **Reviewer presence:** the **PCB Critic becomes a 6th rail station** and a **step in the
  step-by-step flow**.

## Data model (`app/models/schemas.py`)

```python
class DfxItem(BaseModel):
    category: Literal["testability", "dfm", "bringup"]
    item: str
    status: Literal["present", "recommended", "missing"] = "recommended"
    note: str = ""

# PcbReadiness gains (defaulted, so old payloads still validate):
    dfx_checklist: list[DfxItem] = []
```

Category vocabulary:
- **testability** — test points on key nets (power rails, critical signals), SWD/JTAG
  debug-header access.
- **dfm** — fiducials, pin-1/polarity silkscreen, minimum feature sizes vs. the chosen
  fab class, courtyard/keepout spacing.
- **bringup** — power/status LEDs, power-rail test points & sequencing, first-power-on
  checks.

## Agents

### PCB Engineer (`app/agents/pcb_engineer.py`)
Prompt gains a `dfx_checklist` output key: for the proposed board, list the DFM /
testability / bring-up provisions. Mark `present` when the provision already follows from
the architecture (e.g. status LEDs that exist as a block), `recommended` when it should be
added, `missing` only when a recommended provision could not be addressed. Keep items
short and concrete. `run()` parses `data.get("dfx_checklist", [])` into `DfxItem`s.

### PCB Critic (`app/agents/pcb_critic.py`)
Prompt gains a review dimension: check the `dfx_checklist` for gaps — missing test points
on critical nets, no debug access, no fiducials, no power/status indication, polarity/pin-1
silkscreen. Gaps go into the **existing** `missing_blocks` (must-fix) / `warnings`
(worth-noting). No schema change to `PcbCritique`. These already feed the PCB rework loop
and the trace `status="warning"` that drives the rail choreography.

## Rendering

### Report (`app/generators/report.py`, `app/templates/report.html.j2`)
New section **"Design for Test · Manufacturing · Bring-up"**: the checklist grouped by the
three categories, each item with a status marker (✓ present / ➜ recommended / ⚠ missing)
and its note. The context builder flattens `dfx_checklist` into grouped, render-ready data;
the template renders three small grouped blocks (WeasyPrint-safe). Section omitted when the
checklist is empty.

### Schematic top sheet (`app/generators/kicad.py`, `app/templates/root.kicad_sch.j2`)
A compact `DFT / DFM / BRING-UP` text note beside the existing NOTES / CONTROLLED
IMPEDANCE notes. Include only `recommended` + `missing` items (the actionable ones),
truncated, deterministic UUID via `_det_uuid`, KiCad stroke-font safe (ASCII; no special
glyphs). Note omitted when there are no actionable items.

## Reviewer presence (builds on Run A)

### Rail (`app/static/index.html`)
Add **PCB Critic** as a 6th station (red, in the PCB phase, after PCB Eng.). With both PCB
Engineer and PCB Critic on the rail, generalise the rework choreography so the **PCB
Critic → PCB Engineer** rework also shows travelling amber packets (not just the glow). The
`railView()` helper's packet logic extends: `packetFrom='pcb_critic', packetTo='pcb_engineer'`
when the PCB rework beat is active.

### Step-by-step flow (`app/static/index.html`, `app/services/stepwise.py`)
Add `pcb_critic` to the frontend `STAGES` and `STAGE_META`, and to the backend
`_STAGE_ORDER`. `stepwise.run_stage` already imports `PcbCriticAgent`; add a `pcb_critic`
branch that takes the approved `pcb_readiness` and returns a `PcbCritique` (a new optional
`pcb_critique` field on `StepResponse`, mapped like the others). Add a `pending.pcb_critique`
render block (missing_blocks / warnings / risks) reusing the existing findings styling.

## Mock fixtures (`app/services/mock.py`)
`_mock_pcb()` gains an example `dfx_checklist` spanning all three categories (e.g.
`present` status LEDs, `recommended` SWD test points + 3 fiducials, …). `mock_run_rework`
scripts a PCB Critic that flags a missing DFX provision in round 1 (→ `missing_blocks`),
resolved by the PCB Engineer in round 2 — so the demo shows the DFX-driven PCB rework on
the rail. The step-mode mock slice for `pcb_critic` returns the scripted `PcbCritique`.

## Graceful degradation
- Empty `dfx_checklist` → report section and schematic note both omitted; no crash.
- Unknown `category`/`status` → schema defaults (`recommended`) keep it renderable.
- Step mode without a key still works (mock slice for `pcb_critic`).
- Rail without a PCB-rework beat → PCB Critic station just shows done/active, no packets.

## Testing strategy
- **Schema:** `DfxItem` defaults; `PcbReadiness.dfx_checklist` defaults empty; old payloads
  validate.
- **Agents:** PCB Engineer parses `dfx_checklist`; PCB Critic prompt mentions the DFX review
  dimension (assert keyword presence + that gaps land in `missing_blocks`).
- **Report:** context groups items by category with correct status markers; template renders
  the section; section absent when empty.
- **Schematic:** the top sheet contains a `DFT / DFM / BRING-UP` note with the actionable
  items; paren-balance + determinism tests still pass; note absent when no actionable items.
- **Rail (browser):** 6 stations render; the PCB rework beat shows packets pcb_critic→
  pcb_engineer + the PCB Engineer addressed glow (Senior Review Team mock).
- **Step mode (browser):** the flow now walks 6 stages incl. PCB Critic; the pending block
  shows the PcbCritique findings.
- WeasyPrint render stays skip-on-missing-libs (verify the real PDF in Docker before demo).

## Build order (one feature, two phases)
1. **Phase 1 — content (highest value):** schema → PCB Engineer/Critic prompts → mock →
   report section → schematic note.
2. **Phase 2 — visibility:** PCB Critic rail station + rework packets → step-mode PCB Critic
   stage + pending render.

## Affected files
- `app/models/schemas.py` — `DfxItem`, `PcbReadiness.dfx_checklist`, `StepResponse.pcb_critique`.
- `app/agents/pcb_engineer.py` — prompt + parse `dfx_checklist`.
- `app/agents/pcb_critic.py` — prompt DFX review dimension.
- `app/services/mock.py` — `dfx_checklist` fixture + scripted DFX rework + step slice.
- `app/services/stepwise.py` — `pcb_critic` stage.
- `app/generators/report.py`, `app/templates/report.html.j2` — DFX section.
- `app/generators/kicad.py`, `app/templates/root.kicad_sch.j2` — DFX top-sheet note.
- `app/static/index.html` — 6th rail station + PCB rework packets; step-mode PCB Critic stage + pending render.
- `tests/` — schema, agent, report, schematic, (browser) rail/step.
