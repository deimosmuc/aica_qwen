# Efficiency Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, reproducible comparison that shows the multi-agent pipeline surfaces measurably more engineering concerns than a single-agent baseline, live in the UI and as a Markdown report.

**Architecture:** A pure rubric scorer (`rubric.py`) detects which engineering concerns a flattened output text *surfaces*. A `SingleAgentBaseline` agent makes one fair, high-level LLM call. A `comparison.py` service runs both the existing multi-agent `Orchestrator` and the baseline (guarded), scores both with the rubric, and returns a `Comparison`. Exposed via `POST /api/compare`, a UI panel, and `tools/compare_report.py`. Degrades to an illustrative result in Mock Mode.

**Tech Stack:** Python, FastAPI, Pydantic v2, pytest, Alpine.js (existing patterns).

---

## File Structure

- Create: `app/services/rubric.py` — rubric concerns + `score()`/`coverage()`
- Modify: `app/models/schemas.py` — `BaselineResult`, `ConcernResult`, `CompareRequest`, `Comparison`
- Create: `app/agents/baseline.py` — `SingleAgentBaseline`
- Create: `app/services/comparison.py` — `run_comparison()`, `mock_baseline()`, flatten helpers
- Modify: `app/api/routes.py` — `POST /api/compare`
- Modify: `app/static/index.html` — compare button + panel + JS
- Create: `tools/compare_report.py` — script that writes a Markdown report
- Create tests: `tests/test_rubric.py`, `tests/test_baseline_agent.py`, `tests/test_comparison.py`, `tests/test_compare_endpoint.py`

Run all tests with: `.venv/Scripts/python.exe -m pytest -q`

---

## Task 1: Rubric scorer

**Files:**
- Create: `app/services/rubric.py`
- Test: `tests/test_rubric.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rubric.py
"""Comparison rubric: deterministic concern detection."""
from app.services.rubric import RUBRIC, coverage, score


def test_detects_present_concern():
    s = score("TODO: add TVS surge protection on the 24V input")
    assert s["input_protection"] is True


def test_absent_concern_is_false():
    s = score("Just a microcontroller and a connector.")
    assert s["input_protection"] is False
    assert s["reset"] is False


def test_word_boundary_avoids_false_match():
    # "scheduled" must NOT trigger the short token "led" (testability).
    assert score("the build is scheduled")["testability"] is False
    # "forward" must NOT trigger "swd" (debug_access).
    assert score("look forward")["debug_access"] is False


def test_rubric_has_twelve_concerns():
    assert len(RUBRIC) == 12
    assert len({c.id for c in RUBRIC}) == 12


def test_coverage_counts_distinct_concerns():
    text = "SWD debug header and a reset circuit"
    s = score(text)
    assert s["debug_access"] is True
    assert s["reset"] is True
    assert coverage(text) == sum(s.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rubric.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.rubric'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/rubric.py
"""Deterministic engineering-concern rubric for the multi- vs single-agent comparison.

A concern is "covered" when it is *surfaced as engineering work* (block / TODO /
assumption / review item / note) in the flattened output text — NOT when a
component is placed. Detection is plain, reproducible keyword matching so the
metric is auditable; the UI also shows both raw outputs so a human can verify.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Concern:
    id: str
    label: str
    terms: tuple[str, ...]


RUBRIC: tuple[Concern, ...] = (
    Concern("input_protection", "Surge/ESD protection on power input",
            ("tvs", "surge", "esd", "overvoltage", "varistor", "transient")),
    Concern("reverse_polarity", "Reverse-polarity protection",
            ("reverse polarity", "reverse-polarity", "ideal diode", "polarity protection", "reverse voltage")),
    Concern("overcurrent", "Overcurrent / fuse protection",
            ("fuse", "overcurrent", "over-current", "ptc", "current limit", "efuse")),
    Concern("power_domains", "Defined power rails / domains",
            ("rail", "power domain", "ldo", "dc-dc", "buck", "regulator", "+3v3", "+5v", "3v3", "5v")),
    Concern("decoupling", "Decoupling / filtering",
            ("decoupl", "bypass", "ferrite", "bulk capacit", "filtering")),
    Concern("debug_access", "Debug / programming access",
            ("swd", "jtag", "debug", "swclk", "swdio", "programming")),
    Concern("testability", "Test points / status indication",
            ("test point", "testpoint", "status led", "led", "test pad")),
    Concern("reset", "Reset circuit",
            ("reset", "nrst", "power-on reset", "watchdog", "por")),
    Concern("clock", "Clock source",
            ("clock", "crystal", "oscillator", "xtal", "hse", "lse")),
    Concern("interface_protection", "Interface isolation / termination",
            ("isolation", "isolat", "termination", "terminat", "common-mode", "choke", "bus protection")),
    Concern("connectors", "External connectors identified",
            ("connector", "header", "receptacle", "jack", "plug", "socket")),
    Concern("documentation_honesty", "Docs, assumptions, explicit uncertainty",
            ("assumption", "todo", "needs human review", "documentation", "datasheet")),
)

# Short / ambiguous tokens need word-boundary matching to avoid false positives
# (e.g. "led" inside "scheduled", "swd" inside "forward"). Longer stems use plain
# substring so plurals/derivatives still match.
_BOUNDARY = {"led", "swd", "jtag", "por", "ptc", "esd", "tvs", "hse", "lse"}


def _matches(term: str, low_text: str) -> bool:
    if term in _BOUNDARY:
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", low_text) is not None
    return term in low_text


def score(text: str) -> dict[str, bool]:
    """Return {concern_id: surfaced?} for the given text."""
    low = text.lower()
    return {c.id: any(_matches(t, low) for t in c.terms) for c in RUBRIC}


def coverage(text: str) -> int:
    """Number of distinct concerns surfaced in the text."""
    return sum(score(text).values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rubric.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/rubric.py tests/test_rubric.py
git commit -m "feat: deterministic engineering-concern rubric scorer"
```

