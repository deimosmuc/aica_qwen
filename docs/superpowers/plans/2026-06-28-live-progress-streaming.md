# Live Progress Streaming (Auto Mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Auto-mode pipeline stream each agent's result to the browser as it finishes, so the Mission-Control rail and Agent-Society chat run live during a real run instead of showing a spinner then replaying finished work.

**Architecture:** The `Orchestrator` gains a `run_stream()` generator that `yield`s a `StreamEvent` after every agent completes and a final event with the full `RunResponse`. The blocking `run()` is re-implemented by draining that generator, so all existing callers and tests are unchanged. A new `POST /api/run/stream` route serializes events as Server-Sent Events (SSE), pulling the sync generator off the event loop via `anyio.to_thread`. The frontend reads the stream with `fetch` + a `ReadableStream` reader, pushing each step into a live trace that drives the rail and chat in real time. Two small UI fixes ride along: the PCB Critic renders on the right (antagonist side), and a header chip signals "agents working".

**Tech Stack:** Python 3.12, FastAPI / Starlette, Pydantic v2, pytest, Alpine.js (vanilla, in `app/static/index.html`).

---

## File Structure

- `app/models/schemas.py` — **Modify.** Add `StreamEvent` model.
- `app/services/orchestrator.py` — **Modify.** Add `run_stream()` generator + streaming helpers; re-implement `run()` as a drainer; remove the now-unused non-streaming helpers.
- `app/api/routes.py` — **Modify.** Add `POST /api/run/stream` SSE endpoint.
- `app/static/index.html` — **Modify.** Stream consumption in `runAuto()`, live trace state, header chip, remove fake replay, PCB Critic on the right.
- `tests/test_orchestrator_stream.py` — **Create.** Event-sequence tests for `run_stream()`.
- `tests/test_run_stream_endpoint.py` — **Create.** SSE route tests.

---

## Task 1: `StreamEvent` schema

**Files:**
- Modify: `app/models/schemas.py` (after the `RunResponse` class, ~line 265)
- Test: `tests/test_orchestrator_stream.py` (created in Task 2 — no test in this task)

- [ ] **Step 1: Add the `StreamEvent` model**

In `app/models/schemas.py`, immediately after the `RunResponse` class (which ends around line 264 with `pcb_readiness: PcbReadiness | None = None`), add:

```python
# --- Streaming pipeline events (live auto-mode progress) ---------------------


class StreamEvent(BaseModel):
    """One server-sent event from the streaming pipeline.

    `stage` fires as each agent finishes, carrying just that agent's TraceStep
    (the live rail + Society chat need nothing more). `final` carries the
    complete RunResponse the non-streaming path returns today. `error` carries
    the same honest notice used by the blocking fallback and is always followed
    by a `final` event whose result is the example-data fallback.
    """

    type: Literal["stage", "final", "error"]
    step: TraceStep | None = None
    result: RunResponse | None = None
    notice: str | None = None
```

`Literal` and `BaseModel` are already imported at the top of the file (lines 8 and 10) — no new imports.

- [ ] **Step 2: Verify it imports**

Run: `./.venv/Scripts/python.exe -c "from app.models.schemas import StreamEvent; print(StreamEvent(type='stage').type)"`
Expected: prints `stage`

- [ ] **Step 3: Commit**

```bash
git add app/models/schemas.py
git commit -m "feat(schemas): add StreamEvent for live pipeline streaming"
```

---

## Task 2: `Orchestrator.run_stream()` generator + `run()` drainer

**Files:**
- Modify: `app/services/orchestrator.py`
- Test: `tests/test_orchestrator_stream.py`

This refactor converts the two design/review helpers into generators that `yield` a `StreamEvent` per finished step and `return` their results (PEP 380 `yield from`). `run_stream()` orchestrates them; `run()` drains `run_stream()` and returns the `final` result. Behaviour (call counts, rounds, fallbacks) is preserved exactly, so the existing `tests/test_orchestrator.py` keeps passing.

