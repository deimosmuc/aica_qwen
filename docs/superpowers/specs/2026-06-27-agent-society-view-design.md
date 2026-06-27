# Agent Society View — Design Spec
Date: 2026-06-27

## Overview

Feature C: an animated "Agent Society" chat-dialog that replays the finished agent trace as a left/right conversation, showing the Critic–Architect rework loop as a visible back-and-forth debate. Pure frontend — no new backend endpoint, no new files, no build step.

## Goals

- Show the multi-agent pipeline as a living narrative for the demo video
- Make rework rounds (Critic → Architect back-and-forth) visually obvious
- Work fully in Mock Mode (keyless) for the recorded video
- Minimal code delta: stay inside the existing Single-Page Alpine.js app

## Decisions

| Question | Decision |
|---|---|
| Data source | Animated replay of existing `result.trace` / `acc.trace` — no new backend |
| Visual style | Chat-bubbles left/right (Chat-Dialog) |
| Placement | Tab toggle: "📋 Trace" \| "💬 Agent Society" above the existing collaboration section |
| Animation trigger | Automatic when the Society tab is opened (if bubbles not yet populated) |
| Bubble text length | Max 120 chars + `…` — details live in the Trace tab |

## Alpine.js State

Three new fields added to `data()`:

```js
societyBubbles: [],   // populated step-by-step during animation
societyPlaying: false, // true while setTimeout loop is running
societyTab: 'trace',  // 'trace' | 'society'
```

Reset on each new run: `societyBubbles = []`, `societyTab = 'trace'` — called at the top of `runAuto()` and `runStep()`.

## Animation Logic

```js
playSociety() {
  const steps = this.result?.trace ?? this.acc?.trace ?? [];
  if (!steps.length) return;
  this.societyPlaying = true;
  steps.forEach((step, i) => {
    setTimeout(() => {
      this.societyBubbles.push(step);
      if (i === steps.length - 1) this.societyPlaying = false;
    }, i * 350);
  });
}
```

Called on tab click only when `societyBubbles.length === 0`. If the user switches away mid-animation, the `setTimeout`s continue in the background silently — on return the tab shows the already-populated bubbles without replaying.

## UI Structure

The existing "2 · Agent collaboration" section (both auto-run result and step-by-step `acc`) gets a tab header prepended:

```html
<!-- Tab toggle -->
<div class="tab-row">
  <button :class="societyTab==='trace' ? 'tab-active' : 'tab'"
          @click="societyTab='trace'">📋 Trace</button>
  <button :class="societyTab==='society' ? 'tab-active' : 'tab'"
          @click="societyTab='society'; if(!societyBubbles.length) playSociety()">
    💬 Agent Society
  </button>
</div>

<!-- Existing trace list — unchanged -->
<div x-show="societyTab==='trace'"> … </div>

<!-- New Society chat -->
<div x-show="societyTab==='society'" class="society-chat">
  <template x-for="(s, i) in societyBubbles" :key="i">
    <div :class="s.agent==='Critic' ? 'bubble-right' : 'bubble-left'">
      <div class="bubble-avatar" :style="avatarColor(s.agent)"
           x-text="s.agent.slice(0,3).toUpperCase()"></div>
      <div class="bubble-body">
        <div class="bubble-meta">
          <span x-text="s.agent"></span>
          <span class="muted" x-show="s.round > 1" x-text="'· Round ' + s.round"></span>
          <span x-show="s.status==='warning'" class="chip-warn">↺ Rework</span>
        </div>
        <div class="bubble-text"
             x-text="s.summary.slice(0,120) + (s.summary.length>120?'…':'')"></div>
      </div>
    </div>
  </template>
  <div x-show="!societyBubbles.length && !societyPlaying" class="muted">
    Noch kein Run — starte die Pipeline oben.
  </div>
  <div x-show="societyPlaying" class="muted typing-indicator">…</div>
</div>
```

## Bubble Layout

- **Critic** → right-aligned (`flex-direction: row-reverse`, bubble background `#2d1515`)
- **All others** (Requirements, Architect, Arbitration) → left-aligned (bubble background `#1e2130`)
- Avatar circle 28px, color per agent via `avatarColor(agent)`:
  - Requirements → `#3b82f6` (blue)
  - Architect → `#8b5cf6` (purple)
  - Critic → `#ef4444` (red)
  - Arbitration → `#f59e0b` (amber)

## Rework Rounds

- `s.round > 1` → show "· Round N" label in bubble meta
- `s.status === 'warning'` → show `↺ Rework` chip (amber)
- No extra DOM elements needed — carried by existing `TraceStep.round` and `TraceStep.status`

## New CSS Classes

Minimal additions to the existing `<style>` block in `index.html`:

| Class | Purpose |
|---|---|
| `.tab-row` | Flex container for the two tab buttons |
| `.tab` / `.tab-active` | Toggle button styles |
| `.society-chat` | Flex column, `gap: 10px` |
| `.bubble-left` / `.bubble-right` | Flex row / row-reverse, `align-items: flex-start`, `gap: 8px` |
| `.bubble-avatar` | 28px circle, white bold text |
| `.bubble-body` | `flex: 1` |
| `.bubble-meta` | Small text row: agent name + round label + status chip |
| `.bubble-text` | Bubble text, `line-height: 1.4` |
| `.chip-warn` | Amber inline chip |
| `.typing-indicator` | Animated `…` while playing |

## Edge Cases

- **Empty trace**: `playSociety()` returns early; empty-state message shown.
- **Mock Mode**: Works fully — `mock_run_rework` provides 2-round trace with `round`, `status`, `summary` populated.
- **Single round (no rework)**: Round label hidden (`s.round > 1` guard); Critic still appears right with `ok` status.
- **Tab reset on new run**: `societyBubbles = []` + `societyTab = 'trace'` at top of `runAuto()` and `runStep()`.
- **Animation interrupted**: `setTimeout`s finish silently in background; tab shows complete bubbles on return.

## Scope

- Changes only `app/static/index.html`
- No new Python files, no new endpoints, no new tests (pure frontend)
- Manual verification in Mock Mode via `app-mock` launch profile (port 8011)