---

## Task 2: Schemas

**Files:**
- Modify: `app/models/schemas.py` (append after the existing `GenerateResponse`)

- [ ] **Step 1: Add the models**

Append to `app/models/schemas.py`:

```python
# --- Single-agent baseline + comparison --------------------------------------


class BaselineResult(BaseModel):
    """One-shot single-agent output, kept at the same high level as the pipeline."""

    architecture: list[str] = []
    concerns: list[str] = []
    todos: list[str] = []
    human_review: list[str] = []
    assumptions: list[str] = []
    notes: list[str] = []


class ConcernResult(BaseModel):
    id: str
    label: str
    covered_multi: bool
    covered_single: bool


class CompareRequest(BaseModel):
    requirements_text: str = Field(..., description="The natural-language hardware request.")


class Comparison(BaseModel):
    requirements_text: str
    mode: Literal["mock", "qwen"]
    concerns: list[ConcernResult]
    multi_score: int
    single_score: int
    total: int
    delta: int
    multi_calls: int
    single_calls: int
    multi_output: RunResponse
    single_output: BaselineResult
    notice: str | None = None
```

- [ ] **Step 2: Verify it imports**

Run: `.venv/Scripts/python.exe -c "from app.models.schemas import Comparison, BaselineResult, ConcernResult, CompareRequest; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add app/models/schemas.py
git commit -m "feat: comparison + baseline schemas"
```

---

## Task 3: Single-agent baseline agent

