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

## F4 🟦 Overall UI is "bieder" (plain) — won't earn bonus points
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
- **F1, F5, F6 → deferred to the "Smart Diagrams + Component Candidates" feature.** F5/F6
  reference `FloorplanZone.separation`, airflow arrows and candidate cards that **do not
  exist in code yet** — they are refinement notes for that unbuilt feature
  (see `2026-06-27-smart-diagrams-and-component-candidates-design.md`), not bugs in
  shipped code. F1 (project-name title) is a small standalone feature.
- **F7** newly found while triaging F2 — step mode missing the PCB stage.

---
_Add new findings below as they come up during the live run._
