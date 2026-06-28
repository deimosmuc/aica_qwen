# Agent Society "Mission Control" — Metro Pipeline Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live, animated metro-style pipeline rail to the top of the "Agent collaboration" section that choreographs the agent run — stations lighting in sequence, and the Critic→Architect rework shown as amber light-block packets plus an amber back-glow on the addressed agent.

**Architecture:** Frontend-only, all in `app/static/index.html` (Alpine.js + CSS keyframes). A unified reveal clock (`playedSteps` + `playPipeline()`) replays the existing `trace` over time in auto-run and advances live in step mode; both the new rail and the existing society chat render from that one clock. A pure `railView()` helper maps the revealed trace to per-station state + rework choreography descriptors. No backend, schema, template, or pytest changes.

**Tech Stack:** Alpine.js 3 (CDN), plain CSS animations, FastAPI static serving. Verification is browser-based via the Claude Preview MCP tools (the project has no pytest coverage for `index.html`).

---

## Context the engineer needs

- **One file only:** `app/static/index.html`. It is a single-page Alpine app. The component factory is `function architect() { return { ... } }` (~line 715+). State fields are listed near the top of the returned object; methods follow.
- **The trace:** every run produces `trace: TraceStep[]`. Each step has `agent` (display name), `role`, `status` (`"ok"` | `"warning"`), `summary`, `round` (1-based; `>1` means a rework round), `duration_ms`. Agent display names are exactly: `"Requirements Agent"`, `"System Architect"`, `"Design Critic"`, `"Arbitration"`, `"PCB Engineer"`, `"PCB Critic"`.
- **Two run modes / two copies of section 2:**
  - **Auto-run** (`runAuto()`): `/api/run` returns the whole `result` (incl. `result.trace`) at once. Section 2 lives under `<template x-if="result">` with `<h2>2 · Agent collaboration</h2>`.
  - **Step-by-step** (`runStep()` → `loadStage()`/`approveStep()`): builds `acc.trace` one approved stage at a time; the not-yet-approved stage is `pending`. Section 2 lives under `<template x-if="acc">` with `<h2>2 · Agent collaboration — step by step</h2>`.
  - The **rework loop (round > 1) only occurs in auto-run** (the orchestrator's Critic→Architect loop). Step mode runs each stage once. So the amber rework choreography is an auto-run/replay phenomenon; step mode shows linear progression. This is expected and fine — the demo video uses auto-run.
- **Existing chat reveal (F3):** `playSociety()` reveals `result.trace`/`acc.trace` into `societyBubbles` with a 350 ms stagger, reconciling via `societyScheduled`. The typing indicator uses `societyPlaying`. **This plan replaces that mechanism with the unified clock** — keep the bubble *markup* but feed it from the shared clock. Verify F3 behaviour stays intact (bubbles appear progressively, no duplicates, Design Critic right-aligned with the ↺ Rework chip, the "PCB-Readiness Phase" divider before the first PCB Engineer bubble).
- **All user-facing strings must be English** (project directive).
- **Verification tooling:** use the Claude Preview MCP tools. Start the mock server (port 8011 if free, else add a temporary config on another port — remove it before the final commit). `Alpine.$data(document.querySelector('[x-data]'))` returns the live component for `preview_eval` driving/inspection.

---

## File Structure

- **Modify only:** `app/static/index.html`
  - CSS: one new style block for the rail (`.rail-*`, `.stn-*`, packet + glow keyframes, reduced-motion).
  - State: `playedSteps`; remove `societyBubbles`/`societyScheduled`/`societyPlaying` usage in favour of computed reveal.
  - Methods: `pipelineTrace()`, `revealedTrace()`, `playPipeline()`, `isPlaying()`, `railView()`; refactor of `playSociety()` callers; reset in `_resetRun()`; wiring in `runAuto()`/`approveStep()`/`loadStage()`.
  - Markup: a `<div class="rail">` block inserted after the `<h2>` in **both** section-2 copies; chat `x-for` switched to `revealedTrace()`.

No other files change.

---

## Task 1: Rail CSS

**Files:**
- Modify: `app/static/index.html` (the `<style>` block; insert near the other component styles, e.g. right after the `.society-typing` rule)

- [ ] **Step 1: Add the rail style block**

Insert this CSS (find the line `.society-typing { ... }` and add immediately after it):

```css
    /* --- Mission Control pipeline rail (F4) --- */
    .rail { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px;
            padding: 18px 16px 14px; margin-bottom: 16px; }
    .rail-cap { font-size: 11px; letter-spacing: .4px; text-transform: uppercase; color: var(--muted);
                margin-bottom: 18px; display: flex; align-items: center; gap: 8px; }
    .rail-live { width: 7px; height: 7px; border-radius: 50%; background: var(--ok);
                 animation: rl-blink 1.3s infinite; }
    @keyframes rl-blink { 0%,100% { opacity: 1 } 50% { opacity: .25 } }
    .rail-line { position: relative; height: 56px; }
    .rail-track { position: absolute; left: 6%; right: 6%; top: 11px; height: 4px;
                  background: var(--line); border-radius: 2px; overflow: hidden; }
    .rail-fill { position: absolute; left: 0; top: 0; height: 100%; width: 0;
                 background: linear-gradient(90deg, var(--ok), var(--accent)); transition: width .5s ease; }
    .rail-stns { position: absolute; left: 0; right: 0; top: 0; display: flex;
                 justify-content: space-between; padding: 0 6%; }
    .rail-stn { display: flex; flex-direction: column; align-items: center; gap: 8px; }
    .rail-dot { width: 18px; height: 18px; border-radius: 50%; border: 3px solid var(--panel-2);
                position: relative; transition: box-shadow .3s; }
    .rail-stn.upcoming .rail-dot { opacity: .38; }
    .rail-stn.active .rail-dot { box-shadow: 0 0 0 4px var(--accent); animation: rl-pulse 1.3s infinite; }
    @keyframes rl-pulse { 0%,100% { box-shadow: 0 0 0 4px var(--accent) } 50% { box-shadow: 0 0 0 7px transparent } }
    .rail-stn.addressed .rail-dot { animation: rl-glow 1.6s ease-in-out infinite; }
    @keyframes rl-glow { 0%,100% { box-shadow: 0 0 10px 3px #d2992288, 0 0 0 3px #d2992233 }
                          50% { box-shadow: 0 0 20px 7px #d29922ee, 0 0 0 6px #d2992255 } }
    .rail-lbl { font-size: 10px; color: var(--muted); text-align: center; white-space: nowrap; }
    .rail-stn.active .rail-lbl { color: var(--text); }
    .rail-stn.addressed .rail-lbl { color: #e8b75a; }
    .rail-phase { position: absolute; top: 2px; bottom: 18px; border-left: 1px dashed #3a4a5a; }
    .rail-pkt { position: absolute; top: 9px; width: 9px; height: 9px; border-radius: 50%;
                background: #ffd56b; box-shadow: 0 0 8px 2px #d29922; }
    .rail-pkt.p1 { animation: rl-flow 2.2s linear infinite; }
    .rail-pkt.p2 { animation: rl-flow 2.2s linear infinite .7s; }
    .rail-pkt.p3 { animation: rl-flow 2.2s linear infinite 1.4s; }
    @keyframes rl-flow { 0% { opacity: 0; transform: scale(.6) }
                         12% { opacity: 1; transform: scale(1) }
                         88% { opacity: 1; transform: scale(1) }
                         100% { opacity: 0; transform: scale(.6) } }
    .rail-legend { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 16px;
                   font-size: 11px; color: var(--muted); }
    .rail-legend i { display: inline-block; width: 16px; height: 4px; border-radius: 2px;
                     vertical-align: middle; margin-right: 6px; }
    .rail-legend .o { width: 11px; height: 11px; border-radius: 50%; background: #d29922;
                      box-shadow: 0 0 7px 2px #d29922; }
    @media (prefers-reduced-motion: reduce) {
      .rail-live, .rail-stn.active .rail-dot, .rail-stn.addressed .rail-dot, .rail-pkt { animation: none !important; }
      .rail-pkt { display: none !important; }
    }
```

- [ ] **Step 2: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): rail CSS for the mission-control pipeline rail"
```

---

## Task 2: Unified reveal clock + chat refactor

Replace the chat-only `playSociety()` reveal with a single clock both the chat and (later) the rail consume.

**Files:**
- Modify: `app/static/index.html` (state fields ~715-725; `_resetRun()`; `runAuto()`; `runStep()`; `loadStage()`; `approveStep()`; `playSociety()` and its callers; society chat markup ~428-458 and ~559-589)

- [ ] **Step 1: Add `playedSteps` to state, drop the bubble array**

In the returned state object, find:

```js
        societyBubbles: [], societyPlaying: false, societyTab: 'trace', societyScheduled: 0,
