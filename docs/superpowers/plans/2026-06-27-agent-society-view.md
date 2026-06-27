# Agent Society View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an animated "Agent Society" chat-dialog tab to the existing "2 · Agent collaboration" section that replays the finished trace as a left/right conversation, highlighting the Critic–Architect rework loop.

**Architecture:** Pure frontend change in `app/static/index.html`. Three new Alpine.js state fields (`societyBubbles`, `societyPlaying`, `societyTab`) and one new method (`playSociety()`). A tab toggle switches between the existing trace list and the new chat-dialog. No new backend endpoints, no new files.

**Tech Stack:** Alpine.js 3.x (already loaded via CDN), CSS custom properties (existing dark theme variables), vanilla JS `setTimeout` for animation.

---

## File Map

| File | Change |
|---|---|
| `app/static/index.html` | Only file touched: new CSS classes, new Alpine state fields + method, tab toggle markup in both Auto-run and Step-by-step collaboration sections |

No new files. No backend changes. No new tests (pure UI feature; manual verification in Mock Mode).

---

### Task 1: Add CSS classes for the Society tab

**Files:**
- Modify: `app/static/index.html` — inside the `<style>` block, after line 134 (`.correct` rule, before `</style>`)

- [ ] **Step 1: Add the new CSS rules**

In `app/static/index.html`, find the line:
```css
    textarea.correct { width: 100%; margin-top: 8px; min-height: 0; }
```
Insert after it (before `</style>`):

```css
    /* --- Agent Society tab ------------------------------------------------ */
    .tab-row { display: flex; border: 1px solid var(--line); border-radius: 8px;
      overflow: hidden; margin-bottom: 14px; }
    .tab-row button { flex: 1; border-radius: 0; border: none; border-right: 1px solid var(--line);
      background: var(--panel-2); color: var(--muted); font-weight: 500; padding: 8px 0;
      font-size: 13px; cursor: pointer; }
    .tab-row button:last-child { border-right: none; }
    .tab-row button.tab-active { background: var(--panel); color: var(--text); font-weight: 600; }
    .society-chat { display: flex; flex-direction: column; gap: 10px; }
    .bubble-left { display: flex; flex-direction: row; gap: 8px; align-items: flex-start; }
    .bubble-right { display: flex; flex-direction: row-reverse; gap: 8px; align-items: flex-start; }
    .bubble-avatar { width: 28px; height: 28px; border-radius: 50%; display: flex;
      align-items: center; justify-content: center; color: #fff; font-size: 9px;
      font-weight: 700; flex-shrink: 0; }
    .bubble-body { flex: 1; max-width: 72%; }
    .bubble-left .bubble-body { background: #1e2130; border-radius: 0 8px 8px 8px; padding: 8px 10px; }
    .bubble-right .bubble-body { background: #2d1515; border-radius: 8px 0 8px 8px; padding: 8px 10px; }
    .bubble-meta { font-size: 11px; color: var(--muted); margin-bottom: 3px; display: flex;
      gap: 5px; align-items: center; flex-wrap: wrap; }
    .bubble-right .bubble-meta { justify-content: flex-end; }
    .bubble-text { font-size: 13px; line-height: 1.4; color: var(--text); }
    .chip-rework { background: rgba(210,153,34,.15); color: var(--warn); border: 1px solid var(--warn);
      border-radius: 999px; padding: 1px 7px; font-size: 10px; font-weight: 600; }
    .society-empty { color: var(--muted); font-size: 13px; padding: 10px 0; }
    .typing { color: var(--muted); font-size: 22px; letter-spacing: 2px; padding: 2px 0; }
```

- [ ] **Step 2: Start the dev server and verify no visual regressions**

