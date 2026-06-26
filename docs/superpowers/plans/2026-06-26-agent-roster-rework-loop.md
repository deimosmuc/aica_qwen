# Agent Roster — Per-Agent Models + Review-and-Rework Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user run the pipeline as a configurable agent team — each agent on its own model (a strong supervisor + cheaper juniors) — with an optional Critic→Architect review-and-rework loop that turns the linear pipeline iterative and shows the self-correction in the trace.

**Architecture:** A `RunProfile` (role→model map + rework flag + round cap) drives the orchestrator, which builds one `QwenClient` per role via `settings.model_copy`. The Architect↔Critic step is extracted into a helper that, when rework is on, loops while the Critic reports `missing_blocks` (capped at `max_rounds`). Profiles are a named registry; the UI's model dropdown becomes a profile selector. Everything degrades gracefully (unknown profile/model → default; guard block → mock fallback; mock mode → scripted two-round example).

**Tech Stack:** Python, FastAPI, Pydantic v2 / pydantic-settings, Alpine.js, pytest.

Spec: `docs/superpowers/specs/2026-06-26-agent-roster-rework-loop-design.md`

Run tests with the project venv: `.venv/Scripts/python.exe -m pytest`. Known unrelated pre-existing failures: 2 in `tests/test_milestone1.py` (local `.env` has a real `QWEN_API_KEY`, so the app reports `qwen` mode while those tests assert `mock`). Ignore them; everything else must stay green.

**Profile slot keys = the four pipeline stage names** — `requirements`, `architecture`, `critique`, `arbitration` — so `/step` can map a stage straight to its model with no extra mapping.

---

## File structure

- Create `app/services/profiles.py` — `RunProfile`, the `PROFILES` registry, `uniform_profile`, `default_profile`, `resolve_profile`, `profile_for`.
- Modify `app/services/config.py` — bump `guard_max_calls_per_run` 8 → 12.
- Modify `app/models/schemas.py` — `TraceStep.round` (additive); `RunRequest.profile`; `StepRequest.profile`.
- Modify `app/services/orchestrator.py` — per-role clients, `_design_and_review` helper (Task 2), then the rework loop inside it (Task 3).
- Modify `app/services/mock.py` — `mock_run_rework` scripted two-round example.
- Modify `app/api/routes.py` — `/run` and `/step` resolve a profile.
- Modify `app/static/index.html` — profile selector; trace round labels; trace key fix.
- Create `tests/test_profiles.py`; extend `tests/test_run_endpoint.py`; add `tests/test_orchestrator.py`.

---

## Task 1: Profiles registry + guard cap

**Files:**
- Create: `app/services/profiles.py`
- Modify: `app/services/config.py` (`guard_max_calls_per_run`)
- Test: `tests/test_profiles.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_profiles.py`:

```python
"""Run-profile registry and resolution."""
from app.services.config import Settings
from app.services.profiles import (
    PROFILES,
    default_profile,
    profile_for,
    resolve_profile,
)


def test_senior_review_team_assigns_max_to_supervisor():
    p = PROFILES["Senior Review Team"]
    assert p.models["critique"] == "qwen-max"
    assert p.models["arbitration"] == "qwen-max"
    assert p.models["architecture"] == "qwen-plus"
    assert p.rework is True and p.max_rounds == 2


def test_resolve_profile_unknown_name_falls_back_to_default():
    s = Settings()
    p = resolve_profile("does-not-exist", s)
    assert all(m == s.qwen_model for m in p.models.values())
    assert p.rework is False


def test_resolve_profile_sanitises_models_through_allowlist(monkeypatch):
    s = Settings()
    # Force one slot to an unknown model; resolution must coerce it to the default.
    bad = PROFILES["Senior Review Team"].model_copy(
        update={"models": {**PROFILES["Senior Review Team"].models, "critique": "gpt-4"}}
    )
    monkeypatch.setitem(PROFILES, "Bad", bad)
    p = resolve_profile("Bad", s)
    assert p.models["critique"] == s.qwen_model


def test_profile_for_uniform_model():
    s = Settings()
    p = profile_for(None, "qwen-max", s)
    assert all(m == "qwen-max" for m in p.models.values())
    assert p.rework is False


def test_profile_for_unknown_model_defaults():
    s = Settings()
    p = profile_for(None, "gpt-4", s)
    assert all(m == s.qwen_model for m in p.models.values())


def test_guard_cap_raised_for_rework_headroom():
    assert Settings().guard_max_calls_per_run == 12
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_profiles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.profiles'`