```

Replace with:

```js
        playedSteps: 0, societyTab: 'trace', _pipelineTimers: [],
```

- [ ] **Step 2: Reset the clock in `_resetRun()`**

In `_resetRun()` find:

```js
          this.societyBubbles = []; this.societyPlaying = false; this.societyTab = 'trace'; this.societyScheduled = 0;
```

Replace with:

```js
          this._pipelineTimers.forEach(clearTimeout); this._pipelineTimers = [];
          this.playedSteps = 0; this.societyTab = 'trace';
```

- [ ] **Step 3: Add the clock methods; replace `playSociety()`**

Replace the entire `playSociety() { ... }` method with these methods:

```js
        pipelineTrace() {
          return (this.result && this.result.trace) || (this.acc && this.acc.trace) || [];
        },
        revealedTrace() {
          return this.pipelineTrace().slice(0, this.playedSteps);
        },
        isPlaying() {
          return this.playedSteps < this.pipelineTrace().length;
        },
        // Timed replay (auto-run): reveal trace steps one at a time. Idempotent —
        // only schedules the not-yet-revealed steps, so repeat calls never duplicate.
        playPipeline() {
          const total = this.pipelineTrace().length;
          const start = this.playedSteps;
          for (let k = 0; k < total - start; k++) {
            this._pipelineTimers.push(setTimeout(() => { this.playedSteps = start + k + 1; }, k * 600));
          }
        },