```bash
QWEN_API_KEY="" uvicorn app.main:app --port 8011 --reload
```
Open http://localhost:8011 — the page should load normally. CSS additions are inert until used.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "style(society): add CSS classes for Agent Society chat tab"
```

---

### Task 2: Add Alpine.js state and `playSociety()` method

**Files:**
- Modify: `app/static/index.html` — the `architect()` function's `data()` return object and `_resetRun()`

- [ ] **Step 1: Add `avatarColor()` helper and the three new state fields**

In `app/static/index.html`, find the `data()` return object. It starts around:
```js
        loading: false, result: null, approved: false, gen: null, genError: "",
        mode: "mock", guard: null,
        acc: null, pending: null, stepIdx: -1, stepBusy: false, stepNotice: "", stepStopped: false,
        diagramSvg: null, constraintsText: "", correctText: "",
        clarifyAnswers: {},
```

Add three new fields at the end of that block (before `PROFILES:`):
```js
        societyBubbles: [], societyPlaying: false, societyTab: 'trace',
```

So it reads:
```js
        loading: false, result: null, approved: false, gen: null, genError: "",
        mode: "mock", guard: null,
        acc: null, pending: null, stepIdx: -1, stepBusy: false, stepNotice: "", stepStopped: false,
        diagramSvg: null, constraintsText: "", correctText: "",
        clarifyAnswers: {},
        societyBubbles: [], societyPlaying: false, societyTab: 'trace',
        PROFILES: ["Uniform qwen-plus", "Uniform qwen-max", "Budget Turbo", "Senior Review Team"], selectedProfile: "Uniform qwen-plus",
```

- [ ] **Step 2: Reset society state in `_resetRun()`**

Find:
```js
        _resetRun() {
          this.result = null; this.approved = false; this.gen = null; this.genError = "";
          this.acc = null; this.pending = null; this.stepIdx = -1;
          this.stepStopped = false; this.stepNotice = ""; this.diagramSvg = null;
        },
```

Replace with:
```js
        _resetRun() {
          this.result = null; this.approved = false; this.gen = null; this.genError = "";
          this.acc = null; this.pending = null; this.stepIdx = -1;
          this.stepStopped = false; this.stepNotice = ""; this.diagramSvg = null;
          this.societyBubbles = []; this.societyPlaying = false; this.societyTab = 'trace';
        },
```

- [ ] **Step 3: Add `playSociety()` and `avatarColor()` methods**

Find the `clarifyToggle` method. After its closing `},` add:

```js
        playSociety() {
          const steps = (this.result && this.result.trace) || (this.acc && this.acc.trace) || [];
          if (!steps.length) return;
          this.societyPlaying = true;
          steps.forEach((step, i) => {
            setTimeout(() => {
              this.societyBubbles.push(step);
              if (i === steps.length - 1) this.societyPlaying = false;
            }, i * 350);
          });
        },
        avatarColor(agent) {
          const map = {
            'Requirements Agent': '#3b82f6',
            'System Architect':   '#8b5cf6',
            'Design Critic':      '#ef4444',
            'Arbitration':        '#f59e0b',
          };
          const color = map[agent] || '#6b7280';
          return `background:${color}`;
        },
```

- [ ] **Step 4: Reload browser and verify no JS errors**

Open http://localhost:8011, open browser console — should be zero errors. The new state fields are invisible until the tab markup is added.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat(society): Alpine state + playSociety() + avatarColor() helpers"
```

---

### Task 3: Add tab toggle and Society chat to the Auto-run result section

**Files:**
- Modify: `app/static/index.html` — the `<template x-if="result">` block, around line 371

- [ ] **Step 1: Wrap the existing trace list with a tab toggle**

Find the Auto-run "Agent trace" section:
```html
        <!-- Agent trace -->
        <section class="panel">
          <h2>2 · Agent collaboration</h2>
          <div class="trace">
            <template x-for="(s, i) in result.trace" :key="i">
```

Replace the `<h2>` and opening of `<div class="trace">` section — specifically, insert the tab-row header and wrap the existing `<div class="trace">` in a `x-show` div. The full replacement for the section opening:

```html
        <!-- Agent trace -->
        <section class="panel">
          <h2>2 · Agent collaboration</h2>
          <div class="tab-row">
            <button :class="societyTab==='trace' ? 'tab-active' : ''"
                    @click="societyTab='trace'">📋 Trace</button>
            <button :class="societyTab==='society' ? 'tab-active' : ''"
                    @click="societyTab='society'; if(!societyBubbles.length) playSociety()">
              💬 Agent Society
            </button>
          </div>

          <!-- Existing trace list -->
          <div x-show="societyTab==='trace'">
            <div class="trace">
              <template x-for="(s, i) in result.trace" :key="i">
```