- [ ] **Step 1: Write the failing test**

Create `tests/test_orchestrator_stream.py`:

```python
"""Orchestrator.run_stream(): event ordering, rework, error fallback."""
import app.services.orchestrator as orch_mod
from app.models.schemas import (
    Arbitration, Architecture, Block, Critique, PcbCritique, PcbReadiness,
    Requirements, RunResponse, StreamEvent,
)
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.profiles import PROFILES, RunProfile

_ALL_ROLES = ("requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critique")


def _rework_profile(rounds=2):
    return RunProfile(name="t", models={r: "qwen-plus" for r in _ALL_ROLES},
                      rework=True, max_rounds=rounds)


def _stub_pcb_readiness() -> PcbReadiness:
    from app.models.schemas import ConstraintSet, NetClass
    return PcbReadiness(
        layerstack="2-layer", layerstack_reason="simple board",
        netclasses=[NetClass(name="Default", min_width_mm=0.2, clearance_mm=0.2)],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                  via_drill_mm=0.4, via_annular_ring_mm=0.15),
        floorplan_text="MCU central.", floorplan_ascii="[MCU]", package_hints=[],
    )


def _patch_agents(monkeypatch, critic_fn, calls):
    monkeypatch.setattr(orch_mod.RequirementsAgent, "run",
                        lambda self, c, text, g=None: Requirements(requirements=["r"], confidence=0.5))

    def arch(self, c, requirements, g=None):
        calls["arch"] += 1
        return Architecture(blocks=[Block(name="MCU", sheet="mcu.kicad_sch", purpose="core")])

    def crit(self, c, requirements, architecture, g=None):
        calls["crit"] += 1
        return critic_fn(calls["crit"])

    monkeypatch.setattr(orch_mod.SystemArchitectAgent, "run", arch)
    monkeypatch.setattr(orch_mod.DesignCriticAgent, "run", crit)
    monkeypatch.setattr(orch_mod.ArbitrationAgent, "run",
                        lambda self, c, req, arch, crit, g=None: Arbitration(approved_architecture=arch))
    monkeypatch.setattr(orch_mod.PcbEngineerAgent, "run",
                        lambda self, c, req, arch, arb, g=None: _stub_pcb_readiness())
    monkeypatch.setattr(orch_mod.PcbCriticAgent, "run",
                        lambda self, c, req, pcb, g=None: PcbCritique())


def test_stream_emits_stage_events_then_final(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(), calls)
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"),
                                        profile=PROFILES["Uniform qwen-plus"]).run_stream("board"))
    assert all(isinstance(e, StreamEvent) for e in events)
    stage = [e for e in events if e.type == "stage"]
    final = [e for e in events if e.type == "final"]
    assert len(stage) == 6                      # one per agent, no rework
    assert all(e.step is not None for e in stage)
    assert len(final) == 1 and final[-1] is events[-1]   # final is last
    assert isinstance(final[0].result, RunResponse)
    # the final trace equals the streamed steps, in order
    assert [e.step.agent for e in stage] == [s.agent for s in final[0].result.trace]


def test_stream_rework_emits_round_two_steps(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["DUMMY_CLOCK"]) if n == 1 else Critique(), calls)
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"),
                                        profile=_rework_profile()).run_stream("board"))
    stage = [e for e in events if e.type == "stage"]
    assert any(e.step.round == 2 for e in stage)         # rework streamed live
    assert calls["arch"] == 2 and calls["crit"] == 2


def test_stream_error_yields_error_then_mock_final(monkeypatch):
    def boom(self, c, text, g=None):
        raise GuardBlocked("budget cap")
    monkeypatch.setattr(orch_mod.RequirementsAgent, "run", boom)
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="sk-test")).run_stream("board"))
    assert any(e.type == "error" and "budget cap" in (e.notice or "") for e in events)
    final = [e for e in events if e.type == "final"]
    assert len(final) == 1 and final[0].result.mode == "mock"


def test_run_still_returns_final_result(monkeypatch):
    # The blocking run() is now a drainer over run_stream(); behaviour unchanged.
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(), calls)
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"),
                                profile=PROFILES["Uniform qwen-plus"]).run("board")
    assert isinstance(out, RunResponse)
    assert len(out.trace) == 6


def test_stream_mock_mode_emits_steps_and_final():
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="")).run_stream("a 24V board"))
    stage = [e for e in events if e.type == "stage"]
    final = [e for e in events if e.type == "final"]
    assert len(stage) == len(final[0].result.trace) == 6
    assert final[0].result.mode == "mock"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_orchestrator_stream.py -q`
