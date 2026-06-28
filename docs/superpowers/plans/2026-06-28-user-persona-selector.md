# User Persona Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Professional/Student/Maker persona selector that re-tones every agent's output (live mode) by prepending a persona instruction to the existing `guidance` channel, with a visible persona label in the UI and the report.

**Architecture:** A new pure `app/services/persona.py` maps a persona key to an instruction string + display label. `routes.py` prepends the instruction to `guidance` for `/run` and `/step` (so all agents honour it with no signature change) and passes the persona to the report for `/generate`. The frontend adds a selector (default Professional) and a result-header label. Live-only effect; Mock fixtures unchanged.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, Jinja2, Alpine.js, pytest. Frontend verified via Claude Preview MCP.

---

## Context the engineer needs

- `guidance: list[str]` is already threaded to every agent and formatted by
  `app/agents/base.py:guidance_block()`. Prepending one string makes every agent honour it.
- `/run` (`routes.py:87`) calls `Orchestrator(settings, profile).run(req.requirements_text, req.guidance)`.
- `/step` (`routes.py:~203-209`) resolves the model then calls `run_stage(req, settings)`.
- `/generate` calls `generate_report_pdf(req.result, req.requirements_text, _PROJECT_NAME, architecture_svg=client_svg, title=req.project_name)`.
- Mock Mode (`mock_run` / `mock_run_rework`) ignores `guidance` → output unchanged; the persona is surfaced only as a label.
- Run command: `python -m pytest -q` (baseline: 213 passed, 1 skipped).
- Frontend is `app/static/index.html` (Alpine). It already has a profile selector (`selectedProfile`, `PROFILES`) and sends `profile` in `/run`, `/step`, `/generate` bodies. Browser verify via `Alpine.$data(document.querySelector('[x-data]'))` on the mock server (restart the dev server after Python changes — uvicorn has no --reload; only index.html is served fresh).
- English-only output.

---

## File Structure

- `app/services/persona.py` (new) — `Persona` type, instruction/label maps, `resolve_persona`/`persona_instruction`/`persona_label`.
- `app/models/schemas.py` — `persona` field on `RunRequest`, `StepRequest`, `GenerateRequest`.
- `app/api/routes.py` — prepend persona instruction to guidance (`/run`, `/step`); pass persona to the report (`/generate`).
- `app/generators/report.py` + `app/templates/report.html.j2` — persona label line.
- `app/static/index.html` — selector + result-header label; send `persona` in the three bodies.
- `tests/` — `test_persona.py` (new), `test_run_endpoint.py`, `test_report.py`.

---

## Task 1: persona.py module

**Files:**
- Create: `app/services/persona.py`
- Test: `tests/test_persona.py` (new)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_persona.py
from app.services.persona import (
    resolve_persona, persona_instruction, persona_label, PERSONA_INSTRUCTIONS,
)


def test_resolve_known_and_default():
    assert resolve_persona("student") == "student"
    assert resolve_persona("maker") == "maker"
    assert resolve_persona("professional") == "professional"
    assert resolve_persona(None) == "professional"      # default
    assert resolve_persona("banana") == "professional"  # unknown -> default


def test_instruction_and_label():
    assert "engineering student" in persona_instruction("student").lower()
    assert "hobbyist maker" in persona_instruction("maker").lower()
    assert "professional hardware engineer" in persona_instruction(None).lower()  # default
    assert persona_label("student") == "Student"
    assert persona_label("banana") == "Professional"


def test_every_persona_has_an_instruction():
    for key in ("professional", "student", "maker"):
        assert key in PERSONA_INSTRUCTIONS and PERSONA_INSTRUCTIONS[key].strip()
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_persona.py -q` → ImportError.

- [ ] **Step 3: Implement** — create `app/services/persona.py`:

```python
"""User persona → prompt instruction + display label.

A persona re-tones every agent's output. It rides the existing `guidance` channel
(routes.py prepends `persona_instruction(...)`), so no agent signature changes. Pure
and deterministic; unknown / missing personas fall back to "professional".
"""
from __future__ import annotations

from typing import Literal

Persona = Literal["professional", "student", "maker"]

_DEFAULT: str = "professional"

