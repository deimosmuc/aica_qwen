# Adaptive Clarification (Feature B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Requirements Agent's dead-end clarification questions into agent-proposed A/B/C choices the user resolves in the step-by-step flow, feeding the answers back through the existing `guidance` channel.

**Architecture:** Additive schema (`ClarifyingQuestion` with proposed options + single/multi mode), an extended Requirements-Agent prompt, a scripted mock so it runs keyless, and UI clarification cards that append the user's answers to the `acc.guidance` list the step flow already threads through every stage. No new endpoint.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, Alpine.js (single-page `index.html`), pytest.

Spec: `docs/superpowers/specs/2026-06-26-adaptive-clarification-design.md`

---

## File Structure

- `app/models/schemas.py` — add `ClarifyOption`, `ClarifyingQuestion`; add `Requirements.clarifications` + a backfill validator.
- `app/agents/requirements.py` — extend the system prompt to emit `clarifications`.
- `app/services/mock.py` — scripted clarifications in the mock Requirements output.
- `app/static/index.html` — clarification cards in the pending requirements step + answer→guidance accumulation.
- `tests/test_clarification.py` — new test file for schema + mock.
- `tests/test_requirements_agent.py` — add a parse test for clarifications.

---

## Task 1: Schema — ClarifyOption, ClarifyingQuestion, Requirements.clarifications

**Files:**
- Modify: `app/models/schemas.py` (the `Requirements` block, around lines 30-35)
- Test: `tests/test_clarification.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_clarification.py`:

```python
"""Feature B: adaptive clarification — schema + mock."""
from app.models.schemas import ClarifyOption, ClarifyingQuestion, Requirements


def test_clarifying_question_validates():
    q = ClarifyingQuestion(
        id="power",
        text="Which power source?",
        options=[ClarifyOption(label="USB-C, 5V", detail="simple"), ClarifyOption(label="Li-Ion")],
        select="multi",
        assumption="USB 5V",
    )
    assert q.select == "multi"
    assert q.options[0].label == "USB-C, 5V"
    assert q.options[0].detail == "simple"
    assert q.options[1].detail == ""  # detail defaults to empty


def test_clarifying_question_defaults_to_single_select():
    q = ClarifyingQuestion(id="x", text="?")
    assert q.select == "single"
    assert q.options == []


def test_requirements_backfills_questions_from_clarifications():
    r = Requirements(clarifications=[ClarifyingQuestion(id="p", text="Which supply?")])
    assert r.questions == ["Which supply?"]


def test_requirements_keeps_explicit_questions():
    r = Requirements(
        questions=["explicit one"],
        clarifications=[ClarifyingQuestion(id="p", text="Which supply?")],
    )
    assert r.questions == ["explicit one"]  # explicit questions are NOT overwritten
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_clarification.py -v`
Expected: FAIL — `ImportError: cannot import name 'ClarifyOption'`.

- [ ] **Step 3: Add the models + backfill validator**

In `app/models/schemas.py`, change the import line (currently `from pydantic import BaseModel, Field`) to:

```python
from pydantic import BaseModel, Field, model_validator
```

Replace the `Requirements` class (lines ~30-35) with:

```python
class ClarifyOption(BaseModel):
    """One proposed, selectable answer to a clarifying question."""

    label: str            # short, e.g. "USB-C, 5V"
    detail: str = ""      # one-line rationale shown under the label


class ClarifyingQuestion(BaseModel):
    """An ambiguity the Requirements Agent surfaces with concrete options.
    The user picks an option / types their own / skips (keeping `assumption`)."""

    id: str
    text: str
    options: list[ClarifyOption] = []
    select: Literal["single", "multi"] = "single"
    assumption: str = ""  # what the agent assumes if the user skips


class Requirements(BaseModel):
    requirements: list[str] = []
    constraints: list[str] = []
    questions: list[str] = []
    assumptions: list[str] = []
    confidence: float = 0.0
    clarifications: list[ClarifyingQuestion] = []

    @model_validator(mode="after")
    def _backfill_questions(self):
        # Keep the legacy plain-text "Open questions" list working when only the
        # new structured clarifications are provided.
        if self.clarifications and not self.questions:
            self.questions = [c.text for c in self.clarifications]
        return self
```