Expected: FAIL — `AttributeError: 'Orchestrator' object has no attribute 'run_stream'`

- [ ] **Step 3: Refactor the orchestrator**

In `app/services/orchestrator.py`:

(a) Add the import for `StreamEvent` to the existing schemas import (the line starting `from app.models.schemas import ...`, ~line 21):

```python
from app.models.schemas import (
    Arbitration, Architecture, Critique, PcbCritique, PcbReadiness, Requirements,
    RunResponse, StreamEvent, TraceStep,
)
```
(Note: `Arbitration` is referenced by the existing `_pcb_design_and_review` type hint but is currently NOT imported — this import line fixes that latent gap too.)

(b) Replace the two helpers `_pcb_design_and_review` (lines ~109-139) and `_design_and_review` (lines ~141-175) with streaming versions that yield a `StreamEvent` per step and return their results:

```python
    def _design_and_review_stream(self, requirements: Requirements, guidance: list[str]):
        """Design + review with optional Critic->Architect rework. Yields one
        StreamEvent per finished step; returns (architecture, critique, steps)."""
        steps: list[TraceStep] = []
        t = perf_counter()
        architecture = SystemArchitectAgent().run(self._client_for("architecture"), requirements, guidance)
        step = self._arch_step(architecture, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)
        t = perf_counter()
        critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, guidance)
        step = self._critic_step(critique, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)

        round_no = 1
        while self.profile.rework and critique.missing_blocks and round_no < self.profile.max_rounds:
            round_no += 1
            rework_guidance = guidance + [
                "Revise the architecture to address these review findings:",
                *critique.missing_blocks,
                *critique.recommendations,
            ]
            t = perf_counter()
            architecture = SystemArchitectAgent().run(self._client_for("architecture"), requirements, rework_guidance)
            step = self._arch_step(architecture, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)
            t = perf_counter()
            critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, rework_guidance)
            step = self._critic_step(critique, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)

        return architecture, critique, steps

    def _pcb_design_and_review_stream(self, requirements, architecture, arbitration, guidance: list[str]):
        """PCB Engineer + PCB Critic rework loop. Yields one StreamEvent per
        finished step; returns (pcb, pcb_critique, steps)."""
        steps: list[TraceStep] = []
        t = perf_counter()
        pcb = PcbEngineerAgent().run(self._client_for("pcb_engineer"), requirements, architecture, arbitration, guidance)
        step = self._pcb_step(pcb, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)
        t = perf_counter()
        pcb_critique = PcbCriticAgent().run(self._client_for("pcb_critique"), requirements, pcb, guidance)
        step = self._pcb_critic_step(pcb_critique, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)

        round_no = 1
        while self.profile.rework and pcb_critique.missing_blocks and round_no < self.profile.max_rounds:
            round_no += 1
            rework_guidance = guidance + [
                "Revise the PCB recommendations to address these review findings:",
                *pcb_critique.missing_blocks,
            ]
            t = perf_counter()
            pcb = PcbEngineerAgent().run(self._client_for("pcb_engineer"), requirements, architecture, arbitration, rework_guidance)
            step = self._pcb_step(pcb, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)
            t = perf_counter()
            pcb_critique = PcbCriticAgent().run(self._client_for("pcb_critique"), requirements, pcb, rework_guidance)
            step = self._pcb_critic_step(pcb_critique, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)

        return pcb, pcb_critique, steps
```