- [ ] **Step 3: Create the profiles module**

Create `app/services/profiles.py`:

```python
"""Run profiles — compose the agent team like an engineering org.

A profile assigns a model to each pipeline stage (a strong supervisor can run on
a stronger model than the junior sub-agents) and decides whether the Critic→
Architect review-and-rework loop runs. Slot keys are the four pipeline STAGE
names so /step can map a stage straight to its model.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.services.config import Settings

ROLES = ("requirements", "architecture", "critique", "arbitration")


class RunProfile(BaseModel):
    name: str
    models: dict[str, str]      # stage name -> model
    rework: bool = False
    max_rounds: int = 2         # total review rounds (1 initial + up to max_rounds-1 reworks)


def uniform_profile(name: str, model: str) -> RunProfile:
    return RunProfile(name=name, models={r: model for r in ROLES}, rework=False, max_rounds=1)


PROFILES: dict[str, RunProfile] = {
    "Uniform qwen-plus": uniform_profile("Uniform qwen-plus", "qwen-plus"),
    "Uniform qwen-max": uniform_profile("Uniform qwen-max", "qwen-max"),
    "Budget Turbo": uniform_profile("Budget Turbo", "qwen-turbo"),
    "Senior Review Team": RunProfile(
        name="Senior Review Team",
        models={
            "requirements": "qwen-plus",
            "architecture": "qwen-plus",
            "critique": "qwen-max",
            "arbitration": "qwen-max",
        },
        rework=True,
        max_rounds=2,
    ),
}


def default_profile(settings: Settings) -> RunProfile:
    """Uniform profile on the configured default model (today's single-model behaviour)."""
    return uniform_profile(f"Uniform {settings.qwen_model}", settings.qwen_model)


def resolve_profile(name: str | None, settings: Settings) -> RunProfile:
    """Look up a named profile and sanitise every model slot through the allowlist.
    Unknown name -> the uniform default profile."""
    profile = PROFILES.get(name) if name else None
    if profile is None:
        return default_profile(settings)
    models = {role: settings.resolve_model(m) for role, m in profile.models.items()}
    return profile.model_copy(update={"models": models})


def profile_for(name: str | None, model: str | None, settings: Settings) -> RunProfile:
    """Resolve a request to a profile: a named profile wins; else a uniform profile
    from a single model; else the default. All models pass the allowlist."""
    if name:
        return resolve_profile(name, settings)
    if model:
        m = settings.resolve_model(model)
        return uniform_profile(f"Uniform {m}", m)
    return default_profile(settings)
```

- [ ] **Step 4: Bump the guard cap**

In `app/services/config.py`, find:

```python
    guard_max_calls_per_run: int = 8        # one /run must never exceed this
```

Replace with:

```python
    guard_max_calls_per_run: int = 12       # headroom for the rework loop; $ budget is the real cap
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_profiles.py -v`
Expected: PASS (6 tests)

Then the full suite: `.venv/Scripts/python.exe -m pytest -q` → green except the 2 known `test_milestone1.py` failures.

- [ ] **Step 6: Commit**

```bash
git add app/services/profiles.py app/services/config.py tests/test_profiles.py
git commit -m "feat(roster): run-profile registry + raise guard call cap for rework"
```

---

## Task 2: Orchestrator — per-role clients + extracted design/review (no loop yet)

**Files:**
- Modify: `app/models/schemas.py` (`TraceStep`)
- Modify: `app/services/orchestrator.py` (full rewrite)
- Test: `tests/test_orchestrator.py` (new)

- [ ] **Step 1: Add the additive `round` field to `TraceStep`**