```

- [ ] **Step 4: Drive the clock from the run flows**

In `runAuto()`, find the line that sets `this.result = await res.json();` and add a reveal kickoff after the diagram builds. Locate:

```js
            this.diagramSvg = await this.buildDiagram(this.result.architecture);
            this.exportSvg = await this.buildExportDiagram(this.result.architecture);
            await this.fetchGuard();
```

Add immediately after `await this.fetchGuard();` (still inside the `try`):

```js
            this.playPipeline();
```

In `approveStep()`, find:

```js
          this.acc.trace.push(this.pending.trace_step);
          if (this.societyTab === 'society') this.playSociety();  // live bubble if watching (F3)
```

Replace with:

```js
          this.acc.trace.push(this.pending.trace_step);
          this.playedSteps = this.acc.trace.length;  // step mode: reveal approved steps immediately
```

In `approveStep()`, the final-result branch already sets `this.result = {...}`. After it sets `this.result`, the revealed count must cover the full trace. Find (end of `approveStep`):

```js
          this.mode = this.acc.mode; this.acc = null; this.stepIdx = -1;
```

Add immediately before that line:

```js
          this.playedSteps = this.result.trace.length;
```

- [ ] **Step 5: Point the society chat markup at the clock (both copies)**

There are TWO society-chat blocks (stepwise ~428, auto ~559). In **each**, find:

```html
          <template x-for="(s, i) in societyBubbles" :key="i">
```

Replace with:

```html
          <template x-for="(s, i) in revealedTrace()" :key="i">
```

In **each** block, the PCB divider uses `societyBubbles.slice(0, i)`. Find both occurrences:

```html
            <template x-if="s.agent === 'PCB Engineer' && !societyBubbles.slice(0, i).some(b => b.agent === 'PCB Engineer')">
```

Replace each with:

```html
            <template x-if="s.agent === 'PCB Engineer' && !revealedTrace().slice(0, i).some(b => b.agent === 'PCB Engineer')">
```

In **each** block, the empty-state and typing indicator use the old fields. Find (stepwise copy):

```html
          <div x-show="!societyBubbles.length && !societyPlaying" class="society-empty">
            No run yet.
          </div>
          <div x-show="societyPlaying" class="society-typing">···</div>
```

Replace with:

```html
          <div x-show="!revealedTrace().length && !isPlaying()" class="society-empty">
            No run yet.
          </div>
          <div x-show="isPlaying()" class="society-typing">···</div>
```

Find (auto copy):

```html
            <div x-show="!societyBubbles.length && !societyPlaying" class="society-empty">
              No run yet — start the pipeline above.
            </div>
            <div x-show="societyPlaying" class="society-typing">···</div>