(c) Replace the existing `run()` method (lines ~177-252) with a streaming generator `run_stream()` plus a thin draining `run()`:

```python
    def run_stream(self, requirements_text: str, guidance: list[str] | None = None):
        """Stream the pipeline: one `stage` StreamEvent per finished agent, then
        a single `final` event with the full RunResponse. On a guard/Qwen/
        validation failure, emit an `error` event then a `final` with the
        example-data fallback (same honest degradation as the blocking path)."""
        self._meter = RunMeter()
        if self.settings.mock_mode:
            result = mock_run_rework(requirements_text) if self.profile.rework else mock_run(requirements_text)
            for step in result.trace:
                yield StreamEvent(type="stage", step=step)
            yield StreamEvent(type="final", result=result)
            return

        guidance = guidance or []
        steps: list[TraceStep] = []
        try:
            t = perf_counter()
            requirements = RequirementsAgent().run(self._client_for("requirements"), requirements_text, guidance)
            req_step = TraceStep(
                agent=RequirementsAgent.name, role=RequirementsAgent.role, status="ok",
                duration_ms=int((perf_counter() - t) * 1000),
                summary=(
                    f"Live Qwen: structured {len(requirements.requirements)} requirements, "
                    f"raised {len(requirements.questions)} clarification questions "
                    f"(confidence {requirements.confidence:.0%})."
                ),
            )
            steps.append(req_step); yield StreamEvent(type="stage", step=req_step)

            architecture, critique, design_steps = yield from self._design_and_review_stream(requirements, guidance)
            steps.extend(design_steps)

            t = perf_counter()
            arbitration = ArbitrationAgent().run(self._client_for("arbitration"), requirements, architecture, critique, guidance)
            arb_step = TraceStep(
                agent=ArbitrationAgent.name, role=ArbitrationAgent.role, status="ok",
                duration_ms=int((perf_counter() - t) * 1000),
                summary=(
                    f"Live Qwen: approved the architecture; logged {len(arbitration.todo)} TODOs "
                    f"and {len(arbitration.human_review)} human-review items."
                ),
            )
            steps.append(arb_step); yield StreamEvent(type="stage", step=arb_step)

            pcb, pcb_critique, pcb_steps = yield from self._pcb_design_and_review_stream(
                requirements, architecture, arbitration, guidance)
            steps.extend(pcb_steps)
        except GuardBlocked as e:
            yield from self._error_then_fallback(
                requirements_text, f"API limit reached ({e.reason}). Showing example data instead — no charge.")
            return
        except QwenTruncatedError as e:
            yield from self._error_then_fallback(
                requirements_text,
                f"Qwen's answer was cut off ({e}). Showing example data instead — "
                "try a simpler request or raise GUARD_MAX_OUTPUT_TOKENS.")
            return
        except QwenError as e:
            yield from self._error_then_fallback(
                requirements_text, f"Qwen was unreachable ({e}). Showing example data instead.")
            return
        except ValidationError as e:
            yield from self._error_then_fallback(
                requirements_text,
                f"Qwen returned a malformed answer ({e.error_count()} field error(s)). "
                "Showing example data instead.")
            return

        result = RunResponse(
            mode="qwen", requirements=requirements, architecture=architecture,
            critique=critique, arbitration=arbitration, pcb_readiness=pcb,
            trace=steps, needs_approval=True, usage=self._meter.snapshot(),
        )
        yield StreamEvent(type="final", result=result)

    def _error_then_fallback(self, requirements_text: str, notice: str):
        result = mock_run(requirements_text)
        result.notice = notice
        yield StreamEvent(type="error", notice=notice)
        yield StreamEvent(type="final", result=result)

    def run(self, requirements_text: str, guidance: list[str] | None = None) -> RunResponse:
        """Blocking pipeline — drains run_stream() and returns the final result.
        Kept for /api/run, comparison, bench and the existing test-suite."""
        result: RunResponse | None = None
        for event in self.run_stream(requirements_text, guidance):
            if event.type == "final":
                result = event.result
        assert result is not None  # run_stream always ends with a final event
        return result
```