- [ ] **Step 2: Close the new wrapper div after the existing trace list ends**

After the closing `</template>` of the `x-for` loop and before the `</section>` closing tag of the auto-run trace section, find:

```html
            </template>
          </div><!-- /.trace -->
        </section>
```

(Note: the actual closing may look slightly different — find the `</div>` that closes `<div class="trace">` in the auto-run result section, immediately followed by `</section>`.)

Replace those closing tags with:

```html
            </template>
            </div><!-- /.trace -->
          </div><!-- /tab:trace -->

          <!-- Society chat -->
          <div x-show="societyTab==='society'" class="society-chat">
            <template x-for="(s, i) in societyBubbles" :key="i">
              <div :class="s.agent==='Design Critic' ? 'bubble-right' : 'bubble-left'">
                <div class="bubble-avatar" :style="avatarColor(s.agent)"
                     x-text="s.agent.slice(0,3).toUpperCase()"></div>
                <div class="bubble-body">
                  <div class="bubble-meta">
                    <span x-text="s.agent"></span>
                    <span x-show="s.round > 1" x-text="'· Round ' + s.round"></span>
                    <span x-show="s.status==='warning'" class="chip-rework">↺ Rework</span>
                  </div>
                  <div class="bubble-text"
                       x-text="s.summary.slice(0,120) + (s.summary.length > 120 ? '…' : '')"></div>
                </div>
              </div>
            </template>
            <div x-show="!societyBubbles.length && !societyPlaying" class="society-empty">
              Noch kein Run — starte die Pipeline oben.
            </div>
            <div x-show="societyPlaying" class="typing">···</div>
          </div><!-- /tab:society -->

        </section>
```

- [ ] **Step 3: Verify in browser — Auto mode**

