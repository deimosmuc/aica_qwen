# Live-Run Findings — 2026-06-27

Collected by Robert during a live qwen run (Senior Review Team), to be triaged into the
implementation plan(s). Severity: 🟥 bug · 🟧 UX gap · 🟦 enhancement.

## F1 🟦 PDF title should be a real project name, not the raw prompt
The report's `<h1>` currently uses the first line of the user's prompt text ("erstelle mir
ein grundgerüst für…"). It should show a fitting **project name**.
- Option A: ask for a project name via an input field (optional).
- Option B: auto-generate a sensible default name (e.g. from the architecture / a short
  LLM-derived title), pre-filled and editable.
- Likely both: auto-suggest + editable field. Affects `report._report_context` (title)
  and the UI/`GenerateRequest`.

## F2 🟧 Agent collaboration: show upcoming steps greyed-out
In the step-by-step flow only the current/finished agents are visible. The **next stages
should be visible but greyed-out** so the user always knows where they are in the
pipeline (assembly-line feel). Ties into making the pipeline progress legible.

## F3 🟥 Agent Society shows nothing in step-by-step mode
`playSociety()` (index.html ~789) reads `result.trace || acc.trace`. In step mode
`result` is null until the final approval, and `acc` is set to null right after the final
`approve()` (line 847). Depending on timing the function finds no steps and returns early
→ no chat bubbles. Works in auto-run (populated `result.trace`); brittle/empty in the
step flow. **Reproduce in mock mode and fix** (ensure the Society always has a trace
source; populate bubbles from `acc.trace` live during stepping and from `result.trace`
after).

## F4 ✅ DONE — Agent Society "mission control" metro pipeline rail
(2026-06-28, merge `6c4e8fb`.) A live animated metro rail atop the collaboration
section: stations light in sequence with a forward progress glow, a Design→PCB phase
divider and a LIVE chip; the Critic→Architect rework shows amber light-block packets
flowing back + an amber back-glow on the addressed agent (PCB Critic→PCB Engineer
lights the glow too). Driven by the existing trace via a unified reveal clock shared
with the society chat (timed replay in auto-run, live in step mode). Frontend-only.
Spec/plan: `2026-06-28-mission-control-metro-rail-{design,}.md`. Rework choreography
needs the rework-enabled **Senior Review Team** profile. Original note below.


The Agent-Society track rewards making the multi-agent collaboration come alive. The
current UI is a flat dark panel; the Society tab (the literal hero of the track) is plain
and currently buggy (F3). Direction to decide (see chat): turn the Agent Society into an
engaging animated "mission control" (avatars, live typing, hand-offs, Critic pushback,
rework arrows, round badges), a cohesive visual identity, and visible pipeline
choreography (connects to F2). Possibly the highest-leverage demo work — to be scoped.

## F5 🟦 Floorplan: thermal keepout must fence the *sensitive* part
The red dashed thermal barrier must clearly **enclose/isolate the SCD41** (the heat-
sensitive sensor) from the heat sources (Power, MCU) — not float as a vague diagonal. A
clean L-bracket hugging the protected zone reads correctly. Airflow for the PM sensor:
**one** clear directional arrow + "vent clearance", not two ambiguous in/out arrows.
→ The `FloorplanZone.separation` rendering should draw a keepout boundary around the
zone(s) named, with a legible side-label.

## F6 🟦 Candidate reasoning should surface the *placement conflict* explicitly
The strongest argument for separate sensors (PMS/SPS30 + SCD41) over an all-in-one (SEN66)
is **placement**: PM needs airflow at the board edge; CO₂/RH needs a thermally quiet,
draught-free zone — an all-in-one sits in one spot and can't satisfy both. The PCB
Engineer's pros/cons for sensor candidates should make this physical trade-off explicit
(ties the candidate cards to the floorplan). Robert asked why separate is favoured — the
answer is placement freedom + cost-per-function; the all-in-one wins on BOM/extra
measurands (VOC/NOx). Both are valid; surface the trade-off, don't hide it.

## F7 🟥 Step-by-step flow skips the PCB Engineer stage
The frontend `STAGES` (index.html) lists only 4 stages
(`requirements, architecture, critique, arbitration`) while the backend
`_STAGE_ORDER` (stepwise.py) has 5 (`+ pcb_engineer`). So in step-by-step mode the
PCB-Readiness stage never runs — auto-run produces a 6-step trace, step mode only 4.
Fixing it needs a `pending.pcb_readiness` render block + the field mapping
(`pcb_engineer` stage → `pcb_readiness` field) in `approveStep()`. Not a quick fix —
own small task.

---

## Triage / status (updated 2026-06-27)

- **F2 ✅ DONE** — upcoming pipeline stages now render greyed-out ("upcoming") below the
  pending step in the step-by-step trace. Browser-verified in mock mode.
- **F3 ✅ DONE** — was deeper than the `playSociety()` trace-source timing described
  above. The real blocker: the society-chat `<template x-for>` had **two root elements**
  (the PCB-divider `<template x-if>` + the bubble `<div>`), which Alpine silently refuses
  to render → zero bubbles even with a populated array, in BOTH auto and step mode.
  Fix = wrap each row in a single flex-column root `<div>` (both society blocks) PLUS a
  reconcile-based `playSociety()` that appends only not-yet-shown steps (live during
  stepping, across the acc→result hand-off, no duplicates on re-open). Browser-verified
  via real click path: bubbles 1→2→3→4 live, Design-Critic right-aligned with ↺ Rework.
- **F5, F6 → addressed at the data/render level by Smart Diagrams Phase 1**
  (2026-06-28, branch `feat/smart-diagrams-phase1`, plan
  `2026-06-28-smart-diagrams-candidates-phase1.md`). The PCB Engineer now emits
  `floorplan_zones` (with `separation` keep-out intent) and `component_choices`
  (recommended part + alternatives, pros/cons, star score); the report renders a
  category-coloured clustered block diagram, candidate cards, a zone floorplan with
  dashed keep-out lines, and a legend. **Still Phase 2 (visual polish, needs Robert's
  eye):** F5's exact L-bracket keep-out fence + single airflow arrow, F6's explicit
  candidate↔floorplan placement-conflict wording, and the client-side ELK colour/
  clustering/legend + SVG export in `index.html` (the report uses the Python fallback
  diagram until then).
- **F1 ✅ DONE** — Part A (auto-derived title) + Part B (2026-06-28, branch
  `fix/editable-project-title`): optional "Project name" field in the approval step
  overrides the PDF report title; blank falls back to the auto-derived title. The KiCad
  project filename stays `project`. Backend + endpoint tested; browser-verified.
- **F7 ✅ DONE** (2026-06-28, branch `fix/step-pcb-stage-and-impedance-gui`) — the
  frontend `STAGES` now includes `pcb_engineer` (+ `STAGE_META`), the approved
  arbitration is threaded into the step request, and `approveStep()` maps the
  `pcb_engineer` stage to the `pcb_readiness` field. Step mode now walks all 5 stages.
  Bundled the **impedance-GUI gap**: the web UI rendered `pcb_readiness` nowhere
  (only PDF + KiCad did). A shared `pcbReadinessHtml()` renderer (net-class table
  **incl. Impedance column**, constraints, candidate cards, floorplan zones) now feeds
  both the step pending block and a new "PCB-Readiness pack" panel in the auto-run
  result view. Browser-verified in mock mode (USB 90 Ω diff / RS485 120 Ω diff visible).

---
_Add new findings below as they come up during the live run._