(d) Delete the now-unused `_guarded_fallback` method (the old lines ~254-257) — `_error_then_fallback` replaces it. Confirm nothing else references `_guarded_fallback`:

Run: `./.venv/Scripts/python.exe -c "import re,io; s=open('app/services/orchestrator.py').read(); print('refs:', s.count('_guarded_fallback'))"`
Expected: prints `refs: 0`

- [ ] **Step 4: Run the new tests + the existing orchestrator tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_orchestrator_stream.py tests/test_orchestrator.py tests/test_orchestrator_pcb.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add app/services/orchestrator.py tests/test_orchestrator_stream.py
git commit -m "feat(orchestrator): run_stream() generator; run() drains it"
```

---

## Task 3: `POST /api/run/stream` SSE endpoint

**Files:**
- Modify: `app/api/routes.py`
- Test: `tests/test_run_stream_endpoint.py`

The route serializes each `StreamEvent` as an SSE `data:` frame. The orchestrator generator is synchronous and does blocking Qwen I/O, so we pull items off the event loop with `anyio.to_thread.run_sync` (anyio ships with FastAPI; this avoids stalling other requests like `/api/guard`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_run_stream_endpoint.py`:

```python
"""POST /api/run/stream emits SSE events ending in a final RunResponse."""
import json

from fastapi.testclient import TestClient

from app.main import app


def _parse_sse(body: str):
    events = []
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_run_stream_mock_mode_streams_steps_then_final():
    # No QWEN_API_KEY in the test env -> deterministic mock pipeline.
    client = TestClient(app)
    r = client.post("/api/run/stream", json={"requirements_text": "a 24V sensor board"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.text)
    stage = [e for e in events if e["type"] == "stage"]
    final = [e for e in events if e["type"] == "final"]
    assert len(stage) >= 6
    assert len(final) == 1 and events[-1]["type"] == "final"
    assert len(stage) == len(final[0]["result"]["trace"])
    assert final[0]["result"]["mode"] == "mock"
    assert stage[0]["step"]["agent"]   # each stage carries a TraceStep


def test_run_stream_respects_named_profile(monkeypatch):
    captured = {}
    import app.api.routes as routes
    from app.models.schemas import RunResponse, StreamEvent
    from app.services.mock import mock_run

    class FakeOrch:
        def __init__(self, settings, profile=None, client=None):
            captured["profile"] = profile

        def run_stream(self, text, guidance=None):
            yield StreamEvent(type="final", result=mock_run(text))

    monkeypatch.setattr(routes, "Orchestrator", FakeOrch)
    client = TestClient(app)
    r = client.post("/api/run/stream", json={"requirements_text": "x", "profile": "Senior Review Team"})
    assert r.status_code == 200
    assert captured["profile"].rework is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_stream_endpoint.py -q`
Expected: FAIL — 404 (route not defined) on the first test

- [ ] **Step 3: Add the route**

In `app/api/routes.py`, add these imports near the top (after the existing `from fastapi.responses import FileResponse` line, ~line 15):

```python
import anyio
from fastapi.responses import StreamingResponse
```

Then add the endpoint immediately after the existing `run()` function (which ends ~line 89):

