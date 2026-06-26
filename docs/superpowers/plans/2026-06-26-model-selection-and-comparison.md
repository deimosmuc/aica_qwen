# Model Selection + Model Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user pick the Qwen model for the whole pipeline (UI dropdown), and parametrise the existing multi-vs-single comparison with a per-side model so the headline "multi-agent @ qwen-plus beats single-agent @ qwen-max" demo runs in one click — plus a few simple per-side metrics.

**Architecture:** Model choice is applied by copying `Settings` with a different `qwen_model` (`settings.model_copy(...)`) and letting the existing `Orchestrator`/`QwenClient`/stepwise code read it — no agent changes. A `Settings.resolve_model()` allowlist makes any unknown model degrade silently to the default. The comparison schema is extended **additively** (no reshape): existing `multi_*`/`single_*` fields stay, new model-name and metric fields are added. Every path keeps the existing per-side guard + mock fallback.

**Tech Stack:** Python, FastAPI, Pydantic v2 / pydantic-settings, Alpine.js, pytest.

Spec: `docs/superpowers/specs/2026-06-26-model-selection-and-comparison-design.md`

Run tests with the project venv: `.venv/Scripts/python.exe -m pytest`. Known unrelated pre-existing failures: 2 in `tests/test_milestone1.py` (local `.env` has a real `QWEN_API_KEY`, so the app reports `qwen` mode while those tests assert `mock`). Ignore them; everything else must stay green.

---

## File structure

- Modify `app/services/config.py` — add `qwen_models` allowlist + `resolve_model()`.
- Modify `app/models/schemas.py` — `RunRequest.model`, `StepRequest.model`, `CompareRequest.{multi_model,single_model}`, additive `Comparison` fields.
- Modify `app/services/comparison.py` — per-side model + simple metrics.
- Modify `app/api/routes.py` — thread model into `/run`, `/step`; per-side models into `/compare`.
- Modify `app/static/index.html` — model dropdown; compare preset buttons; render side models + metrics.
- Modify `tools/compare_report.py` — include side models + metrics in the report.
- Create `tests/test_config.py`; extend `tests/test_comparison.py`, `tests/test_compare_endpoint.py`; add a run-threading test (in a new `tests/test_run_endpoint.py`).

---

## Task 1: Config — model allowlist + `resolve_model`

**Files:**
- Modify: `app/services/config.py:19`
- Test: `tests/test_config.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
"""Model allowlist resolution on Settings."""
from app.services.config import Settings


def test_resolve_model_passes_through_allowed():
    s = Settings()
    assert s.resolve_model("qwen-max") == "qwen-max"
    assert s.resolve_model("qwen-turbo") == "qwen-turbo"


def test_resolve_model_falls_back_for_unknown_or_empty():
    s = Settings()
    assert s.resolve_model("gpt-4") == s.qwen_model
    assert s.resolve_model(None) == s.qwen_model
    assert s.resolve_model("") == s.qwen_model
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'resolve_model'`

- [ ] **Step 3: Add the allowlist field and resolver**

In `app/services/config.py`, find:

```python
    qwen_model: str = "qwen-plus"
```

Add directly after it:

```python
    # Curated, json_object-capable models the UI may select. "thinking" models
    # are excluded — they don't support json_object output, which the pipeline needs.
    qwen_models: list[str] = ["qwen-plus", "qwen-max", "qwen-turbo"]
```

Then add this method to the `Settings` class (e.g. just above the `mock_mode` property):

```python
    def resolve_model(self, requested: str | None) -> str:
        """Return the requested model if it is allow-listed, else the default.
        Unknown / empty / None all degrade silently to qwen_model (no error)."""
        return requested if requested in self.qwen_models else self.qwen_model
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/config.py tests/test_config.py
git commit -m "feat(model): allow-list of selectable Qwen models + resolve_model"
```

---

## Task 2: Thread `model` through `/run` and `/step`

**Files:**
- Modify: `app/models/schemas.py:16-20` (RunRequest), and `StepRequest`
- Modify: `app/api/routes.py:58-66` (/run), `:133-143` (/step)
- Test: `tests/test_run_endpoint.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_run_endpoint.py`:

```python
"""The /api/run endpoint threads an optional model override into the Orchestrator."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.services.mock import mock_run


def _fake_orch_capturing(captured):
    class FakeOrch:
        def __init__(self, settings):
            captured["model"] = settings.qwen_model

        def run(self, text, guidance=None):
            return mock_run(text)

    return FakeOrch


def test_run_applies_allowlisted_model(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "model": "qwen-max"})
    assert r.status_code == 200
    assert captured["model"] == "qwen-max"


def test_run_unknown_model_falls_back_to_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "model": "gpt-4"})
    assert r.status_code == 200
    assert captured["model"] == "qwen-plus"  # the default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_run_endpoint.py -v`
Expected: FAIL — currently `/run` ignores `model`, so `captured["model"]` is `qwen-plus` even for the `qwen-max` case (first test fails).

- [ ] **Step 3: Add `model` to the request schemas**

In `app/models/schemas.py`, in `class RunRequest`, after the `guidance` field add:

```python
    model: str | None = Field(
        default=None, description="Optional Qwen model override; ignored unless allow-listed."
    )
```

In `class StepRequest` (the stepwise request), after its `guidance` field add:

```python
    model: str | None = None
```

- [ ] **Step 4: Apply the model in the `/run` route**

In `app/api/routes.py`, replace the body of `run`:

```python
    settings = get_settings()
    return Orchestrator(settings).run(req.requirements_text, req.guidance)
```

with:

```python
    settings = get_settings()
    settings = settings.model_copy(update={"qwen_model": settings.resolve_model(req.model)})
    return Orchestrator(settings).run(req.requirements_text, req.guidance)
```

- [ ] **Step 5: Apply the model in the `/step` route**

In `app/api/routes.py`, replace the body of `step`:

```python
    try:
        return run_stage(req, get_settings())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

with:

```python
    settings = get_settings()
    settings = settings.model_copy(update={"qwen_model": settings.resolve_model(req.model)})
    try:
        return run_stage(req, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_run_endpoint.py -v`
Expected: PASS (both tests)

Run the broader suite: `.venv/Scripts/python.exe -m pytest -q`
Expected: green except the 2 known `test_milestone1.py` failures.

- [ ] **Step 7: Commit**

```bash
git add app/models/schemas.py app/api/routes.py tests/test_run_endpoint.py
git commit -m "feat(model): thread optional model override through /run and /step"
```

---

## Task 3: Comparison service — per-side model + simple metrics

**Files:**
- Modify: `app/models/schemas.py` (class `Comparison`)
- Modify: `app/services/comparison.py`
- Test: `tests/test_comparison.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_comparison.py`:

```python
def test_comparison_records_side_models():
    cmp = run_comparison(TEXT, _mock_settings(), single_model="qwen-max")
    assert cmp.multi_model == "qwen-plus"   # default
    assert cmp.single_model == "qwen-max"   # allow-listed, recorded for display


def test_comparison_unknown_side_model_falls_back_to_default():
    cmp = run_comparison(TEXT, _mock_settings(), single_model="gpt-4")
    assert cmp.single_model == "qwen-plus"


def test_comparison_simple_metrics_present():
    cmp = run_comparison(TEXT, _mock_settings())
    # Counts derived from existing output data — non-negative, and the multi
    # pipeline surfaces at least as many review findings as the single mock.
    assert cmp.multi_blocks > 0 and cmp.single_blocks > 0
    assert cmp.multi_findings >= cmp.single_findings
    assert cmp.multi_honesty >= 0 and cmp.single_honesty >= 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_comparison.py::test_comparison_records_side_models -v`
Expected: FAIL — `run_comparison` takes no `single_model`, and `Comparison` has no `single_model`/metric fields.

- [ ] **Step 3: Add the additive fields to `Comparison`**

In `app/models/schemas.py`, in `class Comparison`, add these fields (after `single_calls`):

```python
    # Per-side model + simple metrics (additive — existing fields unchanged).
    multi_model: str = "qwen-plus"
    single_model: str = "qwen-plus"
    multi_blocks: int = 0
    single_blocks: int = 0
    multi_findings: int = 0
    single_findings: int = 0
    multi_honesty: int = 0
    single_honesty: int = 0
```

- [ ] **Step 4: Add the metric helpers in `comparison.py`**

In `app/services/comparison.py`, after the existing `_flatten_baseline` function, add:

```python
def _multi_stats(r: RunResponse) -> tuple[int, int, int]:
    """blocks, review findings, honesty markers — from the multi-agent output."""
    blocks = len(r.architecture.blocks)
    findings = len(r.critique.warnings) + len(r.critique.risks) + len(r.critique.missing_blocks)
    honesty = len(r.arbitration.todo) + len(r.arbitration.human_review) + len(r.arbitration.accepted_assumptions)
    return blocks, findings, honesty


def _single_stats(b: BaselineResult) -> tuple[int, int, int]:
    """blocks, review findings, honesty markers — from the single-agent output."""
    blocks = len(b.architecture)
    findings = len(b.concerns)
    honesty = len(b.todos) + len(b.human_review) + len(b.assumptions)
    return blocks, findings, honesty
```

- [ ] **Step 5: Parametrise `run_comparison` with per-side models**

In `app/services/comparison.py`, replace the whole `run_comparison` function with:

```python
def run_comparison(
    requirements_text: str,
    settings: Settings,
    multi_model: str | None = None,
    single_model: str | None = None,
) -> Comparison:
    multi_name = settings.resolve_model(multi_model)
    single_name = settings.resolve_model(single_model)

    multi = Orchestrator(settings.model_copy(update={"qwen_model": multi_name})).run(requirements_text)
    notice = multi.notice

    if settings.mock_mode:
        baseline = mock_baseline()
        single_calls = 0
        notice = notice or _MOCK_NOTICE
    else:
        try:
            single_settings = settings.model_copy(update={"qwen_model": single_name})
            baseline = SingleAgentBaseline().run(QwenClient(single_settings), requirements_text)
            single_calls = 1
        except (GuardBlocked, QwenError) as e:
            baseline = mock_baseline()
            single_calls = 0
            notice = (f"{notice} " if notice else "") + (
                f"Single-agent side ({single_name}) fell back to example data ({e})."
            )

    multi_scores = score(_flatten_multi(multi))
    single_scores = score(_flatten_baseline(baseline))
    concerns = [
        ConcernResult(
            id=c.id,
            label=c.label,
            covered_multi=multi_scores[c.id],
            covered_single=single_scores[c.id],
        )
        for c in RUBRIC
    ]
    multi_score = sum(multi_scores.values())
    single_score = sum(single_scores.values())
    mb, mf, mh = _multi_stats(multi)
    sb, sf, sh = _single_stats(baseline)

    return Comparison(
        requirements_text=requirements_text,
        mode=multi.mode,
        concerns=concerns,
        multi_score=multi_score,
        single_score=single_score,
        total=len(RUBRIC),
        delta=multi_score - single_score,
        multi_calls=len(multi.trace),
        single_calls=single_calls,
        multi_output=multi,
        single_output=baseline,
        notice=notice,
        multi_model=multi_name,
        single_model=single_name,
        multi_blocks=mb,
        single_blocks=sb,
        multi_findings=mf,
        single_findings=sf,
        multi_honesty=mh,
        single_honesty=sh,
    )
```

- [ ] **Step 6: Run the comparison tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_comparison.py -v`
Expected: PASS — the 3 new tests and the 4 pre-existing ones (including `test_guard_blocked_baseline_falls_back_with_notice`, which still finds "budget cap reached" in the notice).

- [ ] **Step 7: Commit**

```bash
git add app/models/schemas.py app/services/comparison.py tests/test_comparison.py
git commit -m "feat(model): per-side model + simple metrics in the comparison"
```

---

## Task 4: `/compare` route — accept per-side models

**Files:**
- Modify: `app/models/schemas.py` (class `CompareRequest`)
- Modify: `app/api/routes.py:126-130`
- Test: `tests/test_compare_endpoint.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_compare_endpoint.py`:

```python
def test_compare_endpoint_accepts_side_model(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))
    client = TestClient(app)
    resp = client.post(
        "/api/compare",
        json={"requirements_text": "A 24V STM32 board with RS485.", "single_model": "qwen-max"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["single_model"] == "qwen-max"
    assert data["multi_model"] == "qwen-plus"
    assert "multi_findings" in data and "single_findings" in data
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_compare_endpoint.py::test_compare_endpoint_accepts_side_model -v`
Expected: FAIL — `CompareRequest` rejects/ignores `single_model` and the route doesn't pass it.

- [ ] **Step 3: Add the fields to `CompareRequest`**

In `app/models/schemas.py`, in `class CompareRequest`, after `requirements_text` add:

```python
    multi_model: str | None = None
    single_model: str | None = None
```

- [ ] **Step 4: Pass them through the route**

In `app/api/routes.py`, replace the `compare` body:

```python
    return run_comparison(req.requirements_text, get_settings())
```

with:

```python
    return run_comparison(
        req.requirements_text, get_settings(), req.multi_model, req.single_model
    )
```

- [ ] **Step 5: Run the endpoint tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_compare_endpoint.py -v`
Expected: PASS (new test + the pre-existing `test_compare_endpoint_mock`).

- [ ] **Step 6: Commit**

```bash
git add app/models/schemas.py app/api/routes.py tests/test_compare_endpoint.py
git commit -m "feat(model): /compare accepts per-side model overrides"
```

---

## Task 5: UI — model dropdown wired into run/step

**Files:**
- Modify: `app/static/index.html` (state at ~line 500-505; input row ~155-161; fetch bodies ~527 and ~546-553)

Frontend-only; verified by suite-green + visual check.

- [ ] **Step 1: Add `selectedModel` + `MODELS` to the Alpine state**

In `app/static/index.html`, find:

```javascript
        diagramSvg: null, constraintsText: "", correctText: "",
```

Replace with:

```javascript
        diagramSvg: null, constraintsText: "", correctText: "",
        MODELS: ["qwen-plus", "qwen-max", "qwen-turbo"], selectedModel: "qwen-plus",
```

- [ ] **Step 2: Add the dropdown to the input row**

In `app/static/index.html`, find the input `<div class="row">` block and the closing `</div>` after the "Load example" button (around line 160). Add this `<label>` immediately before that closing `</div>`:

```html
        <label class="model-pick">Model:
          <select x-model="selectedModel" :disabled="loading || stepBusy || comparing">
            <template x-for="m in MODELS" :key="m"><option :value="m" x-text="m"></option></template>
          </select>
        </label>
```

- [ ] **Step 3: Send the model in the auto-run fetch**

In `runAuto`, find:

```javascript
              body: JSON.stringify({ requirements_text: this.input, guidance: this.parseConstraints() })
```

Replace with:

```javascript
              body: JSON.stringify({ requirements_text: this.input, guidance: this.parseConstraints(), model: this.selectedModel })
```

- [ ] **Step 4: Send the model in the step fetch**

In `loadStage`, find the `body: JSON.stringify({` block with `stage: this.STAGES[i]` and add `model: this.selectedModel` to it, so it reads:

```javascript
              body: JSON.stringify({
                stage: this.STAGES[i],
                requirements_text: this.input,
                guidance: this.acc.guidance,
                requirements: this.acc.requirements,
                architecture: this.acc.architecture,
                critique: this.acc.critique,
                model: this.selectedModel
              })
```

- [ ] **Step 5: Verify**

Run: `.venv/Scripts/python.exe -m pytest -q` (HTML change; suite unaffected apart from the 2 known failures).
Static check: confirm `selectedModel` appears in the `<select>`, in `runAuto`'s body, and in `loadStage`'s body.
If a dev server is trivial to start, load the page and confirm the dropdown renders with three options and a run still works; otherwise rely on the static check.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "feat(model): UI model dropdown wired into run and step"
```

---

## Task 6: UI — compare presets + render side models/metrics

**Files:**
- Modify: `app/static/index.html` (compare button ~158-159; cmp panel ~177-186; `compareRun` ~602-615)

- [ ] **Step 1: Replace the single compare button with two presets**

In `app/static/index.html`, find:

```html
        <button @click="compareRun()" :disabled="comparing || !input.trim()"
          x-text="comparing ? 'Comparing…' : 'Compare: multi vs single agent'"></button>
```

Replace with:

```html
        <button @click="compareRun()" :disabled="comparing || !input.trim()"
          x-text="comparing ? 'Comparing…' : 'Compare: fair (same model)'"></button>
        <button @click="compareRun({ single_model: 'qwen-max' })" :disabled="comparing || !input.trim()"
          :title="'Multi-agent @ qwen-plus vs single-agent @ qwen-max'"
          x-text="comparing ? 'Comparing…' : '🏆 Architecture beats tier'"></button>
```

- [ ] **Step 2: Accept preset options in `compareRun`**

In `app/static/index.html`, replace:

```javascript
        async compareRun() {
          this.comparing = true; this.cmp = null; this.cmpError = "";
          try {
            const res = await fetch("/api/compare", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ requirements_text: this.input })
            });
```

with:

```javascript
        async compareRun(opts = {}) {
          this.comparing = true; this.cmp = null; this.cmpError = "";
          try {
            const res = await fetch("/api/compare", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ requirements_text: this.input, ...opts })
            });
```

- [ ] **Step 3: Show the side model names and metrics in the cmp panel**

In `app/static/index.html`, replace the score block:

```html
          <div><div class="muted">Multi-agent</div>
            <div class="cmp-score" x-text="cmp.multi_score"></div><span class="of" x-text="'/ ' + cmp.total"></span></div>
          <div><div class="muted">Single-agent</div>
            <div class="cmp-score" x-text="cmp.single_score"></div><span class="of" x-text="'/ ' + cmp.total"></span></div>
```

with:

```html
          <div><div class="muted" x-text="'Multi-agent · ' + cmp.multi_model"></div>
            <div class="cmp-score" x-text="cmp.multi_score"></div><span class="of" x-text="'/ ' + cmp.total"></span>
            <div class="muted" x-text="cmp.multi_blocks + ' blocks · ' + cmp.multi_findings + ' findings · ' + cmp.multi_honesty + ' honesty'"></div></div>
          <div><div class="muted" x-text="'Single-agent · ' + cmp.single_model"></div>
            <div class="cmp-score" x-text="cmp.single_score"></div><span class="of" x-text="'/ ' + cmp.total"></span>
            <div class="muted" x-text="cmp.single_blocks + ' blocks · ' + cmp.single_findings + ' findings · ' + cmp.single_honesty + ' honesty'"></div></div>
```

- [ ] **Step 4: Verify**

Run: `.venv/Scripts/python.exe -m pytest -q` (suite unaffected apart from the 2 known failures).
Static check: confirm two compare buttons exist, `compareRun(opts = {})` accepts options, and the cmp panel references `cmp.multi_model` / `cmp.multi_findings`.
If a dev server is trivial to start, run both compare presets and confirm the side headers show the model names and the metrics line; otherwise rely on the static check.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat(model): compare presets + per-side model/metrics in the UI"
```

---

## Task 7: Report tool — include side models + metrics

**Files:**
- Modify: `tools/compare_report.py:31-45`

- [ ] **Step 1: Update the Markdown summary lines**

In `tools/compare_report.py`, in `_to_markdown`, replace:

```python
        f"**Multi-agent: {cmp.multi_score}/{cmp.total} concerns surfaced "
        f"({cmp.multi_calls} agent call{'s' if cmp.multi_calls != 1 else ''}).**",
        f"**Single-agent: {cmp.single_score}/{cmp.total} concerns surfaced "
        f"({cmp.single_calls} call{'s' if cmp.single_calls != 1 else ''}).**",
```

with:

```python
        f"**Multi-agent @ {cmp.multi_model}: {cmp.multi_score}/{cmp.total} concerns surfaced "
        f"({cmp.multi_calls} agent call{'s' if cmp.multi_calls != 1 else ''}; "
        f"{cmp.multi_blocks} blocks, {cmp.multi_findings} findings, {cmp.multi_honesty} honesty markers).**",
        f"**Single-agent @ {cmp.single_model}: {cmp.single_score}/{cmp.total} concerns surfaced "
        f"({cmp.single_calls} call{'s' if cmp.single_calls != 1 else ''}; "
        f"{cmp.single_blocks} blocks, {cmp.single_findings} findings, {cmp.single_honesty} honesty markers).**",
```

- [ ] **Step 2: Verify the report still generates**

Run: `.venv/Scripts/python.exe tools/compare_report.py "A 24V STM32 board with RS485." outputs/_cmp_check.md`
Expected: prints the score line and "report written to …"; the generated file contains "Multi-agent @ qwen-plus" and the metrics. (This runs live if a key is present — that's fine and cheap; it falls back to illustrative otherwise.)
Then remove the check file: `rm outputs/_cmp_check.md`

- [ ] **Step 3: Commit**

```bash
git add tools/compare_report.py
git commit -m "feat(model): include side models + metrics in the comparison report"
```

---

## Final verification

- [ ] Run the full suite: `.venv/Scripts/python.exe -m pytest -q` — all pass except the 2 known `test_milestone1.py` mock-mode failures.
- [ ] Manually (if a dev server is up): pick qwen-max in the dropdown and run; run both compare presets and confirm the "Architecture beats tier" preset shows Multi-agent @ qwen-plus vs Single-agent @ qwen-max with scores + metrics. If a model isn't accessible on the key, confirm the single side falls back with an honest notice rather than crashing.
- [ ] Confirm no new unqualified "production-ready" claim was introduced.