With the dev server running (http://localhost:8011):
1. Enter any prompt (e.g. "RS485 sensor board") and click "Run agents" (Auto mode ON).
2. After the result appears, the "2 · Agent collaboration" section should show two tabs: "📋 Trace" and "💬 Agent Society".
3. Click "💬 Agent Society" — bubbles should animate in one by one (~350ms apart).
4. Requirements Agent, System Architect, Arbitration should appear on the LEFT.
5. Design Critic should appear on the RIGHT with red avatar.
6. If the mock includes a rework round (round > 1), "· Round 2" label and "↺ Rework" chip should be visible on the Critic bubble.
7. Click "📋 Trace" — existing trace list reappears unchanged.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat(society): tab toggle + Society chat in auto-run result view"
```

---

### Task 4: Add tab toggle and Society chat to the Step-by-step section

**Files:**
- Modify: `app/static/index.html` — the `<template x-if="acc">` block (stepwise section), around line 256

- [ ] **Step 1: Wrap the existing step trace list with a tab toggle**

Find the Step-by-step "Agent collaboration" section:
```html
    <template x-if="acc">
      <section class="panel">
        <h2>2 · Agent collaboration — step by step</h2>
        <div class="trace">
          <template x-for="s in acc.trace" :key="s.agent">
```

Replace the section opening to add the tab-row and wrap the existing trace in `x-show`:

```html
    <template x-if="acc">
      <section class="panel">
        <h2>2 · Agent collaboration — step by step</h2>
        <div class="tab-row">
          <button :class="societyTab==='trace' ? 'tab-active' : ''"
                  @click="societyTab='trace'">📋 Trace</button>
          <button :class="societyTab==='society' ? 'tab-active' : ''"
                  @click="societyTab='society'; if(!societyBubbles.length) playSociety()">
            💬 Agent Society
          </button>
        </div>

        <!-- Existing step trace (approved steps + pending step) -->
        <div x-show="societyTab==='trace'">
          <div class="trace">
            <template x-for="s in acc.trace" :key="s.agent">
```

- [ ] **Step 2: Close the new wrapper div after the existing step trace content**

The stepwise section currently ends after the pending step block and the clarification UI. Find the closing `</section>` of the `<template x-if="acc">` block. Immediately before it, add the closing div for the trace-tab wrapper and the Society chat:

```html
        </div><!-- /tab:trace (stepwise) -->

        <!-- Society chat (stepwise — shows approved steps so far) -->
        <div x-show="societyTab==='society'" class="society-chat">
          <template x-for="(s, i) in societyBubbles" :key="i">
            <div :class="s.agent==='Design Critic' ? 'bubble-right' : 'bubble-left'">
              <div class="bubble-avatar" :style="avatarColor(s.agent)"
                   x-text="s.agent.slice(0,3).toUpperCase()"></div>
              <div class="bubble-body">
                <div class="bubble-meta">
                  <span x-text="s.agent"></span>
                  <span x-show="s.round > 1" x-text="'· Round ' + s.round"></span>
                  <span x-show="s.status==='warning'" class="chip-rework">↺ Rework</span>
                </div>
                <div class="bubble-text"
                     x-text="s.summary.slice(0,120) + (s.summary.length > 120 ? '…' : '')"></div>
              </div>
            </div>
          </template>
          <div x-show="!societyBubbles.length && !societyPlaying" class="society-empty">
            Noch kein Run gestartet.
          </div>
          <div x-show="societyPlaying" class="typing">···</div>
        </div><!-- /tab:society (stepwise) -->

      </section>
    </template>
```

- [ ] **Step 3: Verify in browser — Step-by-step mode**

With the dev server running (http://localhost:8011):
1. Uncheck "Auto mode" checkbox.
2. Enter a prompt and click "Run agents (step by step)".
3. Approve each agent step through the pipeline.
4. After the Requirements Agent step is approved, the "2 · Agent collaboration — step by step" section should now show the tab toggle.
5. Switch to "💬 Agent Society" — approved steps so far should animate in.
6. Approve remaining steps, switch back to Society — all approved steps shown.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat(society): tab toggle + Society chat in step-by-step view"
```

---

### Task 5: Final verification and edge cases

**Files:**
- Read-only verification, no code changes

- [ ] **Step 1: Mock Mode rework round demo**

Start the app in Mock Mode:
```bash
QWEN_API_KEY="" uvicorn app.main:app --port 8011 --reload
```

Run with "Senior Review Team" profile (or any profile) in Auto mode. The mock returns a 2-round trace (`mock_run_rework`). Verify:
- Society tab shows Architect bubble (Round 1, left) → Critic bubble (Round 2 rework, right, with "↺ Rework" chip) → Architect bubble (Round 2, left) → Arbitration bubble (right).
- "· Round 2" label appears on round-2 bubbles.
- Animation runs left-to-right in time (one bubble every ~350ms).
- Existing Trace tab still shows the old step list unchanged.

- [ ] **Step 2: Tab reset on re-run**

Run the pipeline once, switch to Society tab, then click "Run agents" again. Verify:
- Tab resets to "📋 Trace" automatically (because `_resetRun()` sets `societyTab = 'trace'`).
- Society tab on the new result starts with empty bubbles and re-animates on click.

- [ ] **Step 3: Run the hermetic test suite**

```bash
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest -q
```

Expected: all 110 tests pass (no backend changes means no test regressions).

- [ ] **Step 4: Final commit**

If no code changes were needed in this task, no commit required. If edge cases required fixes, commit with:
```bash
git add app/static/index.html
git commit -m "fix(society): edge case fixes from final verification"
```

---

### Task 6: Merge to main

- [ ] **Step 1: Verify branch is clean**

```bash
git status
git log main..HEAD --oneline
```

Expected: 4 commits ahead of main (Tasks 1–4), working tree clean.

- [ ] **Step 2: Merge to main with no-ff**

```bash
git checkout main
git merge --no-ff feat/agent-society -m "feat(society): Agent Society animated chat tab (Feature C)"
```

- [ ] **Step 3: Confirm test suite on main**

```bash
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest -q
```

Expected: all 110 tests pass.