```python
@router.post("/run/stream")
async def run_stream(req: RunRequest) -> StreamingResponse:
    """Server-Sent Events version of /api/run: emit one `stage` event per
    finished agent, then a `final` event with the full result. Lets the UI show
    real live progress instead of a spinner for the whole multi-minute run."""
    settings = get_settings()
    profile = profile_for(req.profile, req.model, settings)
    guidance = [persona_instruction(req.persona)] + req.guidance
    orch = Orchestrator(settings, profile)

    async def event_source():
        gen = orch.run_stream(req.requirements_text, guidance)
        done = object()

        def _next():
            try:
                return next(gen)
            except StopIteration:
                return done

        while True:
            event = await anyio.to_thread.run_sync(_next)
            if event is done:
                break
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

`Orchestrator`, `profile_for`, `persona_instruction`, `get_settings` and `RunRequest` are already imported in this module.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_stream_endpoint.py -q`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add app/api/routes.py tests/test_run_stream_endpoint.py
git commit -m "feat(api): POST /api/run/stream SSE endpoint"
```

---

## Task 4: Frontend — consume the stream, live rail, header chip

**Files:**
- Modify: `app/static/index.html`

No automated test (vanilla Alpine in a single HTML file); verified live in Task 6. Each edit below quotes the exact current text to replace.

- [ ] **Step 1: Add live-stream state fields**

In the `architect()` return object, find the line (~877):

```javascript
        playedSteps: 0, societyTab: 'trace', _pipelineTimers: [],
```

Replace it with:

```javascript
        playedSteps: 0, societyTab: 'trace', _pipelineTimers: [],
        streamTrace: [], streamActive: false, streamStageLabel: "", streamNotice: "",
```

- [ ] **Step 2: Include the live trace in `pipelineTrace()`**

Find (~972):

```javascript
        pipelineTrace() {
          return (this.result && this.result.trace) || (this.acc && this.acc.trace) || [];
        },
```

Replace with:

```javascript
        pipelineTrace() {
          return (this.result && this.result.trace) || (this.acc && this.acc.trace)
                 || (this.streamTrace.length ? this.streamTrace : []);
        },
```

- [ ] **Step 3: Reset stream state on a new run**

Find the `_resetRun()` body (~900-906). Find the line:

```javascript
          this.playedSteps = 0; this.societyTab = 'trace';
```

Replace with:

```javascript
          this.playedSteps = 0; this.societyTab = 'trace';
          this.streamTrace = []; this.streamActive = false; this.streamStageLabel = ""; this.streamNotice = "";
```

- [ ] **Step 4: Rewrite `runAuto()` to read the SSE stream**

Find the whole current `runAuto()` (~907-921):

```javascript
        async runAuto() {
          this._resetRun(); this.loading = true;
          try {
            const res = await fetch("/api/run", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ requirements_text: this.input, guidance: this.parseConstraints(), profile: this.selectedProfile, persona: this.persona })
            });
            this.result = await res.json();
            this.mode = this.result.mode;
            this.diagramSvg = await this.buildDiagram(this.result.architecture);
            this.exportSvg = await this.buildExportDiagram(this.result.architecture);
            await this.fetchGuard();
            this.playPipeline();
          } finally { this.loading = false; }
        },
```

Replace with:

```javascript
        async runAuto() {
          this._resetRun(); this.loading = true; this.streamActive = true;
          try {
            const res = await fetch("/api/run/stream", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ requirements_text: this.input, guidance: this.parseConstraints(), profile: this.selectedProfile, persona: this.persona })
            });
            if (!res.ok || !res.body) throw new Error("Stream failed (" + res.status + ")");
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buf = "";
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              buf += decoder.decode(value, { stream: true });
              let i;
              while ((i = buf.indexOf("\n\n")) >= 0) {
                const frame = buf.slice(0, i); buf = buf.slice(i + 2);
                const line = frame.split("\n").find(l => l.startsWith("data:"));
                if (line) this.handleStreamEvent(JSON.parse(line.slice(5).trim()));
              }
            }
          } catch (e) {
            this.streamNotice = "⚠️ " + e.message;
          } finally {
            this.streamActive = false; this.loading = false;
          }
        },
        async handleStreamEvent(ev) {
          if (ev.type === "stage") {
            this.streamTrace.push(ev.step);
            this.playedSteps = this.streamTrace.length;
            this.streamStageLabel = ev.step.agent;
          } else if (ev.type === "error") {
            this.streamNotice = "⚠️ " + (ev.notice || "");
          } else if (ev.type === "final") {
            this.result = ev.result;
            this.mode = ev.result.mode;
            this.playedSteps = ev.result.trace.length;
            this.streamStageLabel = "";
            this.diagramSvg = await this.buildDiagram(this.result.architecture);
            this.exportSvg = await this.buildExportDiagram(this.result.architecture);
            await this.fetchGuard();
          }
        },