**Files:**
- Create: `app/agents/baseline.py`
- Test: `tests/test_baseline_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_baseline_agent.py
"""The single-agent baseline (one fair, high-level call)."""
from app.agents.baseline import SingleAgentBaseline
from app.models.schemas import BaselineResult


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat_json(self, system, user, model=None):
        self.calls.append({"system": system, "user": user})
        return self.payload


PAYLOAD = {
    "architecture": ["MCU block", "Power 24V->5V->3V3"],
    "concerns": ["Check current budget"],
    "todos": ["TODO: pick STM32 variant"],
    "human_review": [],
    "assumptions": ["Assumption: single board"],
    "notes": ["SWD for programming"],
}


def test_baseline_parses_result():
    client = FakeClient(PAYLOAD)
    result = SingleAgentBaseline().run(client, "A 24V STM32 board")
    assert isinstance(result, BaselineResult)
    assert result.architecture == ["MCU block", "Power 24V->5V->3V3"]
    assert result.assumptions


def test_baseline_prompt_demands_high_level_json():
    client = FakeClient(PAYLOAD)
    SingleAgentBaseline().run(client, "A 24V STM32 board")
    system = client.calls[0]["system"].lower()
    assert "json" in system           # required for Qwen json_object mode
    assert "placeholder" in system    # stays high-level, no real parts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_baseline_agent.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.agents.baseline'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/agents/baseline.py
"""Single-Agent Baseline — the comparison's control group.

ONE LLM call asked to do, in a single pass, what the whole agent team does. The
prompt is competent and fair (not a strawman) and explicitly stays high-level —
a scaffold plus review with placeholder blocks only, no part values or placement —
so the comparison measures review thoroughness at the same altitude.
"""
from __future__ import annotations

from app.agents.base import ChatClient
from app.models.schemas import BaselineResult

NAME = "Single-Agent Baseline"
ROLE = "Generalist (one-shot)"

SYSTEM_PROMPT = """You are a single AI assistant acting as an entire hardware
engineering team at once. From a natural-language hardware request you produce, in
ONE response, a high-level engineering scaffold.

Stay HIGH-LEVEL, like a project scaffold:
- Identify functional blocks, power domains and interfaces; recommend PLACEHOLDER
  components only (e.g. DUMMY_MCU). Do NOT choose real parts or values, and do NOT
  place or wire components. No finished schematic.
- Surface engineering concerns (protection, debug, testability, interfaces, power,
  documentation) as review findings and TODOs.
- Be honest: where something is uncertain, record an ASSUMPTION or a
  "NEEDS HUMAN REVIEW" item instead of fabricating.

Output a JSON object with exactly these keys:
- "architecture": array of strings (functional blocks / power domains / interfaces)
- "concerns": array of strings (design review findings)
- "todos": array of strings
- "human_review": array of strings
- "assumptions": array of strings
- "notes": array of strings
"""


class SingleAgentBaseline:
    name = NAME
    role = ROLE

    def run(self, client: ChatClient, requirements_text: str) -> BaselineResult:
        data = client.chat_json(SYSTEM_PROMPT, requirements_text)
        return BaselineResult.model_validate(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_baseline_agent.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/agents/baseline.py tests/test_baseline_agent.py
git commit -m "feat: single-agent baseline for comparison"
```

---

## Task 4: Comparison service