PERSONA_INSTRUCTIONS: dict[str, str] = {
    "professional": ("Audience: a professional hardware engineer. Be concise and "
                     "technical, assume EE fluency, reference relevant standards / best "
                     "practices, minimal hand-holding."),
    "student": ("Audience: an engineering student. Explain reasoning and trade-offs in "
                "teaching terms, define jargon on first use, favour clarity over brevity."),
    "maker": ("Audience: a hobbyist maker. Be practical and DIY-friendly, prefer "
              "accessible low-cost widely-available parts, use plain language, flag where "
              "a simpler approach suffices."),
}

PERSONA_LABELS: dict[str, str] = {
    "professional": "Professional", "student": "Student", "maker": "Maker",
}


def resolve_persona(persona: str | None) -> str:
    """Return a valid persona key; unknown / None -> the default ("professional")."""
    return persona if persona in PERSONA_INSTRUCTIONS else _DEFAULT


def persona_instruction(persona: str | None) -> str:
    """The audience instruction string for the resolved persona."""
    return PERSONA_INSTRUCTIONS[resolve_persona(persona)]


def persona_label(persona: str | None) -> str:
    """The display label for the resolved persona."""
    return PERSONA_LABELS[resolve_persona(persona)]
```

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_persona.py -q`.

- [ ] **Step 5: Commit** — `git add app/services/persona.py tests/test_persona.py && git commit -m "feat(persona): persona -> instruction + label module"`

---

## Task 2: Schema fields

**Files:**
- Modify: `app/models/schemas.py` (`RunRequest` ~16-24; `StepRequest` ~331-344; `GenerateRequest` ~253-262)
- Test: `tests/test_pcb_schemas.py`

- [ ] **Step 1: Write failing test** — append to `tests/test_pcb_schemas.py`:

```python
def test_persona_fields_default_none():
    from app.models.schemas import RunRequest, StepRequest, GenerateRequest
    from app.services.mock import mock_run
    assert RunRequest(requirements_text="x").persona is None
    assert StepRequest(stage="requirements", requirements_text="x").persona is None
    assert GenerateRequest(requirements_text="x", result=mock_run("x")).persona is None
    assert RunRequest(requirements_text="x", persona="student").persona == "student"
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_pcb_schemas.py::test_persona_fields_default_none -q`.

- [ ] **Step 3: Implement** — add the field to each request model.

In `RunRequest` (after the `profile` field):

```python
    persona: str | None = Field(default=None, description="Audience persona (professional|student|maker); re-tones output.")
```

In `StepRequest` (after `pcb_readiness`):

```python
    persona: str | None = None
```

In `GenerateRequest` (after `project_name`):

```python
    persona: str | None = Field(default=None, description="Audience persona for the report label.")
```

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_pcb_schemas.py -q`.

- [ ] **Step 5: Commit** — `git add app/models/schemas.py tests/test_pcb_schemas.py && git commit -m "feat(schema): persona on run/step/generate requests"`

---

## Task 3: routes.py threading

**Files:**
- Modify: `app/api/routes.py` (imports; `/run` ~78-87; `/step` ~196-210; `/generate` report call ~122-125)
- Test: `tests/test_run_endpoint.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_run_endpoint.py`:

```python
def test_run_prepends_persona_instruction_to_guidance(monkeypatch):
    captured = {}

    class FakeOrch:
        def __init__(self, settings, profile=None, client=None):
            pass

        def run(self, text, guidance=None):
            captured["guidance"] = guidance
            return mock_run(text)

    monkeypatch.setattr(routes, "Orchestrator", FakeOrch)
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "persona": "student",
                                      "guidance": ["Use part XYZ"]})
    assert r.status_code == 200
    g = captured["guidance"]
    assert "engineering student" in g[0].lower()   # persona instruction first
    assert g[1] == "Use part XYZ"                   # user's constraint preserved