```

- [ ] **Step 5: Remove the now-unused fake-replay `playPipeline()`**

Find and delete the entire `playPipeline()` method (~1034-1042):

```javascript
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

(Leave `_pipelineTimers` and its clearing in `_resetRun()` in place — harmless, and still referenced there.)

- [ ] **Step 6: Keep the rail "LIVE" while streaming**

In `railView()`, find (~989):

```javascript
          const settled = total > 0 && this.playedSteps >= total;
```

Replace with:

```javascript
          const settled = total > 0 && this.playedSteps >= total && !this.streamActive;
```

Then find the `return { ... active: ... }` at the end of `railView()` (~1026-1029):

```javascript
          return { stations, fillPct: Math.max(0, fillPct), packetFrom, packetTo,
                   packetStart: packetFrom ? pct(packetFrom) : null,
                   packetEnd: packetTo ? pct(packetTo) : null,
                   active: this.isPlaying() || !!pendingStage };
```

Replace the last line with:

```javascript
                   active: this.isPlaying() || !!pendingStage || this.streamActive };
```

- [ ] **Step 7: Header chip + live spinner text**

Find the status chip in the header (~239-240):

```html
    <span class="status-chip"><span class="live" :class="mode === 'mock' ? 'mock' : ''"></span>
      <span x-text="mode === 'mock' ? 'Mock mode · demo' : 'Qwen Cloud · online'"></span></span>
```

Replace with (adds a second chip shown only while streaming):

```html
    <span class="status-chip"><span class="live" :class="mode === 'mock' ? 'mock' : ''"></span>
      <span x-text="mode === 'mock' ? 'Mock mode · demo' : 'Qwen Cloud · online'"></span></span>
    <span class="status-chip" x-show="streamActive" style="margin-left:10px">
      <span class="rail-live"></span>
      <span x-text="(streamTrace.length) + ' agents done' + (streamStageLabel ? ' · now: ' + streamStageLabel : '')"></span></span>
```

Then find the auto-mode spinner line (~285):

```html
      <p class="spinner" x-show="loading">The agent team is analysing, designing, reviewing and arbitrating…</p>
```

Replace with:

```html
      <p class="spinner" x-show="loading"
         x-text="streamStageLabel ? ('Live: ' + streamStageLabel + ' working… (' + streamTrace.length + ' done)') : 'The agent team is analysing, designing, reviewing and arbitrating…'"></p>
```

- [ ] **Step 8: Surface a stream-level notice**

Find the existing compare-error line just below the spinner (~284):

```html
      <p class="muted" x-show="cmpError" style="margin-top:10px; color: var(--warn)" x-text="cmpError"></p>
```

Add immediately after it:

```html
      <p class="muted" x-show="streamNotice" style="margin-top:10px; color: var(--warn)" x-text="streamNotice"></p>
```

- [ ] **Step 9: Sanity-check the HTML still parses (no server yet)**

Run: `./.venv/Scripts/python.exe -c "import pathlib; s=pathlib.Path('app/static/index.html').read_text(encoding='utf-8'); assert s.count('runAuto') and 'handleStreamEvent' in s and 'playPipeline' not in s; print('ok')"`
Expected: prints `ok`

- [ ] **Step 10: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): live SSE progress for auto mode; remove fake replay"
```

---

## Task 5: Frontend — PCB Critic on the right (antagonist side)

**Files:**
- Modify: `app/static/index.html`

The Society chat currently sends only the Design Critic to the right. The PCB Critic is the PCB Engineer's antagonist and should sit on the right too. The expression appears in **two** places (stepwise block ~535 and result block ~690).

- [ ] **Step 1: Replace both occurrences**

Find each occurrence of:

```html
            <div :class="s.agent==='Design Critic' ? 'bubble-right' : 'bubble-left'">
