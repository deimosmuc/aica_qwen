# Live Progress Streaming (Auto Mode) — Design

**Date:** 2026-06-28
**Status:** Approved (design), pending implementation plan

## Problem

In **Auto mode** the browser fires a single blocking `POST /api/run`. The server
runs the *entire* pipeline (Requirements → Architect → Critic [+rework] →
Arbitration → PCB Engineer → PCB Critic [+rework]) and only returns when
everything is done — realistically **2–5 minutes** (one measured stage ≈ 18 s,
6–8 calls with rework). During that whole time the UI shows only a spinner.

Worse, the "LIVE" Mission-Control rail and the Agent-Society chat are **theatre
after the fact**: `playPipeline()` replays the already-finished trace at
600 ms/step (~4 s) *after* the result arrives. So the user waits minutes on a
spinner, then sees a 4-second "live" animation of work already completed.

Two cosmetic issues ride along:
- The **PCB Critic** renders on the *left* in the Society chat; as the
  antagonist to the PCB Engineer it should be on the **right** (like the Design
  Critic).
- The page gives no "many agents are working" signal beyond the spinner.

Out of scope (decided): the **PDF report** failing on the local Windows `.bat`
run. Root cause is that WeasyPrint needs Pango/Cairo/gdk-pixbuf, which the
Dockerfile installs but a local Windows venv lacks. The report works in the
Docker/deploy build (used for the demo/video). **No change** — we will not chase
WeasyPrint-on-Windows.

## Goal

In Auto mode, the rail and Society chat fill in **as each agent actually
finishes**, with a page-level signal that the agent team is at work. No more
spinner-then-replay.

## Approach: Server-Sent Events over a streamed POST

Chosen over polling (no shared run-state/store to manage) and over native
`EventSource` (GET-only; requirements text + guidance + constraints are awkward
as query params). We stream an SSE-framed body from a `POST` and read it with
`fetch` + a `ReadableStream` reader on the client.

### Backend

1. **Orchestrator → generator.** Extract the pipeline body of
   `Orchestrator.run()` into `run_stream()` that `yield`s typed events as work
   completes:
   - `stage_done` — one per finished agent call, carrying that agent's
     `TraceStep` plus its structured payload (requirements / architecture /
     critique / arbitration / pcb_readiness / pcb_critique) and `round`.
   - `final` — the complete `RunResponse` (same shape returned today), so the
     client renders the architecture/PCB sections exactly as now.
   - `error` — guard block / Qwen error / validation error, carrying the same
     notice text used today, immediately followed by a `final` event whose
     payload is the mock fallback (`_guarded_fallback`). Behaviour identical to
     the current blocking path, just streamed.
   - Mock mode emits the prepared trace as `stage_done` events (with a small
     server-side delay between them so the rail still animates) then `final`.

2. **`run()` keeps working.** Re-implement the existing blocking `run()` by
   draining `run_stream()` and returning the `final` payload. `/api/run`,
   `/api/step`, comparison, bench and all existing tests stay untouched.

3. **New route `POST /api/run/stream`.** Returns `StreamingResponse` with media
   type `text/event-stream`, writing `data: {json}\n\n` per event. Same request
   body as `/api/run` (`RunRequest`). Honors the same `profile`, `persona`,
   `guidance` plumbing.

### Frontend

4. **`runAuto()` consumes the stream.** Replace the single
   `fetch().json()` + `playPipeline()` with a streamed read: parse SSE events,
   and on each `stage_done` push the `TraceStep` into a live trace array and bump
   `playedSteps` so the rail + Society chat advance in real time. On `final`,
   set `this.result`, build the diagrams, fetch the guard. Delete the
   `playPipeline()` fake-replay path (and its timers) for auto runs.

5. **Page-level liveness.** While streaming, show a header chip such as
   "🟢 N agents collaborating · now: <current stage>" driven by the live trace;
   the existing rail `active` state already pulses. Spinner text updated to name
   the current agent rather than the generic "analysing…".

6. **PCB Critic on the right.** In both Society-chat blocks change
   `s.agent === 'Design Critic'` to
   `['Design Critic','PCB Critic'].includes(s.agent)` so both critics sit on the
   right (lines ~535 and ~690 of `app/static/index.html`).

## Data flow

```
runAuto() --POST /api/run/stream--> route --> Orchestrator.run_stream()
   <--SSE stage_done (Requirements)----  (agent finishes)
   <--SSE stage_done (Architect r1)----
   <--SSE stage_done (Critic r1, warn)-
   <--SSE stage_done (Architect r2)----  (rework)
   ... rail + society chat fill live as each arrives ...
   <--SSE final (full RunResponse)-----  --> render architecture/PCB/approval
```

## Error handling

- Guard block / Qwen error / truncation / validation error mid-stream → `error`
  event (same notice strings as today) then `final` with the mock fallback. The
  client shows the notice and renders the fallback result, exactly as the
  blocking path does now.
- Network drop mid-stream → client surfaces a generic "stream interrupted —
  retry" notice; no partial result is treated as final (only the `final` event
  sets `this.result`).
- Mock mode → identical event sequence, so the demo path exercises the same UI.

## Testing

- **Orchestrator:** `run_stream()` over a fake `ChatClient` emits the expected
  ordered event types (`stage_done` × N, then `final`); rework rounds produce the
  extra `stage_done` events; an injected error yields `error` then a mock
  `final`. Existing `run()` tests still pass (it drains the generator).
- **Route:** `POST /api/run/stream` returns `text/event-stream`; the streamed
  body parses into the expected event sequence ending in `final` (mock mode, no
  key — deterministic).
- **Frontend:** manual verification via the live server — rail advances stage by
  stage during a real run; both critics appear on the right; header chip shows
  active agents.

## Non-goals

- No change to `/api/step` (step mode already gives genuine per-stage progress).
- No change to the PDF report path or its Windows behaviour.
- No persistence / resumable runs / cancellation token (a dropped connection
  just abandons the run, same as today).