In `app/models/schemas.py`, in `class TraceStep`, after the `duration_ms` field add:

```python
    # Review round this step belongs to (1 = initial; >1 = rework round).
    round: int = 1
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_orchestrator.py`:

```python
"""Orchestrator: per-role model wiring + behaviour preservation."""
from app.services.config import Settings
from app.services.orchestrator import Orchestrator
from app.services.profiles import PROFILES


def test_client_per_role_uses_profile_model():
    orch = Orchestrator(Settings(qwen_api_key="sk-test"), profile=PROFILES["Senior Review Team"])
    assert orch._client_for("critique")._model == "qwen-max"
    assert orch._client_for("arbitration")._model == "qwen-max"
    assert orch._client_for("architecture")._model == "qwen-plus"


def test_default_profile_is_uniform():
    s = Settings(qwen_api_key="sk-test")
    orch = Orchestrator(s)
    assert orch._client_for("critique")._model == s.qwen_model


def test_mock_mode_pipeline_unchanged():
    out = Orchestrator(Settings(qwen_api_key="")).run("a 24V board")
    assert out.mode == "mock"
    assert len(out.trace) == 4
    assert all(s.round == 1 for s in out.trace)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `Orchestrator.__init__` has no `profile` param and no `_client_for`.

- [ ] **Step 4: Rewrite `orchestrator.py`**

Replace the ENTIRE contents of `app/services/orchestrator.py` with:

```python
"""Orchestrator — owns all state and runs agents in sequence.

Agents never talk to each other directly. The orchestrator calls each agent,
holds the resulting JSON, and passes what is needed to the next one. Each stage
runs on the model assigned by the active RunProfile, so a senior supervisor can
run on a stronger model than the junior sub-agents.
"""
from __future__ import annotations

from time import perf_counter