```

and

```html
              <div :class="s.agent==='Design Critic' ? 'bubble-right' : 'bubble-left'">
```

Replace the class expression in **both** with `['Design Critic','PCB Critic'].includes(s.agent)`. The two full replacement lines are:

```html
            <div :class="['Design Critic','PCB Critic'].includes(s.agent) ? 'bubble-right' : 'bubble-left'">
```

```html
              <div :class="['Design Critic','PCB Critic'].includes(s.agent) ? 'bubble-right' : 'bubble-left'">
```

(They differ only by leading indentation — match each in place.)

- [ ] **Step 2: Verify both were changed and none remain on the old form**

Run: `./.venv/Scripts/python.exe -c "import pathlib; s=pathlib.Path('app/static/index.html').read_text(encoding='utf-8'); assert \"s.agent==='Design Critic' ? 'bubble-right'\" not in s; assert s.count(\"['Design Critic','PCB Critic'].includes(s.agent)\")==2; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "fix(ui): PCB Critic renders on the right as antagonist"
```

---

## Task 6: Full verification (test suite + live run)

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all). If anything fails, fix before proceeding.

- [ ] **Step 2: Start the live server**

Run (background): `./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8012 --log-level warning`
Then: `curl -s http://127.0.0.1:8012/api/health`
Expected: `"mode":"qwen"` (the real key in `.env` is loaded)

- [ ] **Step 3: Verify the stream emits incrementally (raw)**

Run: `curl -N -s -X POST http://127.0.0.1:8012/api/run/stream -H "Content-Type: application/json" -d '{"requirements_text":"A 24V industrial sensor board with an STM32, USB-C and RS485.","profile":"Senior Review Team","persona":"professional"}'`
Expected: `data: {"type":"stage",...}` lines arrive one at a time over ~1-4 minutes (Requirements first, then Architect, Critic, possibly round-2 rework, Arbitration, PCB Engineer, PCB Critic), ending with a single `data: {"type":"final",...}`. Confirms real incremental delivery, not one buffered blob.

- [ ] **Step 4: Verify in the browser (preview tools)**

Open `http://127.0.0.1:8012`, enable the **Auto mode** checkbox, load the example, click **Run agents**, and confirm:
- the header shows the live "N agents done · now: <agent>" chip,
- the Mission-Control rail advances stage by stage **during** the run (not a 4-second replay at the end),
- in the **Agent Society** tab, both **Design Critic** and **PCB Critic** bubbles sit on the right,
- on completion the architecture, PCB-Readiness pack and approval sections render as before.

Capture a screenshot as proof.

- [ ] **Step 5: Stop the server**

Stop the background uvicorn task.

- [ ] **Step 6: Final commit (if any verification fixes were made)**

```bash
git add -A
git commit -m "test: verify live streaming end-to-end"
```

---

## Self-Review Notes

- **Spec coverage:** SSE backend (Tasks 1-3) ✓; live rail / remove replay (Task 4 steps 4-6) ✓; page-level "agents working" signal (Task 4 step 7) ✓; PCB Critic on the right (Task 5) ✓; report left unchanged (no task touches `report.py` / `generate`) ✓; error/guard fallback streamed (Task 2 `_error_then_fallback`, tested) ✓; mock-mode parity (Task 2 + Task 3 tests) ✓.
- **Backward compat:** `run()` re-implemented as a drainer; `/api/run`, comparison, bench and all existing orchestrator/endpoint tests untouched and re-run in Task 6 step 1.
- **Naming consistency:** `run_stream`, `_design_and_review_stream`, `_pcb_design_and_review_stream`, `_error_then_fallback`, `handleStreamEvent`, `streamTrace`/`streamActive`/`streamStageLabel`/`streamNotice` used identically across backend tasks and frontend tasks.
- **Latent fix:** Task 2 step 3(a) adds the missing `Arbitration` import the existing `_pcb_design_and_review` type hint already assumed.
