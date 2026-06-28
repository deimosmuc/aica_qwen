# Agent Society "Mission Control" — Metro Pipeline Rail (Design Spec)

**Date:** 2026-06-28
**Status:** Approved in brainstorming, pending written-spec review.
**Track:** Polish / Agent-Society jury appeal (F4). This is **Run A** of the
deployment-ready push (Run B = persona, Run C = KiCad output quality).

## Summary

Make the multi-agent collaboration *visually come alive* with a **Metro-style live
pipeline rail** placed at the top of the "Agent collaboration" section. The rail
choreographs the pipeline as a transit line whose stations (the agents) light up in
sequence, and — the hero moment — renders the **Critic → Architect rework loop** as
amber "light-block" packets streaming backward along the line while the addressed
agent glows amber and re-runs. This turns the already-existing conflict→rework→
resolution arc (Critic→Architect loop + Arbitration) into the literal visual centre
of the Agent-Society track pitch.

The substance already exists (rework loop, rounds, arbitration, trace data). Run A is
**presentation**, not new pipeline logic.

## Goals

- An at-a-glance, animated overview of the whole pipeline that reads as "live mission
  control", shown in **both** auto-run and step-by-step modes.
- The **rework/conflict** is the visual hero: clearly show that the Critic sends notes
  back and the addressed agent reacts.
- A coherent **colour language** reused across rail, chat, and report accents.
- Deterministic in **Mock Mode** so the 5-minute demo video is repeatable.
- All user-facing text **English only** (project directive: no German in any output).

## Non-goals / out of scope (Run A)

- No full-page visual-identity refresh (header / panels / typography / global theme).
  Only *light* accent consistency rides along.
- No backend / pipeline changes — the rail is driven entirely by the existing `trace`.
- No new graph/animation library — plain Alpine.js + CSS keyframes, matching the stack.
- Persona selector, KiCad Stage 2, DRU impedance, light theme — separate runs/later.

## Locked design decisions (from brainstorming)

- **Form:** Hybrid — Metro **pipeline rail on top**, the existing Trace/Society tabs +
  chat **below** (chat = detail/substance, rail = choreography/overview).
- **Rail style:** Metro/transit line (chosen over a stepper and a pill track) — a
  horizontal track with station dots and a travelling progress glow.
- **Rework rendering:** **no badge / no round number.** Instead:
  - The Critic (the "speaker") emits **amber light-block packets** that travel
    *backward* along the line to the addressed agent.
  - The **addressed agent gets a warm amber back-glow** ("I'm addressed and reacting")
    while it re-runs; the glow fades when it completes.
- **Colour language:** green→blue = progress / hand-off (forward); **amber = critique /
  rework** (backward packets + addressed-agent glow + the existing ↺ Rework chat chip).
- **Scope:** the "Agent collaboration" section only; light global accents allowed.

## The Metro Rail

Horizontal track spanning the section, with **5 stations** in pipeline order:

| Station | Agent | Colour (existing `avatarColor`) |
|---|---|---|
| Requirements | Requirements Agent | `#3b82f6` blue |
| Architect | System Architect | `#8b5cf6` purple |
| Critic | Design Critic | `#ef4444` red |
| Arbitration | Arbitration | `#f59e0b` amber |
| PCB Eng. | PCB Engineer | `#0d9488` teal |

- **Station** = a coloured dot (agent colour) + a label beneath.
- **States:**
  - *upcoming* — dimmed (~0.38 opacity), neutral track behind.
  - *active* — pulsing ring in the agent colour (the current "speaker").
  - *done* — solid dot, the track segment behind it filled with the green→blue glow.
- **Forward progress glow** (green→blue) fills the track left→right as stations finish.
- A **"LIVE" chip** with a blinking dot sits in the section's caption while a run plays.

### Phase boundary

A subtle dashed divider on the rail after **Arbitration** separates the **Design
phase** from the **PCB-Readiness phase**, mirroring the existing "PCB-Readiness Phase"
divider in the society chat.

## Conflict / rework choreography (hero)

When a stage's trace step indicates a rework trigger (Design Critic step with
`status == "warning"` / non-empty `missing_blocks`, i.e. a `round > 1` follows):