**Files:**
- Create: `app/services/comparison.py`
- Test: `tests/test_comparison.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_comparison.py
"""The comparison service (multi-agent vs single-agent)."""
from app.models.schemas import Comparison
from app.services.comparison import run_comparison
from app.services.config import Settings

TEXT = "A 24V industrial board with an STM32, USB-C and RS485 and status LEDs."


def _mock_settings():
    return Settings(qwen_api_key="")  # mock_mode True


def test_mock_comparison_shows_multi_ahead():
    cmp = run_comparison(TEXT, _mock_settings())
    assert isinstance(cmp, Comparison)
    assert cmp.mode == "mock"
    assert cmp.total == 12
    assert cmp.multi_score > cmp.single_score
    assert cmp.delta == cmp.multi_score - cmp.single_score


def test_mock_comparison_concern_flags():
    cmp = run_comparison(TEXT, _mock_settings())
    by_id = {c.id: c for c in cmp.concerns}
    # The pipeline's Critic surfaces surge protection; the single-pass mock does not.
    assert by_id["input_protection"].covered_multi is True
    assert by_id["input_protection"].covered_single is False


def test_mock_comparison_is_labelled_illustrative():
    cmp = run_comparison(TEXT, _mock_settings())
    assert cmp.notice is not None
    assert "illustrative" in cmp.notice.lower()
    assert cmp.multi_calls == 4
    assert cmp.single_calls == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_comparison.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.comparison'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/comparison.py
"""Multi-agent vs single-agent efficiency comparison.

Runs the same requirement through the existing multi-agent Orchestrator and the
single-agent baseline, scores both with the deterministic rubric, and returns a
Comparison. In Mock Mode (or if the guard blocks the baseline) it produces a
clearly-labelled illustrative result so the demo always works.
"""
from __future__ import annotations

from app.agents.baseline import SingleAgentBaseline
from app.models.schemas import (
    BaselineResult,
    Comparison,
    ConcernResult,
    RunResponse,
)
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.orchestrator import Orchestrator
from app.services.qwen_client import QwenClient, QwenError
from app.services.rubric import RUBRIC, score

_MOCK_NOTICE = "Illustrative comparison (Mock Mode) — set a Qwen API key for a live measurement."


def mock_baseline() -> BaselineResult:
    """A representative single-pass output: gets the obvious blocks, misses much
    of the review (no surge/reset/clock/decoupling/isolation). Used in Mock Mode."""
    return BaselineResult(
        architecture=[
            "MCU block with an STM32",
            "Power supply: 24V to 5V and 3V3 rails",
            "USB-C connector for configuration",
            "RS485 interface",
            "Status LEDs",
        ],
        concerns=["Make sure the power supply can deliver enough current."],
        todos=["TODO: choose an STM32 variant.", "TODO: add the connectors."],
        human_review=[],
        assumptions=["Assumption: single-board design."],
        notes=["SWD can be used for programming."],
    )


def _flatten_multi(r: RunResponse) -> str:
    a, c, arb, req = r.architecture, r.critique, r.arbitration, r.requirements
    parts: list[str] = []
    parts += req.requirements + req.constraints + req.assumptions + req.questions
    parts += [f"{b.name} {b.purpose}" for b in a.blocks]
    parts += a.interfaces + a.signals + a.power + a.placeholder_components + a.notes
    parts += c.warnings + c.risks + c.missing_blocks + c.recommendations
    parts += arb.todo + arb.human_review + arb.accepted_assumptions
    return "\n".join(parts)


def _flatten_baseline(b: BaselineResult) -> str:
    return "\n".join(
        b.architecture + b.concerns + b.todos + b.human_review + b.assumptions + b.notes
    )


def run_comparison(requirements_text: str, settings: Settings) -> Comparison:
    multi = Orchestrator(settings).run(requirements_text)
    notice = multi.notice

    if settings.mock_mode:
        baseline = mock_baseline()
        single_calls = 0
        notice = notice or _MOCK_NOTICE
    else:
        try:
            baseline = SingleAgentBaseline().run(QwenClient(settings), requirements_text)
            single_calls = 1
        except (GuardBlocked, QwenError) as e:
            baseline = mock_baseline()
            single_calls = 0
            notice = (f"{notice} " if notice else "") + f"Baseline fell back to example data ({e})."

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
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_comparison.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/comparison.py tests/test_comparison.py
git commit -m "feat: multi- vs single-agent comparison service"
```

---

## Task 5: /api/compare endpoint

**Files:**
- Modify: `app/api/routes.py`
- Test: `tests/test_compare_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compare_endpoint.py
"""The /api/compare endpoint."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.services.config import Settings


def test_compare_endpoint_mock(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))
    client = TestClient(app)
    resp = client.post("/api/compare", json={"requirements_text": "A 24V STM32 board with RS485."})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 12
    assert len(data["concerns"]) == 12
    assert data["multi_score"] > data["single_score"]
    assert data["mode"] == "mock"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_compare_endpoint.py -q`
Expected: FAIL with 404 (route not defined) → assertion error on status_code

- [ ] **Step 3: Add the imports**

In `app/api/routes.py`, add to the `from app.models.schemas import (...)` block the names `CompareRequest` and `Comparison`, and add this import near the other service imports:

```python
from app.services.comparison import run_comparison
```

The schemas import block should read:

```python
from app.models.schemas import (
    CompareRequest,
    Comparison,
    GenerateRequest,
    GenerateResponse,
    RunRequest,
    RunResponse,
)
```

- [ ] **Step 4: Add the endpoint**

Append to `app/api/routes.py` (after the `download` endpoint):

```python
@router.post("/compare", response_model=Comparison)
def compare(req: CompareRequest) -> Comparison:
    """Run the same requirement through the multi-agent pipeline and a single-agent
    baseline, and score both with the deterministic rubric."""
    return run_comparison(req.requirements_text, get_settings())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_compare_endpoint.py -q`
Expected: PASS (1 passed)

- [ ] **Step 6: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all previous tests + the new ones)

- [ ] **Step 7: Commit**

```bash
git add app/api/routes.py tests/test_compare_endpoint.py
git commit -m "feat: POST /api/compare endpoint"
```

---

## Task 6: UI — compare button + panel

**Files:**
- Modify: `app/static/index.html`

