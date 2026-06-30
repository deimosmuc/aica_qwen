# Universal activity indicator — design

Date: 2026-06-30
Status: approved (pending spec review)

## Problem

Four agent actions can be "busy", but only two give visible feedback:

| Action | State flag | Feedback today |
|---|---|---|
| Run agents (auto) | `loading` | Full metro rail + header chip + spinner |
| Step-by-step | `stepBusy` | Small "Running agent…" spinner |
| Compare | `comparing` | None — only greyed-out buttons |
| Preset Bench | `benching` | None — only button text |

Compare runs two full pipelines (multi-agent Orchestrator + single-agent baseline,
`app/services/comparison.py`) and takes ~1–3 min with no progress UI. The result panel
renders far down the page, so a user who scrolls sees nothing happening and assumes it
froze. Same gap for Bench.

## Goal

One coherent "something is working, be patient" indicator across all four actions,
unified under the existing metro metaphor rather than a competing UI element.

## Design

### Two presentations of one metaphor

- **Multi-agent auto** (`streamActive`): the full metro rail with all 6 stations, packet
  animations, and live conversation — unchanged. The busy "wimmel" view is appropriate
  because the whole society is collaborating.
- **Single-step and bulk** (`stepBusy` / `comparing` / `benching`): a compact
  **focused single station** — one node, its label, a running/waiting state, and a timer.
  Calmer and clearer than a 6-station row for a simple or opaque operation.

### Focused-station component

A single metro node on a short track stub:

- **Running:** solid station-colored core with a pulsing expanding ring + elapsed timer
  (`m:ss`). The ticking timer is the proof-of-life even when the label is static.
- **Waiting:** hollow amber ring, e.g. "waiting for your approval" (step mode between
  stages). No timer.

Station identity by mode:

- **Step mode:** the *real* current station, derived from the existing
  `railView()` active-key logic (`pending.stage` / `stepIdx`). E.g. "System Architect ·
  running…".
- **Compare / Bench:** a *synthetic* station, because these are blocking calls with no
  per-stage streaming — we cannot know the internal agent. E.g. "Comparing two designs ·
  running · multi + single agent, ~1–3 min". This is the honest framing; we do not fake
  an internal stage.

### Placement

- The full metro rail stays **in-flow** where it is now.
- The focused station is **sticky** while a long run is active, so it stays visible when
  the user scrolls (Compare/Bench results are far down the page). This directly fixes the
  original "looks frozen" complaint.

### State plumbing (Alpine)

- `busy` getter — `loading || stepBusy || comparing || benching`.
- `focusStation` getter — returns `{ label, color, state, showTimer }` chosen by which
  flag is set; step mode reuses `railView()`'s active station, compare/bench return their
  synthetic node.
- Elapsed timer — start a `setInterval` when `busy` flips true (watch), clear and reset
  when it flips false. Stored as `busyElapsed` seconds, formatted `m:ss`.

## Out of scope (YAGNI)

- No backend streaming for `/api/compare` or `/api/bench`. Converting them to SSE would
  give real per-stage stations but is a larger, riskier change before the deadline. The
  honest synthetic-station + timer is sufficient.
- The existing header status chip (Mock/Online) is unchanged.

## Testing

- Manual: trigger each of the four busy states and confirm the right presentation appears,
  the timer ticks, sticky stays visible on scroll during Compare, and the indicator clears
  on completion/error.
- Confirm no regression to the full metro rail in auto mode (stations, packets, legend).