(`Literal` is already imported at the top of the file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_clarification.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `python -m pytest -q`
Expected: all previously-passing tests still pass (91 + 4 new).

- [ ] **Step 6: Commit**

```bash
git add app/models/schemas.py tests/test_clarification.py
git commit -m "feat(B): clarification schema — ClarifyingQuestion + options + question backfill"
```

---

## Task 2: Requirements Agent emits clarifications

**Files:**
- Modify: `app/agents/requirements.py` (the `SYSTEM_PROMPT` JSON-keys section, lines ~30-36)
- Test: `tests/test_requirements_agent.py` (add one test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_requirements_agent.py`:

```python
VALID_WITH_CLARIFY = {
    "requirements": ["24 V supply"],
    "constraints": [],
    "questions": [],
    "assumptions": [],
    "confidence": 0.6,
    "clarifications": [
        {
            "id": "power",
            "text": "Which power source?",
            "options": [
                {"label": "USB-C, 5V", "detail": "simple"},
                {"label": "Li-Ion + charger", "detail": "portable"},
            ],
            "select": "single",
            "assumption": "USB 5V",
        }
    ],
}


def test_agent_parses_clarifications():
    client = FakeClient(VALID_WITH_CLARIFY)
    result = RequirementsAgent().run(client, "a small board")
    assert len(result.clarifications) == 1
    q = result.clarifications[0]
    assert q.id == "power"
    assert q.select == "single"
    assert q.options[0].label == "USB-C, 5V"
    # questions backfilled from the clarification text
    assert result.questions == ["Which power source?"]
    # the prompt must instruct the model to produce options
    assert "clarifications" in client.calls[0]["system"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_requirements_agent.py::test_agent_parses_clarifications -v`
Expected: FAIL on `assert "clarifications" in client.calls[0]["system"]` (prompt not updated yet).

- [ ] **Step 3: Extend the system prompt**

In `app/agents/requirements.py`, in `SYSTEM_PROMPT`, replace the `- "questions": ...` line in the output-keys list with:

```
- "questions": array of strings (plain clarification questions; may be empty if you use clarifications)
- "clarifications": array of objects, each:
    {"id": short-stable-id, "text": the question,
     "options": [{"label": short choice, "detail": one-line rationale}, ...] (2-3 options),
     "select": "single" (default) or "multi" (only when several options can sensibly combine),
     "assumption": what you would assume if the user skips this question}
```

And append this rule to the `Rules:` block:

```
- For each genuine, decision-changing ambiguity, prefer a "clarifications" entry
  with 2-3 concrete options over a bare question. Keep clarifications few (about
  2-4) — only the ambiguities that would actually change the design. Use
  "select": "multi" only when multiple options can legitimately be combined.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_requirements_agent.py::test_agent_parses_clarifications -v`
Expected: PASS.

- [ ] **Step 5: Run the requirements + clarification tests**

Run: `python -m pytest tests/test_requirements_agent.py tests/test_clarification.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/agents/requirements.py tests/test_requirements_agent.py
git commit -m "feat(B): Requirements Agent proposes clarification options"
```

---

## Task 3: Mock mode ships scripted clarifications

**Files:**
- Modify: `app/services/mock.py` (the `Requirements(...)` block inside `mock_run`, lines ~22-43)
- Test: `tests/test_clarification.py` (add one test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_clarification.py`:

```python
def test_mock_requirements_has_clarifications():
    from app.services.mock import mock_run

    r = mock_run("").requirements
    assert len(r.clarifications) >= 2
    # at least one single and one multi, so the demo exercises both UIs
    assert any(c.select == "single" for c in r.clarifications)
    assert any(c.select == "multi" for c in r.clarifications)
    # every clarification offers concrete options and a fallback assumption
    assert all(c.options for c in r.clarifications)
    assert all(c.assumption for c in r.clarifications)
    # questions are backfilled so the legacy "Open questions" chip still counts
    assert len(r.questions) == len(r.clarifications)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_clarification.py::test_mock_requirements_has_clarifications -v`
Expected: FAIL — `assert len(r.clarifications) >= 2` (currently 0).

- [ ] **Step 3: Add scripted clarifications to the mock**

In `app/services/mock.py`, add `ClarifyOption, ClarifyingQuestion` to the imports from `app.models.schemas`.

In `mock_run`, replace the `questions=[...]` argument of the `Requirements(...)` constructor (lines ~34-37) with a `clarifications=[...]` argument (drop the explicit `questions` — it auto-backfills):

```python
        clarifications=[
            ClarifyingQuestion(
                id="rs485-isolation",
                text="Is galvanic isolation required on the RS485 interface?",
                select="single",
                options=[
                    ClarifyOption(label="Isolated transceiver + isolated DC-DC",
                                  detail="robust on a noisy fieldbus, more parts/cost"),
                    ClarifyOption(label="Non-isolated transceiver",
                                  detail="cheaper and smaller, fine for short quiet links"),
                ],
                assumption="Non-isolated RS485",
            ),
            ClarifyingQuestion(
                id="status-indicators",
                text="Which status indications should the board expose?",
                select="multi",
                options=[
                    ClarifyOption(label="Power LED", detail="supply present"),
                    ClarifyOption(label="Fault LED", detail="error / brown-out"),
                    ClarifyOption(label="Bus-activity LED", detail="RS485 traffic"),
                ],
                assumption="A single status LED",
            ),
        ],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_clarification.py::test_mock_requirements_has_clarifications -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass (the existing stepwise/orchestrator tests that assert "raised 2 clarification questions" still hold, because `questions` backfills to length 2).

- [ ] **Step 6: Commit**

```bash
git add app/services/mock.py tests/test_clarification.py
git commit -m "feat(B): scripted mock clarifications (one single, one multi) for keyless demo"
```

---

## Task 4: UI — clarification cards + answer→guidance accumulation

**Files:**
- Modify: `app/static/index.html` — the pending requirements output (around lines 242-249) and the Alpine component script (`approveStep`, state, around lines 517-602).

This task has no JS unit harness; it is verified in the browser via the project's run/preview workflow.

- [ ] **Step 1: Add clarification state + answer-collection helpers to the Alpine component**

In `app/static/index.html`, in the component `data()` object (near line 517-518), add a state field for answers:

```javascript
        clarifyAnswers: {},   // { [questionId]: { choice: Set<label> | "", text: "" } }
```

Add these methods to the component (place them next to `approveStep`, ~line 579):

```javascript
        clarifyInit(qs) {
          // start every question unanswered (skipped by default)
          this.clarifyAnswers = {};
          (qs || []).forEach(q => { this.clarifyAnswers[q.id] = { picked: [], text: "" }; });
        },
        clarifyToggle(q, label) {
          const a = this.clarifyAnswers[q.id];
          if (q.select === "multi") {
            const i = a.picked.indexOf(label);
            if (i >= 0) a.picked.splice(i, 1); else a.picked.push(label);
          } else {
            a.picked = (a.picked[0] === label) ? [] : [label];   // single: toggle/replace
          }
        },
        clarifyAnswered() {
          return Object.values(this.clarifyAnswers)
            .filter(a => a.picked.length || a.text.trim()).length;
        },
        clarifyToGuidance(qs) {
          // build one guidance string per answered question; skipped ones add nothing
          const out = [];
          (qs || []).forEach(q => {
            const a = this.clarifyAnswers[q.id];
            const txt = a.text.trim();
            const parts = a.picked.slice();
            if (txt) parts.push(txt);
            if (parts.length) out.push("GEKLÄRT: " + q.text + " → " + parts.join(", "));
          });
          return out;
        },
```

Modify `approveStep()` (line ~579) so that, when approving the requirements step, the clarification answers are pushed into `acc.guidance` before advancing. After the existing `const stage = ...` / before `this.acc.trace.push(...)`, insert:

```javascript
          if (stage === "requirements" && this.pending.requirements &&
              this.pending.requirements.clarifications &&
              this.pending.requirements.clarifications.length) {
            this.clarifyToGuidance(this.pending.requirements.clarifications)
                .forEach(g => this.acc.guidance.push(g));
          }
```

(Find the exact current body of `approveStep` first; insert the block right after `stage` is known and before the step is committed/advanced. Read lines 579-595 to place it precisely.)

- [ ] **Step 2: Initialise answers when a requirements step with clarifications arrives**

In `loadStage(i)` where the pending step is set (`this.stepIdx = i; this.pending = data;`, ~line 572), add right after:

```javascript
            if (data.requirements && data.requirements.clarifications && data.requirements.clarifications.length) {
              this.clarifyInit(data.requirements.clarifications);
            }
```

- [ ] **Step 3: Render the clarification cards in the pending requirements block**

In `app/static/index.html`, inside the pending requirements `<template x-if="pending.requirements">` block (after the existing `assumptions` `out-grp`, ~line 247), add:

```html
                    <template x-if="pending.requirements.clarifications && pending.requirements.clarifications.length">
                      <div class="clarify" style="margin-top:12px">
                        <b>Help the agents decide</b>
                        <template x-for="q in pending.requirements.clarifications" :key="q.id">
                          <div class="q-card" style="border:1px solid var(--border); border-radius:10px; padding:10px 12px; margin-top:8px">
                            <div x-text="q.text" style="font-weight:600"></div>
                            <div class="muted" x-show="q.select==='multi'" style="font-size:12px">Pick one or more</div>
                            <div style="display:flex; flex-direction:column; gap:6px; margin-top:6px">
                              <template x-for="o in q.options" :key="o.label">
                                <label style="display:flex; gap:8px; align-items:flex-start; cursor:pointer">
                                  <input :type="q.select==='multi' ? 'checkbox' : 'radio'"
                                         :checked="clarifyAnswers[q.id] && clarifyAnswers[q.id].picked.includes(o.label)"
                                         @change="clarifyToggle(q, o.label)">
                                  <span><b x-text="o.label"></b><span class="muted" x-show="o.detail" x-text="' — ' + o.detail"></span></span>
                                </label>
                              </template>
                            </div>
                            <input class="correct" style="margin-top:6px; width:100%"
                                   x-model="clarifyAnswers[q.id].text"
                                   placeholder="✏︎ own answer (optional)">
                            <div class="muted" style="font-size:12px; margin-top:4px"
                                 x-show="!(clarifyAnswers[q.id].picked.length || clarifyAnswers[q.id].text.trim())"
                                 x-text="'If skipped: ' + q.assumption"></div>
                          </div>
                        </template>
                        <div class="muted" style="margin-top:8px"
                             x-text="clarifyAnswered() + ' of ' + pending.requirements.clarifications.length + ' answered'"></div>
                      </div>
                    </template>
```

- [ ] **Step 4: Relabel the approve button for the requirements step**

The existing approve button (~line 280) reads "Approve & continue". To make the clarification flow obvious, make its label adapt when clarifications are present. Replace that button line with:

```html
                <button class="approve" @click="approveStep()"
                  x-text="(pending.requirements && pending.requirements.clarifications && pending.requirements.clarifications.length) ? 'Continue with my answers →' : 'Approve & continue'"></button>
```

- [ ] **Step 5: Verify in the browser (mock mode, no key needed)**

Use the project run workflow to launch the app (see project skill / `/run`). In the UI:
1. Turn the **Auto** toggle OFF (step-by-step mode).
2. Enter any request and run; let the **Requirements** step appear.
3. Confirm two clarification cards render: "RS485 isolation" (radio, single) and "status indications" (checkboxes, multi).
4. Pick an option on one, type a free-text answer on the other, leave nothing on a third option; confirm the "If skipped: …" hint shows only while unanswered and the "X of 2 answered" counter updates.
5. Click **Continue with my answers →**, advance to the Architect step, and confirm the chosen answers appear under **"Active constraints (honored by every agent)"** as `GEKLÄRT: …` lines.

Capture a screenshot of the clarification cards and of the resulting `GEKLÄRT:` guidance entries as proof.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "feat(B): UI clarification cards — answers flow into pipeline guidance"
```

---

## Self-Review notes (for the implementer)

- **Spec coverage:** schema (Task 1), agent options + single/multi (Task 2), mock keyless demo (Task 3), UI cards + free-text + skip + guidance feedback (Task 4). One-click `/api/run` is intentionally untouched (out of scope).
- **Backfill contract:** `questions` is only auto-filled when empty, so existing tests asserting explicit questions are unaffected; mock drops its explicit `questions` so the count (2) comes from the clarifications.
- **Guidance contract:** every answered question becomes a `GEKLÄRT: <question> → <answers>` line on `acc.guidance`; the step flow already passes `acc.guidance` to Architect/Critic/Arbitration ([stepwise.py:81](app/services/stepwise.py:81), [:96], [:116]).
- **Type consistency:** `ClarifyOption(label, detail)`, `ClarifyingQuestion(id, text, options, select, assumption)`, `clarifyAnswers[id] = {picked: [], text: ""}` used identically across Tasks 1-4.