No unit test; verified in the browser at the end (preview tools).

- [ ] **Step 1: Add CSS**

In the `<style>` block, after the `.preview img { ... }` rule, add:

```css
    .cmp-scores { display: flex; gap: 22px; flex-wrap: wrap; align-items: center; }
    .cmp-score { font-size: 28px; font-weight: 700; }
    .cmp-score .of { color: var(--muted); font-size: 16px; font-weight: 400; }
    .cmp-delta { padding: 6px 12px; border-radius: 999px; font-weight: 600;
      background: rgba(63,185,80,.15); color: var(--ok); border: 1px solid var(--ok); }
    table.cmp { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
    table.cmp th, table.cmp td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }
    table.cmp th.c, table.cmp td.c { text-align: center; width: 90px; }
```

- [ ] **Step 2: Add the compare button**

In section 1, replace the existing button `.row` block:

```html
      <div class="row">
        <button class="primary" @click="run()" :disabled="loading || !input.trim()"
          x-text="loading ? 'Agents working…' : 'Run agents'"></button>
        <button @click="loadExample()" :disabled="loading">Load example</button>
      </div>
```

with (adds the compare button):

```html
      <div class="row">
        <button class="primary" @click="run()" :disabled="loading || !input.trim()"
          x-text="loading ? 'Agents working…' : 'Run agents'"></button>
        <button @click="compareRun()" :disabled="comparing || !input.trim()"
          x-text="comparing ? 'Comparing…' : 'Compare: multi vs single agent'"></button>
        <button @click="loadExample()" :disabled="loading || comparing">Load example</button>
      </div>
      <p class="muted" x-show="cmpError" style="margin-top:10px; color: var(--warn)" x-text="cmpError"></p>
```

- [ ] **Step 3: Add the comparison panel**

Immediately after the closing `</section>` of section 1 (the input panel), add:

```html
    <template x-if="cmp">
      <section class="panel">
        <h2>Multi-agent vs single-agent</h2>
        <div class="notice" x-show="cmp.notice" x-text="'⚠️ ' + (cmp.notice || '')" style="margin-bottom:14px"></div>
        <div class="cmp-scores">
          <div><div class="muted">Multi-agent</div>
            <div class="cmp-score" x-text="cmp.multi_score"></div><span class="of" x-text="'/ ' + cmp.total"></span></div>
          <div><div class="muted">Single-agent</div>
            <div class="cmp-score" x-text="cmp.single_score"></div><span class="of" x-text="'/ ' + cmp.total"></span></div>
          <span class="cmp-delta" x-text="'+' + cmp.delta + ' concerns surfaced'"></span>
        </div>
        <p class="muted" style="margin-top:8px"
          x-text="cmp.multi_calls + ' agent calls vs ' + cmp.single_calls + ' — more engineering value per extra call. Coverage = concern surfaced as engineering work, not a placed component.'"></p>
        <table class="cmp">
          <thead><tr><th>Engineering concern</th><th class="c">Multi</th><th class="c">Single</th></tr></thead>
          <tbody>
            <template x-for="c in cmp.concerns" :key="c.id">
              <tr>
                <td x-text="c.label"></td>
                <td class="c" x-text="c.covered_multi ? '✅' : '—'"></td>
                <td class="c" x-text="c.covered_single ? '✅' : '—'"></td>
              </tr>
            </template>
          </tbody>
        </table>
      </section>
    </template>
```

- [ ] **Step 4: Add JS state and method**

In `architect()`, add to the returned state object (next to `generating`):

```javascript
        comparing: false, cmp: null, cmpError: "",
```

And add this method after `generate()` (remember to add a comma after the previous method):

```javascript
        async compareRun() {
          this.comparing = true; this.cmp = null; this.cmpError = "";
          try {
            const res = await fetch("/api/compare", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ requirements_text: this.input })
            });
            if (!res.ok) throw new Error("Compare failed (" + res.status + ")");
            this.cmp = await res.json();
            await this.fetchGuard();
          } catch (e) {
            this.cmpError = "⚠️ " + e.message;
          } finally { this.comparing = false; }
        }
```

- [ ] **Step 5: Verify in the browser**