```

Replace with:

```html
            <div x-show="!revealedTrace().length && !isPlaying()" class="society-empty">
              No run yet — start the pipeline above.
            </div>
            <div x-show="isPlaying()" class="society-typing">···</div>
```

- [ ] **Step 6: Fix the society tab button (both copies)**

Both tab buttons call `playSociety()` on click. Find each:

```html
                  @click="societyTab='society'; playSociety()">
```

Replace each with:

```html
                  @click="societyTab='society'">
```

(The clock now runs independently of the tab; switching tabs just shows the already-revealed bubbles.)

- [ ] **Step 7: Verify in the browser (F3 intact + reveal works)**

Start the mock server and verify:

Run (preview_start `app-mock`, or a temp config on a free port). Then drive auto-run:

```js
// preview_eval
(async () => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  d.input = "24V sensor board, STM32, USB-C, RS485, status LEDs."; d.auto = true;
  await d.runAuto();
  await new Promise(r => setTimeout(r, 5000)); // let the replay finish
  return { played: d.playedSteps, total: d.pipelineTrace().length, bubbles: d.revealedTrace().length };
})()
```

Expected: `played === total` and `bubbles === total` (all steps revealed after replay). Open the 💬 Agent Society tab, confirm bubbles render, Design Critic is right-aligned with a ↺ Rework chip, and the "PCB-Readiness Phase" divider appears before the first PCB Engineer bubble. Check `preview_console_logs` (level error) → none.

- [ ] **Step 8: Commit**

```bash
git add app/static/index.html
git commit -m "refactor(ui): unified pipeline reveal clock; chat renders from shared trace"
```

---

## Task 3: `STATIONS` constant + `railView()` helper

A pure function mapping the revealed trace to per-station state and rework descriptors. Browser-unit-tested via `preview_eval`.

**Files:**
- Modify: `app/static/index.html` (add `railView()` near the other methods, e.g. after `revealedTrace()`)

- [ ] **Step 1: Add the helper**

Add this method (place right after `revealedTrace()`):

```js
        railView() {
          const STATIONS = [
            { key: 'requirements', label: 'Requirements', agent: 'Requirements Agent', color: '#3b82f6' },
            { key: 'architecture', label: 'Architect',    agent: 'System Architect',   color: '#8b5cf6' },
            { key: 'critique',     label: 'Critic',        agent: 'Design Critic',      color: '#ef4444' },
            { key: 'arbitration',  label: 'Arbitration',   agent: 'Arbitration',        color: '#f59e0b' },
            { key: 'pcb_engineer', label: 'PCB Eng.',      agent: 'PCB Engineer',       color: '#0d9488' },
          ];
          const revealed = this.revealedTrace();
          const total = this.pipelineTrace().length;
          const settled = total > 0 && this.playedSteps >= total;
          const last = revealed.length ? revealed[revealed.length - 1] : null;
          const seen = new Set(revealed.map(s => s.agent));
          // active station: step mode -> pending/loading stage; auto replay -> last revealed agent until settled
          const pendingStage = this.pending ? this.pending.stage
            : (this.stepBusy && this.stepIdx >= 0 ? this.STAGES[this.stepIdx] : null);
          let activeKey = pendingStage;
          if (!activeKey && last && !settled) {
            const a = STATIONS.find(st => st.agent === last.agent);
            activeKey = a ? a.key : null;
          }
          // rework beat (auto replay only): the active step is a warning Critic or a round>1 Architect
          let addressed = null, packetFrom = null, packetTo = null;
          if (!pendingStage && last && !settled &&
              ((last.agent === 'Design Critic' && last.status === 'warning') ||
               (last.agent === 'System Architect' && last.round > 1))) {
            addressed = 'System Architect';
            packetFrom = 'critique';
            packetTo = 'architecture';
          }
          const stations = STATIONS.map(st => {
            let state = 'upcoming';
            if (st.key === activeKey) state = 'active';
            else if (seen.has(st.agent)) state = 'done';
            return { key: st.key, label: st.label, color: st.color, state,
                     addressed: st.agent === addressed };
          });
          // forward fill %: fraction of stations reached (done or active)
          const reached = stations.filter(s => s.state !== 'upcoming').length;
          const fillPct = STATIONS.length > 1 ? Math.round((reached - 1) / (STATIONS.length - 1) * 100) : 0;
          return { stations, fillPct: Math.max(0, fillPct), packetFrom, packetTo,
                   active: this.isPlaying() || !!pendingStage };
        },