from app.agents.arbitration import ArbitrationAgent
from app.agents.architect import SystemArchitectAgent
from app.agents.base import ChatClient
from app.agents.critic import DesignCriticAgent
from app.agents.requirements import RequirementsAgent
from app.models.schemas import Architecture, Critique, Requirements, RunResponse, TraceStep
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.mock import mock_run
from app.services.profiles import RunProfile, default_profile
from app.services.qwen_client import QwenClient, QwenError, QwenTruncatedError


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        profile: RunProfile | None = None,
        client: ChatClient | None = None,
    ):
        self.settings = settings
        self.profile = profile or default_profile(settings)
        self._client = client  # test override: when set, used for every role

    def _client_for(self, role: str) -> ChatClient:
        if self._client is not None:
            return self._client
        model = self.profile.models[role]
        return QwenClient(self.settings.model_copy(update={"qwen_model": model}))

    @staticmethod
    def _arch_step(architecture: Architecture, round_no: int, ms: int) -> TraceStep:
        if round_no == 1:
            summary = (
                f"Live Qwen: proposed {len(architecture.blocks)} functional blocks, "
                f"{len(architecture.power)} power domains across hierarchical sheets."
            )
        else:
            summary = (
                f"Live Qwen (rework round {round_no}): revised the architecture to "
                f"{len(architecture.blocks)} blocks addressing the critic's findings."
            )
        return TraceStep(
            agent=SystemArchitectAgent.name, role=SystemArchitectAgent.role,
            status="ok", duration_ms=ms, round=round_no, summary=summary,
        )

    @staticmethod
    def _critic_step(critique: Critique, round_no: int, ms: int) -> TraceStep:
        n = len(critique.warnings) + len(critique.risks) + len(critique.missing_blocks)
        return TraceStep(
            agent=DesignCriticAgent.name, role=DesignCriticAgent.role,
            status="warning" if n else "ok", duration_ms=ms, round=round_no,
            summary=(
                f"Live Qwen (round {round_no}): flagged {len(critique.warnings)} warnings, "
                f"{len(critique.risks)} risks, {len(critique.missing_blocks)} missing blocks."
            ),
        )

    def _design_and_review(
        self, requirements: Requirements, guidance: list[str]
    ) -> tuple[Architecture, Critique, list[TraceStep]]:
        """One design + review pass (round 1). The rework loop is added in a later task."""
        steps: list[TraceStep] = []
        t = perf_counter()
        architecture = SystemArchitectAgent().run(self._client_for("architecture"), requirements, guidance)
        steps.append(self._arch_step(architecture, 1, int((perf_counter() - t) * 1000)))
        t = perf_counter()
        critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, guidance)
        steps.append(self._critic_step(critique, 1, int((perf_counter() - t) * 1000)))
        return architecture, critique, steps

    def run(self, requirements_text: str, guidance: list[str] | None = None) -> RunResponse:
        if self.settings.mock_mode:
            return mock_run(requirements_text)
        guidance = guidance or []
        try:
            t = perf_counter()
            requirements = RequirementsAgent().run(
                self._client_for("requirements"), requirements_text, guidance
            )
            req_ms = int((perf_counter() - t) * 1000)

            architecture, critique, design_steps = self._design_and_review(requirements, guidance)

            t = perf_counter()
            arbitration = ArbitrationAgent().run(
                self._client_for("arbitration"), requirements, architecture, critique, guidance
            )
            arb_ms = int((perf_counter() - t) * 1000)
        except GuardBlocked as e:
            return self._guarded_fallback(
                requirements_text,
                f"API limit reached ({e.reason}). Showing example data instead — no charge.",
            )
        except QwenTruncatedError as e:
            return self._guarded_fallback(
                requirements_text,
                f"Qwen's answer was cut off ({e}). Showing example data instead — "
                "try a simpler request or raise GUARD_MAX_OUTPUT_TOKENS.",
            )
        except QwenError as e:
            return self._guarded_fallback(
                requirements_text,
                f"Qwen was unreachable ({e}). Showing example data instead.",
            )

        req_step = TraceStep(
            agent=RequirementsAgent.name, role=RequirementsAgent.role, status="ok",
            duration_ms=req_ms,
            summary=(
                f"Live Qwen: structured {len(requirements.requirements)} requirements, "
                f"raised {len(requirements.questions)} clarification questions "
                f"(confidence {requirements.confidence:.0%})."
            ),
        )
        arb_step = TraceStep(
            agent=ArbitrationAgent.name, role=ArbitrationAgent.role, status="ok",
            duration_ms=arb_ms,
            summary=(
                f"Live Qwen: approved the architecture; logged {len(arbitration.todo)} TODOs "
                f"and {len(arbitration.human_review)} human-review items."
            ),
        )

        return RunResponse(
            mode="qwen",
            requirements=requirements,
            architecture=architecture,
            critique=critique,
            arbitration=arbitration,
            trace=[req_step, *design_steps, arb_step],
            needs_approval=True,
        )

    def _guarded_fallback(self, requirements_text: str, notice: str) -> RunResponse:
        result = mock_run(requirements_text)
        result.notice = notice
        return result
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v`
Expected: PASS (3 tests)

Then the full suite: `.venv/Scripts/python.exe -m pytest -q`
Expected: green except the 2 known failures. (The comparison test that monkeypatches `Orchestrator.run` still works — the signature is unchanged.)

- [ ] **Step 6: Commit**

```bash
git add app/models/schemas.py app/services/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(roster): per-role model clients + extracted design/review pass"
```

---

## Task 3: Orchestrator — the review-and-rework loop

**Files:**
- Modify: `app/services/orchestrator.py` (`_design_and_review` only)
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_orchestrator.py`:

```python
import app.services.orchestrator as orch_mod
from app.models.schemas import Arbitration, Architecture, Block, Critique, Requirements
from app.services.profiles import RunProfile


def _rework_profile(rounds=2):
    return RunProfile(
        name="t",
        models={r: "qwen-plus" for r in ("requirements", "architecture", "critique", "arbitration")},
        rework=True, max_rounds=rounds,
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


def test_rework_stops_when_critic_is_clean(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    # round 1 reports a missing block; round 2 is clean.
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["DUMMY_CLOCK"]) if n == 1 else Critique(), calls)
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"), profile=_rework_profile()).run("board")
    assert calls["arch"] == 2 and calls["crit"] == 2     # initial + exactly one rework
    assert any(s.round == 2 for s in out.trace)
    assert out.critique.missing_blocks == []             # final state is the clean one


def test_rework_is_bounded_when_critic_never_satisfied(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["still missing"]), calls)
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"), profile=_rework_profile(rounds=2)).run("board")
    assert calls["arch"] == 2 and calls["crit"] == 2     # capped at max_rounds, no infinite loop
    assert max(s.round for s in out.trace) == 2


def test_no_rework_when_profile_disables_it(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["DUMMY_CLOCK"]), calls)
    profile = _rework_profile()
    profile = profile.model_copy(update={"rework": False})
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"), profile=profile).run("board")
    assert calls["arch"] == 1 and calls["crit"] == 1     # single pass despite missing blocks
    assert all(s.round == 1 for s in out.trace)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py::test_rework_stops_when_critic_is_clean -v`
Expected: FAIL — `_design_and_review` is single-pass, so `calls["arch"] == 1`, not 2.

- [ ] **Step 3: Add the loop to `_design_and_review`**

In `app/services/orchestrator.py`, replace the `_design_and_review` method body with:

```python
    def _design_and_review(
        self, requirements: Requirements, guidance: list[str]
    ) -> tuple[Architecture, Critique, list[TraceStep]]:
        """Design + review, with an optional Critic->Architect rework loop.

        Round 1 is the initial design + review. While rework is enabled and the
        Critic still reports missing blocks, the findings are fed back to the
        Architect (via the existing guidance mechanism) and re-reviewed, up to
        max_rounds total rounds. missing_blocks is the trigger (warnings/risks
        are softer and would never converge).
        """
        steps: list[TraceStep] = []
        t = perf_counter()
        architecture = SystemArchitectAgent().run(self._client_for("architecture"), requirements, guidance)
        steps.append(self._arch_step(architecture, 1, int((perf_counter() - t) * 1000)))
        t = perf_counter()
        critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, guidance)
        steps.append(self._critic_step(critique, 1, int((perf_counter() - t) * 1000)))

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
            steps.append(self._arch_step(architecture, round_no, int((perf_counter() - t) * 1000)))
            t = perf_counter()
            critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, rework_guidance)
            steps.append(self._critic_step(critique, round_no, int((perf_counter() - t) * 1000)))

        return architecture, critique, steps
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v`
Expected: PASS (all, including the Task 2 tests)

Then the full suite: `.venv/Scripts/python.exe -m pytest -q` → green except the 2 known failures.

- [ ] **Step 5: Commit**

```bash
git add app/services/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(roster): Critic->Architect review-and-rework loop (bounded)"
```

---

## Task 4: Mock mode — scripted two-round rework

**Files:**
- Modify: `app/services/mock.py`
- Modify: `app/services/orchestrator.py` (mock branch)
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
def test_mock_mode_rework_profile_shows_two_rounds():
    out = orch_mod.Orchestrator(Settings(qwen_api_key=""), profile=_rework_profile()).run("a 24V board")
    assert out.mode == "mock"
    assert sorted({s.round for s in out.trace}) == [1, 2]
    # round-1 critic flagged gaps; the final critique is clean.
    round1_critic = [s for s in out.trace if s.agent == "Design Critic" and s.round == 1][0]
    assert round1_critic.status == "warning"
    assert out.critique.missing_blocks == []