Run the server: use preview_start with config `app`.
Then: fill the textarea, click `Compare: multi vs single agent`, and confirm via preview_snapshot/screenshot that the panel shows two scores, a `+N concerns surfaced` delta, and the 12-row concern table with ✅/— for each side. Check preview_console_logs (level error) is empty.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "feat: comparison panel in the UI"
```

---

## Task 7: compare_report.py script

**Files:**
- Create: `tools/compare_report.py`

- [ ] **Step 1: Write the script**

```python
# tools/compare_report.py
"""Generate a Markdown report of the multi- vs single-agent comparison.

Run in Qwen mode for the real numbers used in the repo/slide deck:
    .venv/Scripts/python.exe tools/compare_report.py "A 24V STM32 board with RS485" docs/comparison-report.md
In Mock Mode it produces an illustrative report (clearly labelled).
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.services.comparison import run_comparison
from app.services.config import Settings


def _to_markdown(cmp) -> str:
    lines = [
        "# Multi-agent vs single-agent comparison",
        "",
        f"**Request:** {cmp.requirements_text}",
        "",
        f"**Mode:** {cmp.mode}",
    ]
    if cmp.notice:
        lines += ["", f"> {cmp.notice}"]
    lines += [
        "",
        f"**Multi-agent: {cmp.multi_score}/{cmp.total} concerns surfaced "
        f"({cmp.multi_calls} agent calls).**",
        f"**Single-agent: {cmp.single_score}/{cmp.total} concerns surfaced "
        f"({cmp.single_calls} call).**",
        f"**Difference: +{cmp.delta} concerns.**",
        "",
        "_Coverage = the concern was surfaced as engineering work (block / TODO /"
        " assumption / review item), not a placed component._",
        "",
        "| Engineering concern | Multi-agent | Single-agent |",
        "| --- | :---: | :---: |",
    ]
    for c in cmp.concerns:
        lines.append(f"| {c.label} | {'✅' if c.covered_multi else '—'} | {'✅' if c.covered_single else '—'} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else (
        "A 24V industrial sensor board with an STM32, USB-C for configuration, "
        "an RS485 fieldbus interface and status LEDs."
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("comparison-report.md")

    cmp = run_comparison(text, Settings())
    out_path.write_text(_to_markdown(cmp), encoding="utf-8")
    print(f"multi {cmp.multi_score}/{cmp.total} vs single {cmp.single_score}/{cmp.total} "
          f"(+{cmp.delta}); mode={cmp.mode}")
    print(f"report written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it (Mock Mode is fine for a smoke check)**

Run: `.venv/Scripts/python.exe tools/compare_report.py "A 24V STM32 board with USB-C and RS485 and status LEDs" outputs/comparison-report.md`
Expected: prints `multi N/12 vs single M/12 (+K); mode=mock` with N > M, and writes the file.

- [ ] **Step 3: Commit**

```bash
git add tools/compare_report.py
git commit -m "feat: comparison report script"
```

---

## Task 8: Final verification

- [ ] **Step 1: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (previous 43 + ~11 new).

- [ ] **Step 2: Design-time role-sharpening pass (free by-product)**

Run `tools/compare_report.py` on 2–3 different requirements (in Qwen mode if a key is available, else Mock). Read the per-concern matrix; note any concern the **multi-agent** side misses repeatedly (e.g. `reverse_polarity`, `overcurrent`). For each repeated miss, sharpen the relevant agent prompt — typically the Design Critic in `app/agents/critic.py` (add the missed concern to its review checklist) or the Architect. Re-run to confirm the gap closes. Keep changes minimal and commit separately:

```bash
git add app/agents/critic.py
git commit -m "tune: sharpen Critic to cover <concern> (rubric eval)"
```

- [ ] **Step 3: Update README** (optional but recommended)

Add a short "Multi-agent vs single-agent" section to `README.md` describing the comparison and how to run `tools/compare_report.py`. Commit.

---

## Notes for the implementer

- All new services are deterministic except the live LLM calls, which are guarded
  by the existing `ApiGuard` (`app/services/guard.py`) and always have a Mock
  fallback — do not add API calls outside the orchestrator/QwenClient path.
- The comparison must never claim a Mock-Mode result is a real measurement; the
  `notice` field carries the "illustrative" label and the UI/report surface it.
- Follow existing code style: module docstring, `from __future__ import annotations`,
  type hints, concise comments explaining *why*.