```

- [ ] **Step 2: Browser-unit-test the helper**

With the mock server running and the page loaded (no run needed), evaluate the helper against synthetic traces:

```js
// preview_eval
(() => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  // linear progress, 2 of 5 revealed, still playing
  d.result = { trace: [
    { agent: 'Requirements Agent', status: 'ok', round: 1 },
    { agent: 'System Architect',   status: 'ok', round: 1 },
    { agent: 'Design Critic',      status: 'ok', round: 1 },
    { agent: 'Arbitration',        status: 'ok', round: 1 },
    { agent: 'PCB Engineer',       status: 'ok', round: 1 },
  ]};
  d.acc = null; d.pending = null; d.stepBusy = false; d.stepIdx = -1;
  d.playedSteps = 2;
  const v1 = d.railView();
  // rework beat: warning Critic is the last revealed
  d.result.trace = [
    { agent: 'Requirements Agent', status: 'ok', round: 1 },
    { agent: 'System Architect',   status: 'ok', round: 1 },
    { agent: 'Design Critic',      status: 'warning', round: 1 },
    { agent: 'System Architect',   status: 'ok', round: 2 },
    { agent: 'Arbitration',        status: 'ok', round: 1 },
    { agent: 'PCB Engineer',       status: 'ok', round: 1 },
  ];
  d.playedSteps = 3;
  const v2 = d.railView();
  d.result = null; d.playedSteps = 0;  // reset
  return {
    v1_states: v1.stations.map(s => s.key + ':' + s.state),
    v2_packet: [v2.packetFrom, v2.packetTo],
    v2_addressed: v2.stations.filter(s => s.addressed).map(s => s.key),
  };
})()
```

Expected:
- `v1_states` = `["requirements:done","architecture:active","critique:upcoming","arbitration:upcoming","pcb_engineer:upcoming"]`
- `v2_packet` = `["critique","architecture"]`
- `v2_addressed` = `["architecture"]`

If the output matches, the helper is correct. (No commit yet — the helper is unused until Task 4.)

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): railView() helper mapping trace to pipeline-rail state"
```

---

## Task 4: Rail markup (both section copies)

**Files:**
- Modify: `app/static/index.html` (after the `<h2>` in both section-2 copies)

- [ ] **Step 1: Add the rail markup to the stepwise copy**

Find:

```html
      <section class="panel">
        <h2>2 · Agent collaboration — step by step</h2>
        <div class="tab-row">
```

Insert the rail block between the `</h2>` and `<div class="tab-row">`:

```html
        <div class="rail" x-show="railView().stations.length">
          <div class="rail-cap"><span class="rail-live" x-show="railView().active"></span> Agent collaboration · <span x-text="railView().active ? 'LIVE' : 'done'"></span></div>
          <div class="rail-line">
            <div class="rail-track"><div class="rail-fill" :style="`width:${railView().fillPct}%`"></div></div>
            <div class="rail-phase" style="left:81.5%"></div>
            <template x-for="(p, i) in (railView().packetFrom ? [1,2,3] : [])" :key="i">
              <div class="rail-pkt" :class="'p'+p"
                   :style="`left:${railView().packetFrom==='critique' ? 56 : 56}%; animation-name:rl-flow`"></div>
            </template>
            <div class="rail-stns">
              <template x-for="st in railView().stations" :key="st.key">
                <div class="rail-stn" :class="st.addressed ? 'addressed' : st.state">
                  <div class="rail-dot" :style="`background:${st.state==='upcoming' ? '#3a4a5a' : st.color}`"></div>
                  <div class="rail-lbl" x-text="st.label"></div>
                </div>
              </template>
            </div>
          </div>
          <div class="rail-legend">
            <span><i style="background:linear-gradient(90deg,var(--ok),var(--accent))"></i>Progress / hand-off →</span>
            <span><i style="background:#ffd56b"></i>← Critic feedback</span>
            <span><span class="o" style="display:inline-block;margin-right:6px;vertical-align:middle"></span>addressed / reacting</span>
          </div>
        </div>
```

> **Note on packet positioning:** the backward packets animate from the Critic (~56%) toward the Architect (~31%). The exact `left` start and the `rl-flow` keyframe's horizontal travel are tuned in Task 5; for now the three packets render at the Critic position. (Task 5 makes them travel.)