def test_mock_mode_non_rework_profile_is_single_pass():
    out = orch_mod.Orchestrator(Settings(qwen_api_key=""), profile=PROFILES["Uniform qwen-plus"]).run("board")
    assert len(out.trace) == 4
    assert all(s.round == 1 for s in out.trace)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py::test_mock_mode_rework_profile_shows_two_rounds -v`
Expected: FAIL — mock mode always returns the single-pass `mock_run` (4 steps, all round 1).

- [ ] **Step 3: Add `mock_run_rework` to `mock.py`**

In `app/services/mock.py`, add `TraceStep` is already imported. Append this function after `mock_run`:

```python
def mock_run_rework(requirements_text: str) -> RunResponse:
    """Scripted two-round example for rework-enabled profiles, so the demo shows
    self-correction without an API key. Round 1 omits the Debug/LED block and the
    Critic flags it; round 2 adds it and the Critic is clean. The returned
    architecture/critique are the final (round-2) state."""
    base = mock_run(requirements_text)

    # Round-1 architecture: the same design minus the Debug block (the gap).
    round1_arch = base.architecture.model_copy(
        update={"blocks": [b for b in base.architecture.blocks if b.name != "Debug"]}
    )
    # Round-2: the full architecture, Critic now clean.
    round2_critique = Critique(
        warnings=base.critique.warnings,
        risks=base.critique.risks,
        missing_blocks=[],
        recommendations=base.critique.recommendations,
    )

    trace = [
        TraceStep(agent="Requirements Agent", role="Senior Systems Engineer", status="ok", round=1,
                  summary="Structured 5 requirements, raised 2 clarification questions."),
        TraceStep(agent="System Architect", role="Principal Hardware Architect", status="ok", round=1,
                  summary=f"Proposed {len(round1_arch.blocks)} functional blocks across hierarchical sheets."),
        TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", status="warning", round=1,
                  summary="Flagged 1 missing block (Debug/SWD + status LEDs)."),
        TraceStep(agent="System Architect", role="Principal Hardware Architect", status="ok", round=2,
                  summary=f"Revised: added the Debug block — now {len(base.architecture.blocks)} blocks."),
        TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", status="ok", round=2,
                  summary="Re-reviewed: no missing blocks remain."),
        TraceStep(agent="Arbitration", role="Chief Engineer", status="ok", round=2,
                  summary="Approved architecture; logged 2 TODOs and 2 human-review items."),
    ]

    return RunResponse(
        mode="mock",
        requirements=base.requirements,
        architecture=base.architecture,   # final = full design
        critique=round2_critique,
        arbitration=base.arbitration,
        trace=trace,
        needs_approval=True,
    )
```

(`round1_arch` and `round1_critique` document the scripted first round inside the trace summaries; the returned object carries the final round-2 state, mirroring how the live loop returns its last architecture/critique.)

- [ ] **Step 4: Branch the orchestrator's mock path on the profile**

In `app/services/orchestrator.py`, update the import:

```python
from app.services.mock import mock_run
```

to:

```python
from app.services.mock import mock_run, mock_run_rework
```

And replace the mock-mode line in `run`:

```python
        if self.settings.mock_mode:
            return mock_run(requirements_text)