1. **Amber packets** (small glowing dots, `#ffd56b` core + amber halo) travel
   *backward* along the track from the Critic station to the addressed agent
   (Architect), staggered, looping for the duration of the rework beat.
2. The **addressed agent** shows a soft, pulsing **amber back-glow** and is marked as
   re-running; the glow fades once that agent's next (round-2) step completes.
3. No badge, no number — the motion + glow carry the meaning.

The **same language** applies to the PCB phase if the **PCB Critic** sends the **PCB
Engineer** back for rework.

When round 1 is clean (no rework), there are simply no amber packets — only forward
progress. The choreography is fully data-driven.

## How it is driven (data → motion)

Single source of truth: the **`trace`** (`TraceStep[]`, each with `agent`, `role`,
`status`, `round`, `duration_ms`). No backend change — the trace already carries
everything; `mock_run_rework` already scripts a 2-round rework for the keyless demo.

- **Auto-run:** the full trace returns at once from `/api/run`. The rail **replays it
  as a timed choreography** — stations light in sequence, the forward glow advances,
  and amber packets + addressed-glow fire on the `round > 1` / `warning` beats. This
  reuses the same "reconcile against the trace and animate the not-yet-shown steps"
  pattern as `playSociety()` (the chat), so rail and chat stay in lock-step.
- **Step-by-step:** the rail advances **live** as each stage is approved — the pending
  stage shows *active*, approved stages show *done*; a round-2 Architect step lights the
  rework choreography at that moment.
- **Shared state:** rail and chat derive from the same trace source; a small helper
  maps the trace to per-station state (`done` / `active` / `upcoming`, plus which agent
  is currently "addressed" for the amber glow).

## Structure / where the code goes

- **`app/static/index.html` only.** New rail markup at the **top of the "2 · Agent
  collaboration" section**, above the Trace/Society tab row, rendered in both the
  auto-run result view and the stepwise view (the two existing copies of that section).
- A small Alpine helper (e.g. `railStations(trace, opts)`) computes each station's
  state from the trace; CSS `@keyframes` drive the pulse, glow, packet flow, and
  addressed-glow. Animations are CSS-only; Alpine just toggles classes / binds state.
- The auto-run replay extends the existing `playSociety()` timing so the rail and the
  chat bubbles animate from the same clock.
- **No backend, no schema, no template changes.**

## Graceful degradation

- Missing / empty `trace` → rail renders all stations as *upcoming* (no crash).
- A trace without any `round > 1` → forward progress only, no amber choreography.
- Unknown agent name in the trace → neutral grey station (no colour lookup crash).
- Reduced motion: respect `prefers-reduced-motion` — fall back to static state colours
  (filled/active/dim) without the travelling packets.

## Testing strategy

- **Browser smoke (Mock Mode, preview tools)** — the project has no pytest coverage for
  `index.html`, so verification is browser-based and matches existing practice:
  - Auto-run: stations light Requirements→…→PCB in order; the forward glow advances;
    on the scripted rework the amber packets stream Critic→Architect and the Architect
    shows the amber back-glow; no console errors.
  - Step mode: the rail advances per approval; the pending stage shows *active*; the
    round-2 step triggers the rework choreography.
  - Both modes: rail and chat stay in sync; reduced-motion path renders static.
- **Determinism:** Mock Mode (`mock_run` / `mock_run_rework`) yields the scripted
  2-round story so the choreography is repeatable for the recorded video.

## Risks

- **Replay timing vs the chat** — rail and chat must not drift. Mitigation: drive both
  from one clock (extend `playSociety`'s reconcile/stagger), single trace source.
- **Packet positioning across widths** — the backward packet path depends on station
  x-positions. Mitigation: position packets relative to the track (percentages between
  the two stations) so it survives responsive resizing; verify at a couple of widths.
- **Over-animation / distraction** — keep durations calm, honour `prefers-reduced-
  motion`, and only animate during an active run (static once settled).
- **Two copies of section 2** (auto + step) — keep the rail markup/logic factored so
  both copies stay consistent (shared helper + shared CSS, parallel markup).

## Affected files

- `app/static/index.html` — rail markup (×2 section copies), CSS keyframes, Alpine
  helper for per-station state, and replay-timing integration with `playSociety()`.
- (Docs) this spec; findings/status memory updated on completion.

No other files change.