- [ ] **Step 2: Add the same rail markup to the auto copy**

Find:

```html
        <section class="panel">
          <h2>2 · Agent collaboration</h2>
          <div class="tab-row">
```

Insert the **identical** rail `<div class="rail"> … </div>` block (copy it verbatim from Step 1) between `</h2>` and `<div class="tab-row">`. The markup is data-driven, so the same block works in both modes.

- [ ] **Step 3: Verify the rail renders and advances (auto + step)**

Auto-run replay:

```js
// preview_eval
(async () => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  d.input = "24V sensor board, STM32, USB-C, RS485, status LEDs."; d.auto = true;
  await d.runAuto();
  await new Promise(r => setTimeout(r, 600));   // mid-replay
  const mid = d.railView().stations.map(s => s.state);
  await new Promise(r => setTimeout(r, 5000));  // settled
  const end = d.railView().stations.map(s => s.state);
  return { mid, end };
})()
```

Expected: `mid` shows leftmost stations `done`/`active` and rightmost `upcoming`; `end` shows all `done` (none `active`). Take a `preview_screenshot` mid-replay for visual confirmation of the lit rail. Then step mode:

```js
// preview_eval
(async () => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const settle = async () => { for (let i=0;i<40 && (d.stepBusy || (!d.pending && !d.result));i++) await sleep(60); };
  d.input = "24V sensor board"; d.auto = false;
  await d.runStep(); await settle();
  const first = d.railView().stations.map(s => s.key+':'+s.state);
  return { first };  // requirements should be 'active'
})()
```

Expected: `requirements:active`, the rest `upcoming`. Confirm no console errors.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): render the metro pipeline rail in both run views"
```

---

## Task 5: Rework choreography (travelling packets)

Make the amber packets actually travel Critic→Architect during the rework beat.

**Files:**
- Modify: `app/static/index.html` (the `@keyframes rl-flow` rule from Task 1; the packet markup in both rail copies)

- [ ] **Step 1: Make the flow keyframe travel between the two stations**

The stations sit at even positions across the track (`left:6%`..`right:6%`, i.e. station centres at ~6%, ~28.5%, ~50%, ~71.5%, ~94% of the rail width — Critic at 50%, Architect at ~28.5%). Replace the Task 1 `@keyframes rl-flow` with one that travels from the Critic to the Architect:

```css
    @keyframes rl-flow { 0%   { left: 50%; opacity: 0; transform: scale(.6) }
                         12%  { opacity: 1; transform: scale(1) }
                         88%  { left: 30%; opacity: 1; transform: scale(1) }
                         100% { left: 28.5%; opacity: 0; transform: scale(.6) } }
```

- [ ] **Step 2: Simplify the packet markup in both rail copies**

In **both** rail copies, replace the packet `<template>` from Task 4:

```html
            <template x-for="(p, i) in (railView().packetFrom ? [1,2,3] : [])" :key="i">
              <div class="rail-pkt" :class="'p'+p"
                   :style="`left:${railView().packetFrom==='critique' ? 56 : 56}%; animation-name:rl-flow`"></div>
            </template>
```

with (the `left` is now driven entirely by the keyframe):

```html
            <template x-if="railView().packetFrom === 'critique'">
              <div><div class="rail-pkt p1"></div><div class="rail-pkt p2"></div><div class="rail-pkt p3"></div></div>
            </template>
```

- [ ] **Step 3: Verify the choreography with the scripted rework**

The mock pipeline includes a rework round (`mock_run_rework`) via the orchestrator on auto-run. Drive auto-run and catch the rework beat:

```js
// preview_eval
(async () => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  d.input = "24V sensor board, STM32, USB-C, RS485, status LEDs."; d.auto = true;
  await d.runAuto();
  const seen = { packet: false, addressed: false };
  // poll railView across the replay to catch the rework beat
  for (let i = 0; i < 30; i++) {
    const v = d.railView();
    if (v.packetFrom === 'critique') seen.packet = true;
    if (v.stations.some(s => s.addressed)) seen.addressed = true;
    await new Promise(r => setTimeout(r, 250));
    if (!d.isPlaying()) break;
  }
  return { trace: d.pipelineTrace().map(s => s.agent + (s.round>1?'(R'+s.round+')':'') + ':' + s.status), ...seen };
})()
```

Expected: the `trace` contains a `System Architect(R2)` and/or a `Design Critic:warning` step, and both `seen.packet` and `seen.addressed` are `true` at some point during the replay. If the mock trace has no rework round, note it and confirm with `mock_run_rework` data (the auto run uses the rework-capable mock); the choreography is correct as long as it fires when a `round>1`/`warning` step is the active one.

Take a `preview_screenshot` during the rework beat showing the amber packets between Critic and Architect and the Architect's amber glow.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): animate Critic->Architect rework packets on the rail"
```