```

with:

```python
        if self.settings.mock_mode:
            return mock_run_rework(requirements_text) if self.profile.rework else mock_run(requirements_text)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v`
Expected: PASS (all)

Then the full suite: `.venv/Scripts/python.exe -m pytest -q` → green except the 2 known failures.

- [ ] **Step 6: Commit**

```bash
git add app/services/mock.py app/services/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(roster): scripted two-round rework example for mock mode"
```

---

## Task 5: Routes — `/run` and `/step` accept a profile

**Files:**
- Modify: `app/models/schemas.py` (`RunRequest`, `StepRequest`)
- Modify: `app/api/routes.py` (`/run`, `/step`)
- Test: `tests/test_run_endpoint.py` (update + extend)

- [ ] **Step 1: Update and extend the run-endpoint tests**

The existing `tests/test_run_endpoint.py` captures `settings.qwen_model`; the model now lives in the profile. Replace the WHOLE file with:

```python
"""The /api/run and /api/step endpoints resolve an optional profile / model."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.services.mock import mock_run


def _fake_orch_capturing(captured):
    class FakeOrch:
        def __init__(self, settings, profile=None, client=None):
            captured["profile"] = profile

        def run(self, text, guidance=None):
            return mock_run(text)

    return FakeOrch


def test_run_uniform_model_builds_uniform_profile(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "model": "qwen-max"})
    assert r.status_code == 200
    assert all(m == "qwen-max" for m in captured["profile"].models.values())
    assert captured["profile"].rework is False


def test_run_named_profile_assigns_per_role_models(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "profile": "Senior Review Team"})
    assert r.status_code == 200
    assert captured["profile"].models["critique"] == "qwen-max"
    assert captured["profile"].models["architecture"] == "qwen-plus"
    assert captured["profile"].rework is True


def test_run_unknown_profile_falls_back_to_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(routes, "Orchestrator", _fake_orch_capturing(captured))
    client = TestClient(app)
    r = client.post("/api/run", json={"requirements_text": "x", "profile": "nope"})
    assert r.status_code == 200
    assert captured["profile"].models["critique"] == "qwen-plus"  # default
    assert captured["profile"].rework is False


def test_step_uses_profile_model_for_its_stage(monkeypatch):
    from app.models.schemas import StepResponse, TraceStep
    captured = {}

    def fake_run_stage(req, settings):
        captured["model"] = settings.qwen_model
        return StepResponse(
            stage=req.stage, mode="qwen",
            trace_step=TraceStep(agent="Design Critic", role="Senior Hardware Reviewer", summary="ok"),
        )

    monkeypatch.setattr(routes, "run_stage", fake_run_stage)
    client = TestClient(app)
    r = client.post("/api/step", json={"stage": "critique", "requirements_text": "x",
                                       "profile": "Senior Review Team"})
    assert r.status_code == 200
    assert captured["model"] == "qwen-max"  # the supervisor model for the critique stage
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_run_endpoint.py -v`
Expected: FAIL — `RunRequest`/`StepRequest` have no `profile`; routes don't build profiles; `FakeOrch` is constructed with one arg today.

- [ ] **Step 3: Add `profile` to the request schemas**

In `app/models/schemas.py`, in `class RunRequest`, after the `model` field add:

```python
    profile: str | None = Field(default=None, description="Named run profile; overrides `model` when set.")
```

In `class StepRequest`, after its `model` field add:

```python
    profile: str | None = None
```

- [ ] **Step 4: Resolve the profile in `/run`**

In `app/api/routes.py`, add the import near the other service imports:

```python
from app.services.profiles import profile_for
```

Replace the `run` body:

```python
    settings = get_settings()
    settings = settings.model_copy(update={"qwen_model": settings.resolve_model(req.model)})
    return Orchestrator(settings).run(req.requirements_text, req.guidance)
```

with:

```python
    settings = get_settings()
    profile = profile_for(req.profile, req.model, settings)
    return Orchestrator(settings, profile).run(req.requirements_text, req.guidance)
```

- [ ] **Step 5: Resolve the profile in `/step`**

In `app/api/routes.py`, replace the `step` body:

```python
    settings = get_settings()
    settings = settings.model_copy(update={"qwen_model": settings.resolve_model(req.model)})
    try:
        return run_stage(req, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

with:

```python
    settings = get_settings()
    profile = profile_for(req.profile, req.model, settings)
    settings = settings.model_copy(update={"qwen_model": profile.models[req.stage]})
    try:
        return run_stage(req, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_run_endpoint.py -v`
Expected: PASS (4 tests)

Then the full suite: `.venv/Scripts/python.exe -m pytest -q` → green except the 2 known failures.

- [ ] **Step 7: Commit**

```bash
git add app/models/schemas.py app/api/routes.py tests/test_run_endpoint.py
git commit -m "feat(roster): /run and /step resolve a run profile (per-stage model)"
```

---

## Task 6: UI — profile selector + trace round labels

**Files:**
- Modify: `app/static/index.html`

Frontend-only; verify by suite-green + static checks.

- [ ] **Step 1: Replace the model state with profile state**

In `app/static/index.html`, find:

```javascript
        MODELS: ["qwen-plus", "qwen-max", "qwen-turbo"], selectedModel: "qwen-plus",
```

Replace with:

```javascript
        PROFILES: ["Uniform qwen-plus", "Uniform qwen-max", "Budget Turbo", "Senior Review Team"], selectedProfile: "Uniform qwen-plus",
```

- [ ] **Step 2: Turn the model dropdown into a profile selector**

In `app/static/index.html`, find:

```html
        <label class="model-pick">Model:
          <select x-model="selectedModel" :disabled="loading || stepBusy || comparing">
            <template x-for="m in MODELS" :key="m"><option :value="m" x-text="m"></option></template>
          </select>
        </label>
```

Replace with:

```html
        <label class="model-pick">Profile:
          <select x-model="selectedProfile" :disabled="loading || stepBusy || comparing">
            <template x-for="p in PROFILES" :key="p"><option :value="p" x-text="p"></option></template>
          </select>
        </label>
```

- [ ] **Step 3: Send the profile in the auto-run fetch**

In `app/static/index.html`, find:

```javascript
              body: JSON.stringify({ requirements_text: this.input, guidance: this.parseConstraints(), model: this.selectedModel })
```

Replace with:

```javascript
              body: JSON.stringify({ requirements_text: this.input, guidance: this.parseConstraints(), profile: this.selectedProfile })
```

- [ ] **Step 4: Send the profile in the step fetch**

In `app/static/index.html`, find (inside `loadStage`'s body object):

```javascript
                critique: this.acc.critique,
                model: this.selectedModel
```

Replace with:

```javascript
                critique: this.acc.critique,
                profile: this.selectedProfile
```

- [ ] **Step 5: Fix the auto-run trace key and add the round label**

In `app/static/index.html`, find the auto-run trace block:

```html
            <template x-for="s in result.trace" :key="s.agent">
              <div class="step" :class="s.status">
                <div class="dot" :class="s.status"></div>
                <div style="flex:1">
                  <span class="agent" x-text="s.agent"></span>
                  <span class="role" x-text="'· ' + s.role"></span>
                  <span class="ms" x-show="s.duration_ms" x-text="fmtMs(s.duration_ms)"></span>
```

Replace with:

```html
            <template x-for="(s, i) in result.trace" :key="i">
              <div class="step" :class="s.status">
                <div class="dot" :class="s.status"></div>
                <div style="flex:1">
                  <span class="agent" x-text="s.agent"></span>
                  <span class="role" x-text="'· ' + s.role"></span>
                  <span class="round" x-show="s.round > 1" x-text="'· round ' + s.round" style="color: var(--warn); font-size: 12px;"></span>
                  <span class="ms" x-show="s.duration_ms" x-text="fmtMs(s.duration_ms)"></span>
```

(The `:key="i"` change is required: with rework there are two "System Architect" / "Design Critic" steps, so keying by `s.agent` would collide and Alpine would drop the duplicates.)

- [ ] **Step 6: Verify**

Run: `.venv/Scripts/python.exe -m pytest -q` — suite unaffected apart from the 2 known failures.
Static checks (grep the file): `selectedProfile` appears in state, in the `<select>`, in the run body, and in the step body; the old `selectedModel` / `MODELS` are gone; the auto-run trace uses `(s, i) in result.trace` with `:key="i"` and references `s.round`.
If a dev server is trivial to start: pick "Senior Review Team", run, and confirm the trace shows round-2 Architect/Critic steps with the "round 2" label; otherwise rely on the static checks.

- [ ] **Step 7: Commit**

```bash
git add app/static/index.html
git commit -m "feat(roster): UI profile selector + rework round labels in the trace"
```

---

## Final verification

- [ ] Full suite: `.venv/Scripts/python.exe -m pytest -q` — all pass except the 2 known `test_milestone1.py` mock-mode failures.
- [ ] Mock-mode demo (no key needed): selecting "Senior Review Team" shows the scripted two-round self-correction in the trace (round 1 flags a missing block → round 2 clean). A uniform profile is single-pass.
- [ ] Live (if a key is present): "Senior Review Team" runs Critic/Arbitration on qwen-max and the others on qwen-plus; if the Critic reports missing blocks the Architect is re-invoked once and the trace shows round 2. Worst case stays within the 12-call guard; the $ budget remains the real cap.
- [ ] Graceful degradation: unknown profile/model → default; guard block / Qwen error → example data with an honest notice.
- [ ] No new unqualified "production-ready" claim introduced.