def test_step_prepends_persona_instruction(monkeypatch):
    from app.services.config import Settings
    captured = {}
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))

    def fake_run_stage(req, settings):
        captured["guidance"] = req.guidance
        from app.models.schemas import StepResponse, TraceStep
        return StepResponse(stage=req.stage, mode="mock",
                            trace_step=TraceStep(agent="Requirements Agent", role="r", summary="s"))

    monkeypatch.setattr(routes, "run_stage", fake_run_stage)
    client = TestClient(app)
    r = client.post("/api/step", json={"stage": "requirements", "requirements_text": "x",
                                       "persona": "maker", "guidance": ["keep it cheap"]})
    assert r.status_code == 200
    assert "hobbyist maker" in captured["guidance"][0].lower()
    assert captured["guidance"][1] == "keep it cheap"
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_run_endpoint.py -q`.

- [ ] **Step 3a: Import the helper** — add to `routes.py` imports:

```python
from app.services.persona import persona_instruction
```

- [ ] **Step 3b: `/run` prepend** — replace the `run()` body's return:

```python
    settings = get_settings()
    profile = profile_for(req.profile, req.model, settings)
    guidance = [persona_instruction(req.persona)] + req.guidance
    return Orchestrator(settings, profile).run(req.requirements_text, guidance)