---

## Task 6: Final polish + cross-mode smoke

**Files:**
- Modify: `app/static/index.html` (only if the smoke surfaces a fix)

- [ ] **Step 1: Reduced-motion check**

In `preview_eval`, emulate reduced motion is not directly togglable; instead verify the CSS guard exists and the static states still read correctly by inspecting computed styles of a `.rail-stn.active .rail-dot` (it should still have a box-shadow ring). Confirm the `@media (prefers-reduced-motion: reduce)` block from Task 1 is present in the served file:

```js
// preview_eval
(async () => (await (await fetch('/?_cb='+Date.now(),{cache:'no-store'})).text())).then
// simpler: fetch and check
```

Use instead:

```js
// preview_eval
(async () => {
  const t = await (await fetch('/?_cb='+Date.now(), {cache:'no-store'})).text();
  return { reducedMotion: t.includes('prefers-reduced-motion'), noGerman: !/Empfehlung|Noch kein|GEKLÄRT/.test(t) };
})()
```

Expected: `reducedMotion: true`, `noGerman: true`.

- [ ] **Step 2: Full cross-mode smoke**

- Auto-run: rail lights left→right, rework packets+glow fire, settles to all-done; chat (Society tab) animates in sync, Critic right-aligned + ↺ Rework, PCB divider present.
- Step mode: rail advances per approval; pending stage shows active; reaches PCB Engineer; final approve builds the result with the rail all-done.
- `preview_console_logs` (level error) → none in either mode.
- `preview_screenshot` of the settled rail for the records.

- [ ] **Step 3: Run the Python suite (guard against accidental breakage)**

Run: `python -m pytest -q`
Expected: `195 passed, 1 skipped` (unchanged — this task touches no Python).

- [ ] **Step 4: Final commit**

```bash
git add app/static/index.html
git commit -m "polish(ui): mission-control rail reduced-motion + cross-mode smoke"
```

---

## Self-Review

**Spec coverage:**
- Hybrid rail-on-top + chat-below → Task 4 (rail above the tabs) + Task 2 (chat from shared clock). ✓
- Metro rail with stations/states/forward glow/LIVE chip → Task 1 (CSS) + Task 3 (`railView`) + Task 4 (markup). ✓
- Rework: amber packets + addressed back-glow, no badge → Task 1 (`.rail-pkt`, `.addressed`) + Task 3 (`packetFrom/To`, `addressed`) + Task 5 (travel). ✓
- Phase boundary after Arbitration → `.rail-phase` (Task 1) + markup `left:81.5%` (Task 4). ✓
- Colour language green→blue / amber → Task 1 CSS + legend (Task 4). ✓
- Driven by trace; replay in auto, live in step; rail+chat one clock → Task 2. ✓
- English-only → Task 1/4 strings English; Task 6 checks `noGerman`. ✓
- Graceful degradation (empty trace, no rework, reduced motion) → `x-show="railView().stations.length"`, packet `x-if`, reduced-motion media query. ✓
- No backend/schema/template change → only `index.html` touched. ✓

**Placeholder scan:** every step has concrete code/commands and expected output. No TBD/TODO. ✓

**Type/name consistency:** `playedSteps`, `pipelineTrace()`, `revealedTrace()`, `isPlaying()`, `playPipeline()`, `railView()` used consistently across Tasks 2-6; station `key`s (`requirements/architecture/critique/arbitration/pcb_engineer`) match `STAGES` and `pending.stage`; agent display names match the trace. ✓

**Known nuance:** the rework choreography only fires in auto-run (the rework loop is orchestrator-only; step mode runs each stage once) — documented in "Context" and Task 5. The phase-divider `left:81.5%` and packet travel `%` are visual approximations to verify/adjust during Tasks 4-5 browser checks.