```

- [ ] **Step 3c: `/step` prepend** — in `step()`, before the `try:` that calls `run_stage`, merge the persona into the request's guidance:

```python
    req = req.model_copy(update={"guidance": [persona_instruction(req.persona)] + req.guidance})
    try:
        return run_stage(req, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 3d: `/generate` persona to report** — pass the persona to the report call:

```python
        pdf_bytes = generate_report_pdf(
            req.result, req.requirements_text, _PROJECT_NAME,
            architecture_svg=client_svg, title=req.project_name, persona=req.persona,
        )
```

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_run_endpoint.py -q`.

- [ ] **Step 5: Commit** — `git add app/api/routes.py tests/test_run_endpoint.py && git commit -m "feat(api): thread persona into guidance (/run, /step) + report (/generate)"`

---

## Task 4: Report persona label

**Files:**
- Modify: `app/generators/report.py` (`generate_report_pdf` ~503-525; `_report_context` ~175+)
- Modify: `app/templates/report.html.j2` (meta area near the title/date)
- Test: `tests/test_report.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_report.py`:

```python
def test_report_context_persona_label():
    ctx = _report_context(mock_run("x"), "A board", "project", persona="student")
    assert ctx["persona_label"] == "Student"
    ctx2 = _report_context(mock_run("x"), "A board", "project")
    assert ctx2["persona_label"] == ""   # no persona -> no label


def test_report_template_renders_persona_label():
    from app.generators.report import _jinja_env
    ctx = _report_context(mock_run("x"), "A 24V board", "project", persona="maker")
    ctx["architecture_svg"] = "<svg/>"; ctx["floorplan_svg"] = "<svg/>"
    html = _jinja_env.get_template("report.html.j2").render(**ctx)
    assert "Audience: Maker" in html
```

- [ ] **Step 2: Run, expect failure** — `python -m pytest tests/test_report.py -q`.

- [ ] **Step 3a: Import + context** — in `report.py`, add the import near the top:

```python
from app.services.persona import persona_label
```

Change `_report_context` signature to accept `persona`:

```python
def _report_context(result: RunResponse, requirements_text: str, project_name: str,
                    title: str | None = None, persona: str | None = None) -> dict:
```

Add to the returned dict:

```python
        "persona_label": persona_label(persona) if persona else "",
```

- [ ] **Step 3b: Pass persona through `generate_report_pdf`** — change its signature and the `_report_context` call:

```python
def generate_report_pdf(
    result: RunResponse, requirements_text: str, project_name: str,
    architecture_svg: str | None = None, title: str | None = None, persona: str | None = None,
) -> bytes:
```

and inside:

```python
    context = _report_context(result, requirements_text, project_name, title=title, persona=persona)
```

- [ ] **Step 3c: Template** — in `report.html.j2`, near the date/meta line under the `<h1>`, add a conditional label. Find the existing meta line (e.g. the date) and add beside/under it:

```html
  {% if persona_label %}<div class="meta-persona">Audience: {{ persona_label }}</div>{% endif %}
```

Add minimal CSS to the report `<style>`:

```css
  .meta-persona { font-size: 8.5px; color: #0f766e; margin-top: 2px; }
```

- [ ] **Step 4: Run, expect pass** — `python -m pytest tests/test_report.py -q`.

- [ ] **Step 5: Commit** — `git add app/generators/report.py app/templates/report.html.j2 tests/test_report.py && git commit -m "feat(report): Audience persona label"`

---

## Task 5: Frontend selector + label

**Files:**
- Modify: `app/static/index.html` (state; the input controls area; `runAuto`/`loadStage`/`generate` request bodies; result-header label)

- [ ] **Step 1: Add state** — in the component state object, near `selectedProfile`, add:

```js
        PERSONAS: [["professional","Professional"],["student","Student"],["maker","Maker"]], persona: "professional",
```

- [ ] **Step 2: Add the selector** — next to the profile selector in the input controls, add a labelled dropdown. Find the profile `<select>` (bound to `selectedProfile`) and add after its wrapper:

```html
          <label class="model-pick">Audience
            <select x-model="persona">
              <template x-for="p in PERSONAS" :key="p[0]"><option :value="p[0]" x-text="p[1]"></option></template>
            </select>
          </label>
```

- [ ] **Step 3: Send `persona` in the three request bodies**

In `runAuto()`'s `/api/run` body, add `persona: this.persona`:

```js
              body: JSON.stringify({ requirements_text: this.input, guidance: this.parseConstraints(), profile: this.selectedProfile, persona: this.persona })
```

In `loadStage()`'s `/api/step` body, add `persona: this.persona` (after `profile`):

```js
                profile: this.selectedProfile,
                persona: this.persona
```

In `generate()`'s `/api/generate` body, add `persona: this.persona`:

```js
              body: JSON.stringify({ requirements_text: this.input, result: this.result, architecture_svg: this.exportSvg, project_name: this.projectName.trim() || null, persona: this.persona })
```

- [ ] **Step 4: Result-header label** — add a small chip showing the audience near the result top. In the `<template x-if="result">` block, just under the guard-notice line, add:

```html
        <div class="status-chip" x-text="'Audience: ' + (PERSONAS.find(p => p[0]===persona)||[,'Professional'])[1]"></div>
```

- [ ] **Step 5: Verify in the browser**

Restart the mock dev server (Python changed in Tasks 1-4). Then:

```js
// preview_eval
(async () => {
  const d = Alpine.$data(document.querySelector('[x-data]'));
  // selector defaults to professional
  const def = d.persona;
  d.persona = "student";
  let sent = null; const orig = window.fetch;
  window.fetch = (u, o) => { if (u === "/api/run") sent = JSON.parse(o.body); return orig(u, o); };
  d.input = "24V sensor board"; d.auto = true; await d.runAuto(); window.fetch = orig;
  await new Promise(r => setTimeout(r, 400));
  const chip = [...document.querySelectorAll('.status-chip')].some(e => e.textContent.includes('Audience: Student'));
  return { defaultPersona: def, sentPersona: sent && sent.persona, chipShowsStudent: chip };
})()
```

Expected: `defaultPersona === "professional"`, `sentPersona === "student"`, `chipShowsStudent === true`. Check `preview_console_logs` (error) → none.

- [ ] **Step 6: Final suite + commit**

Run: `python -m pytest -q` → all green (expect ~221 passed).
`git add app/static/index.html && git commit -m "feat(ui): persona selector + Audience label"`

---

## Self-Review

**Spec coverage:**
- persona.py map + resolvers → Task 1. ✓
- persona on the three requests → Task 2. ✓
- prepend to guidance (/run, /step), persona to report (/generate) → Task 3. ✓
- report Audience label → Task 4. ✓
- selector default Professional + send in 3 bodies + result label → Task 5. ✓
- Live-only + visible label; Mock unchanged (guidance ignored by mock) → Tasks 3/5. ✓
- English-only → all strings English. ✓
- Graceful fallback (unknown/None → professional; no label when persona None in report) → Tasks 1/4. ✓

**Placeholder scan:** every step has concrete code/commands + expected output. The only "find the existing line" notes (profile select, report meta line) name the exact anchor to locate. ✓

**Type/name consistency:** `resolve_persona`/`persona_instruction`/`persona_label` used consistently; `persona` field name identical across schema, routes, report, UI; `PERSONA_INSTRUCTIONS`/`PERSONA_LABELS` keys (`professional`/`student`/`maker`) match the UI `PERSONAS` keys; `generate_report_pdf(..., persona=...)` matches the routes call and `_report_context(..., persona=...)`. ✓

**Nuance:** the report shows the label only when a persona is explicitly passed (`persona_label(persona) if persona else ""`), so legacy/programmatic report calls without a persona render no label; the GUI always sends one (default professional).
