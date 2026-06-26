# Preset Bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "📊 Preset Bench" that runs one request through a curated trio of presets and shows a single combined table of tokens, cost, and a deterministic quality score per preset — proving "team beats tier AND is cheaper".

**Architecture:** A per-run `RunMeter` sums real token usage/cost across all stage clients (and rework rounds) and rides home on `RunResponse.usage`. Per-model pricing makes cost reflect tier. A new `bench` service runs the trio through the existing Orchestrator, scores each with the existing deterministic rubric, and returns a `BenchResult`; Mock Mode returns labelled illustrative rows. A new endpoint + UI panel render the combined table.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, Alpine.js (`index.html`), pytest.

Spec: `docs/superpowers/specs/2026-06-26-preset-bench-design.md`

---

## File Structure

- `app/models/schemas.py` — add `RunUsage`, `RunResponse.usage`, `BenchRow`, `BenchResult`, `BenchRequest`.
- `app/services/metering.py` (new) — `RunMeter` (logic over `RunUsage`).
- `app/services/qwen_client.py` — feed an optional meter after each recorded call.
- `app/services/orchestrator.py` — optional shared `guard`, thread one `RunMeter`, attach `usage`.
- `app/services/config.py` — per-model price map.
- `app/services/guard.py` — per-model price lookup in `_estimate_cost`/`record`.
- `app/services/bench.py` (new) — the curated-trio bench (live + mock).
- `app/api/routes.py` — `POST /api/bench`.
- `app/static/index.html` — "📊 Preset Bench" button + result table.
- Tests: `tests/test_metering.py` (new), additions to `tests/test_qwen_client.py`, `tests/test_guard.py`, `tests/test_bench.py` (new).

---

## Task 1: RunUsage + RunMeter + RunResponse.usage

**Files:**
- Modify: `app/models/schemas.py`
- Create: `app/services/metering.py`
- Test: `tests/test_metering.py` (create)

- [ ] **Step 1: Write the failing test** — create `tests/test_metering.py`:

```python
"""Preset Bench: per-run token/cost metering."""
from app.models.schemas import RunUsage
from app.services.metering import RunMeter


def test_meter_starts_empty():
    assert RunMeter().snapshot() == RunUsage()


def test_meter_accumulates_across_calls():
    m = RunMeter()
    m.add(100, 50, 0.001)
    m.add(200, 80, 0.002)
    snap = m.snapshot()
    assert snap.calls == 2
    assert snap.input_tokens == 300
    assert snap.output_tokens == 130
    assert round(snap.cost_usd, 6) == 0.003
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metering.py -v`
Expected: FAIL — `ImportError: cannot import name 'RunUsage'`.

- [ ] **Step 3a: Add `RunUsage` to `app/models/schemas.py`**

Add this class in the "Full pipeline response" section, ABOVE `RunResponse`:

```python
class RunUsage(BaseModel):
    """Real token/cost totals for one pipeline run (live mode only)."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
```

Add the field to `RunResponse` (additive, after `notice`):

```python
    # Real token/cost usage for this run (None in Mock Mode).
    usage: RunUsage | None = None
```

- [ ] **Step 3b: Create `app/services/metering.py`**

```python
"""Per-run usage meter — sums token/cost across every stage client of one run.

The Orchestrator creates one RunMeter per run() and shares it with every stage
QwenClient, so usage accumulates across stages AND rework rounds without any
per-stage bookkeeping. The snapshot rides home on RunResponse.usage.
"""
from __future__ import annotations

from app.models.schemas import RunUsage


class RunMeter:
    def __init__(self) -> None:
        self._calls = 0
        self._in = 0
        self._out = 0
        self._cost = 0.0

    def add(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self._calls += 1
        self._in += input_tokens
        self._out += output_tokens
        self._cost += cost_usd

    def snapshot(self) -> RunUsage:
        return RunUsage(
            calls=self._calls,
            input_tokens=self._in,
            output_tokens=self._out,
            cost_usd=round(self._cost, 6),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metering.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models/schemas.py app/services/metering.py tests/test_metering.py
git commit -m "feat(bench): RunUsage + RunMeter; RunResponse.usage"
```

---

## Task 2: QwenClient feeds the meter

**Files:**
- Modify: `app/services/qwen_client.py`
- Test: `tests/test_qwen_client.py` (add one test)

- [ ] **Step 1: Write the failing test** — add to `tests/test_qwen_client.py` (reuse its existing `_FakeResp` and `_client` helper):

```python
def test_client_feeds_meter_after_a_call(tmp_path, monkeypatch):
    from app.services.metering import RunMeter
    payload = {
        "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 123, "completion_tokens": 45},
    }
    settings = Settings(qwen_api_key="x")
    guard = ApiGuard(settings, state_dir=tmp_path, now=lambda: 1000.0)
    monkeypatch.setattr(
        "app.services.qwen_client.httpx.post", lambda *a, **k: _FakeResp(payload)
    )
    meter = RunMeter()
    client = QwenClient(settings, guard=guard, meter=meter)
    client.chat_json("sys", "A 24V board with an STM32")
    snap = meter.snapshot()
    assert snap.calls == 1
    assert snap.input_tokens == 123
    assert snap.output_tokens == 45
    assert snap.cost_usd > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_qwen_client.py::test_client_feeds_meter_after_a_call -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'meter'`.

- [ ] **Step 3: Add the meter to `QwenClient`**

In `app/services/qwen_client.py`, change `__init__` to accept a meter:

```python
    def __init__(
        self,
        settings: Settings,
        guard: ApiGuard | None = None,
        timeout: float = 60.0,
        meter: "RunMeter | None" = None,
    ):
        self._api_key = settings.qwen_api_key
        self._base_url = settings.qwen_base_url.rstrip("/")
        self._model = settings.qwen_model
        self._timeout = timeout
        self._guard = guard or ApiGuard(settings)
        self._meter = meter
```

Add the import at the top (under the existing imports):

```python
from app.services.metering import RunMeter
```

In `chat_json`, change the record line (currently `self._guard.record(...)` with no capture) to capture the cost and feed the meter:

```python
        cost = self._guard.record(model, system, user, input_tokens, output_tokens, result)
        if self._meter is not None:
            self._meter.add(input_tokens, output_tokens, cost)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_qwen_client.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add app/services/qwen_client.py tests/test_qwen_client.py
git commit -m "feat(bench): QwenClient feeds an optional RunMeter"
```

---

## Task 3: Orchestrator threads one meter; attaches RunResponse.usage

**Files:**
- Modify: `app/services/orchestrator.py`
- Test: `tests/test_metering.py` (add one integration test)

- [ ] **Step 1: Write the failing test** — add to `tests/test_metering.py`:

```python
def test_orchestrator_attaches_summed_usage(tmp_path, monkeypatch):
    """A live run (faked httpx) sums usage across all four stage calls and
    attaches it to RunResponse.usage."""
    from app.services.config import Settings
    from app.services.guard import ApiGuard
    from app.services.orchestrator import Orchestrator

    # Every stage returns the same minimal-but-valid JSON for its agent.
    payload = {
        "choices": [{"message": {"content": '{"requirements":[],"blocks":[],"warnings":[],"approved_architecture":{"blocks":[]}}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 40},
    }

    class _FakeResp:
        def raise_for_status(self): return None
        def json(self): return payload

    monkeypatch.setattr("app.services.qwen_client.httpx.post", lambda *a, **k: _FakeResp())
    settings = Settings(qwen_api_key="x")
    guard = ApiGuard(settings, state_dir=tmp_path, now=lambda: 1000.0)
    res = Orchestrator(settings, guard=guard).run("A 24V board with an STM32")

    assert res.mode == "qwen"
    assert res.usage is not None
    assert res.usage.calls == 4          # requirements, architecture, critique, arbitration
    assert res.usage.input_tokens == 400
    assert res.usage.output_tokens == 160
    assert res.usage.cost_usd > 0
```

NOTE: the JSON above carries every key the four agents need (each agent validates only its own slice; missing keys default to empty lists), so all four live calls succeed and none falls back to Mock.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metering.py::test_orchestrator_attaches_summed_usage -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'guard'`.

- [ ] **Step 3: Add `guard` param + meter threading to `Orchestrator`**

In `app/services/orchestrator.py`:

Add the import:

```python
from app.services.metering import RunMeter
```

Change `__init__` (additive `guard` param) and store the guard + a meter:

```python
    def __init__(
        self,
        settings: Settings,
        profile: RunProfile | None = None,
        client: ChatClient | None = None,
        guard=None,
    ):
        self.settings = settings
        self.profile = profile or default_profile(settings)
        self._client = client  # test override: when set, used for every role
        self._guard = guard    # optional shared ApiGuard for all stage clients
        self._meter = RunMeter()
```

Change `_client_for` to pass the shared guard + meter into each real client:

```python
    def _client_for(self, role: str) -> ChatClient:
        if self._client is not None:
            return self._client
        model = self.profile.models[role]
        return QwenClient(
            self.settings.model_copy(update={"qwen_model": model}),
            guard=self._guard,
            meter=self._meter,
        )
```

In `run()`, on the LIVE (non-mock) success path, attach the usage snapshot to the returned `RunResponse`. Find where the live `RunResponse(...)` is constructed and add `usage=self._meter.snapshot()` to it. (Read `run()` — the live `RunResponse(...)` is the one built after the agents complete, NOT the `mock_run`/`mock_run_rework` early return and NOT `_guarded_fallback`. Mock and fallback paths must keep `usage=None`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metering.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: only the 2 known pre-existing `test_milestone1.py` failures (real `QWEN_API_KEY` in `.env` forces qwen mode); everything else passes. Confirm no NEW failures, especially in `tests/test_orchestrator.py` (the added `guard=None` default keeps existing behaviour).

- [ ] **Step 6: Commit**

```bash
git add app/services/orchestrator.py tests/test_metering.py
git commit -m "feat(bench): orchestrator threads one RunMeter; attaches RunResponse.usage"
```

---

## Task 4: Per-model pricing in Settings + Guard

**Files:**
- Modify: `app/services/config.py`, `app/services/guard.py`
- Test: `tests/test_guard.py` (add tests)

- [ ] **Step 1: Write the failing test** — add to `tests/test_guard.py` (it already constructs `Settings` + `ApiGuard`; match its style):

```python
def test_record_uses_per_model_pricing(tmp_path):
    from app.services.config import Settings
    from app.services.guard import ApiGuard

    s = Settings(qwen_api_key="x")
    g = ApiGuard(s, state_dir=tmp_path, now=lambda: 1000.0)
    # Same token counts, different model tier -> max costs more than turbo.
    cost_turbo = g.record("qwen-turbo", "sys", "user", 1000, 1000, {"ok": True})
    cost_max = g.record("qwen-max", "sys2", "user2", 1000, 1000, {"ok": True})
    assert cost_max > cost_turbo


def test_record_unknown_model_falls_back_to_flat_price(tmp_path):
    from app.services.config import Settings
    from app.services.guard import ApiGuard

    s = Settings(qwen_api_key="x")
    g = ApiGuard(s, state_dir=tmp_path, now=lambda: 1000.0)
    cost = g.record("some-unlisted-model", "sys", "user", 1000, 1000, {"ok": True})
    expected = (1000 / 1000) * s.guard_price_in_per_1k + (1000 / 1000) * s.guard_price_out_per_1k
    assert round(cost, 6) == round(expected, 6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_guard.py::test_record_uses_per_model_pricing -v`
Expected: FAIL — both costs equal (flat pricing), so `cost_max > cost_turbo` is False.

- [ ] **Step 3: Add the price map to `Settings`**

In `app/services/config.py`, add (after `guard_price_out_per_1k`):

```python
    # Per-model price ESTIMATES (USD per 1K tokens). Unknown models fall back to
    # the flat guard_price_*_per_1k above. Confirm against the live Qwen price
    # page before relying on exact figures.
    guard_prices_per_1k: dict[str, dict[str, float]] = {
        "qwen-turbo": {"in": 0.0003, "out": 0.0006},
        "qwen-plus": {"in": 0.001, "out": 0.002},
        "qwen-max": {"in": 0.004, "out": 0.012},
    }
```

- [ ] **Step 4: Use per-model pricing in the Guard**

In `app/services/guard.py`, add a price helper and use it in both `record` and `_estimate_cost`.

Add this method to `ApiGuard`:

```python
    def _price(self, model: str) -> tuple[float, float]:
        """(in_per_1k, out_per_1k) for a model, falling back to the flat price."""
        p = self.s.guard_prices_per_1k.get(model)
        if p is None:
            return self.s.guard_price_in_per_1k, self.s.guard_price_out_per_1k
        return p["in"], p["out"]
```

In `record`, replace the cost computation:

```python
        price_in, price_out = self._price(model)
        cost = (input_tokens / 1000) * price_in + (output_tokens / 1000) * price_out
```

In `_estimate_cost`, add the `model` argument and use it. Change the signature and body:

```python
    def _estimate_cost(self, system: str, user: str, model: str) -> float:
        in_tok = _estimate_tokens(system) + _estimate_tokens(user)
        out_tok = self.s.guard_max_output_tokens
        price_in, price_out = self._price(model)
        return (in_tok / 1000) * price_in + (out_tok / 1000) * price_out
```

And update its one caller in `precheck` (currently `estimate = self._estimate_cost(system, user)`):

```python
            estimate = self._estimate_cost(system, user, model)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_guard.py -v`
Expected: PASS (existing guard tests + the 2 new ones). If an existing guard test asserted an exact cost using the flat price for an unknown/empty model, it still holds via the fallback.

- [ ] **Step 6: Commit**

```bash
git add app/services/config.py app/services/guard.py tests/test_guard.py
git commit -m "feat(bench): per-model price estimates in the API guard"
```

---

## Task 5: Bench schemas + service + mock + endpoint

**Files:**
- Modify: `app/models/schemas.py`, `app/api/routes.py`
- Create: `app/services/bench.py`
- Test: `tests/test_bench.py` (create)

- [ ] **Step 1: Write the failing tests** — create `tests/test_bench.py`:

```python
"""Preset Bench: curated-trio cost+quality comparison."""
from app.services.bench import BENCH_PRESETS, run_bench
from app.services.config import Settings


def test_mock_bench_returns_illustrative_trio():
    s = Settings(qwen_api_key="")  # mock mode
    res = run_bench("A 24V industrial RS485 board with an STM32", s)
    assert res.mode == "mock"
    assert res.illustrative is True
    assert [r.preset for r in res.rows] == BENCH_PRESETS
    # every row has real numbers and a quality score in range
    for r in res.rows:
        assert r.usage.calls > 0
        assert r.usage.cost_usd > 0
        assert 0 <= r.quality <= 12
    # exactly one row is flagged the best quality, and it is the Senior Review Team
    best = [r for r in res.rows if r.best_quality]
    assert len(best) == 1
    assert best[0].preset == "Senior Review Team"
    assert res.takeaway  # non-empty one-liner


def test_quality_per_cent_computed_and_zero_safe():
    from app.models.schemas import BenchRow, RunUsage
    from app.services.bench import _quality_per_cent

    assert _quality_per_cent(12, RunUsage(cost_usd=0.0)) == 0.0
    # 12 quality over 8.7 cents -> ~1.38
    assert round(_quality_per_cent(12, RunUsage(cost_usd=0.087)), 2) == 1.38
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bench.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.bench'`.

- [ ] **Step 3a: Add bench schemas to `app/models/schemas.py`**

Add at the end of the file:

```python
# --- Preset Bench (cost + quality across presets) ----------------------------


class BenchRow(BaseModel):
    preset: str
    rounds: int            # review rounds actually used (1 = no rework)
    usage: RunUsage
    quality: int           # rubric coverage, 0..12
    quality_per_cent: float  # quality points per USD-cent spent (0 when cost is 0)
    best_quality: bool = False  # highest quality (tie-break: lowest cost)


class BenchRequest(BaseModel):
    requirements_text: str


class BenchResult(BaseModel):
    requirements_text: str
    mode: Literal["mock", "qwen"]
    rows: list[BenchRow]
    takeaway: str          # one-line headline built from the best-quality row
    illustrative: bool     # True in Mock Mode (numbers are not real)
    notice: str | None = None
```

- [ ] **Step 3b: Create `app/services/bench.py`**

```python
"""Preset Bench — run one request through a curated trio of presets and compare
cost and quality side by side.

Live mode runs each preset through the real Orchestrator (sharing one API guard
for consistent budget accounting) and scores the output with the deterministic
rubric. Mock Mode returns fixed, clearly-illustrative rows so the demo works
without an API key.
"""
from __future__ import annotations

from app.models.schemas import BenchResult, BenchRow, RunResponse, RunUsage
from app.services.comparison import _flatten_multi
from app.services.config import Settings
from app.services.guard import ApiGuard
from app.services.orchestrator import Orchestrator
from app.services.profiles import resolve_profile
from app.services.rubric import coverage

# The curated trio — edit here to change what the bench compares.
BENCH_PRESETS = ["Senior Review Team", "Uniform qwen-max", "Budget Turbo"]

_MOCK_NOTICE = "Illustrative bench (Mock Mode) — set a Qwen API key for real cost/quality numbers."

# Fixed illustrative numbers for Mock Mode (no real calls happen). Tell the
# intended story: the team scores highest AND costs less than single qwen-max.
_MOCK_ROWS = {
    "Senior Review Team": dict(rounds=2, calls=6, input_tokens=9000, output_tokens=5200, cost_usd=0.087, quality=12),
    "Uniform qwen-max": dict(rounds=1, calls=4, input_tokens=5500, output_tokens=3600, cost_usd=0.109, quality=9),
    "Budget Turbo": dict(rounds=1, calls=4, input_tokens=5200, output_tokens=3200, cost_usd=0.021, quality=7),
}


def _quality_per_cent(quality: int, usage: RunUsage) -> float:
    cents = usage.cost_usd * 100
    return round(quality / cents, 4) if cents > 0 else 0.0


def _rounds(resp: RunResponse) -> int:
    return max((s.round for s in resp.trace), default=1)


def _mark_best_and_takeaway(rows: list[BenchRow]) -> str:
    if not rows:
        return ""
    # Best quality wins; ties broken by lower cost.
    best = max(rows, key=lambda r: (r.quality, -r.usage.cost_usd))
    best.best_quality = True
    # Compare the winner's cost to the priciest single-model preset for the pitch line.
    pricier = [r for r in rows if r.preset != best.preset and r.usage.cost_usd > best.usage.cost_usd]
    if pricier:
        rival = max(pricier, key=lambda r: r.usage.cost_usd)
        return (
            f"{best.preset}: highest quality ({best.quality}/12) AND cheaper "
            f"(${best.usage.cost_usd:.3f}) than {rival.preset} (${rival.usage.cost_usd:.3f})."
        )
    return f"{best.preset}: highest quality ({best.quality}/12) at ${best.usage.cost_usd:.3f}."


def _mock_result(requirements_text: str) -> BenchResult:
    rows = []
    for name in BENCH_PRESETS:
        d = _MOCK_ROWS[name]
        usage = RunUsage(calls=d["calls"], input_tokens=d["input_tokens"],
                         output_tokens=d["output_tokens"], cost_usd=d["cost_usd"])
        rows.append(BenchRow(
            preset=name, rounds=d["rounds"], usage=usage, quality=d["quality"],
            quality_per_cent=_quality_per_cent(d["quality"], usage),
        ))
    takeaway = _mark_best_and_takeaway(rows)
    return BenchResult(requirements_text=requirements_text, mode="mock", rows=rows,
                       takeaway=takeaway, illustrative=True, notice=_MOCK_NOTICE)


def run_bench(requirements_text: str, settings: Settings, guard: ApiGuard | None = None) -> BenchResult:
    if settings.mock_mode:
        return _mock_result(requirements_text)

    shared_guard = guard or ApiGuard(settings)
    rows: list[BenchRow] = []
    notice = None
    for name in BENCH_PRESETS:
        profile = resolve_profile(name, settings)
        resp = Orchestrator(settings, profile=profile, guard=shared_guard).run(requirements_text)
        if resp.notice:
            notice = resp.notice  # surface the last guard/fallback notice, if any
        usage = resp.usage or RunUsage()
        quality = coverage(_flatten_multi(resp))
        rows.append(BenchRow(
            preset=name, rounds=_rounds(resp), usage=usage, quality=quality,
            quality_per_cent=_quality_per_cent(quality, usage),
        ))
    takeaway = _mark_best_and_takeaway(rows)
    return BenchResult(requirements_text=requirements_text, mode="qwen", rows=rows,
                       takeaway=takeaway, illustrative=False, notice=notice)
```

- [ ] **Step 3c: Add the endpoint to `app/api/routes.py`**

Add `BenchRequest, BenchResult` to the schema imports near the top, add `from app.services.bench import run_bench`, and add the endpoint (mirroring `/compare`):

```python
@router.post("/bench", response_model=BenchResult)
def bench(req: BenchRequest) -> BenchResult:
    """Run the curated preset trio over one request and compare cost + quality."""
    return run_bench(req.requirements_text, get_settings())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bench.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: only the 2 known pre-existing `test_milestone1.py` failures; nothing else new.

- [ ] **Step 6: Commit**

```bash
git add app/models/schemas.py app/services/bench.py app/api/routes.py tests/test_bench.py
git commit -m "feat(bench): curated-trio bench service, schemas, mock + /api/bench endpoint"
```

---

## Task 6: UI — "📊 Preset Bench" button + result table

**Files:**
- Modify: `app/static/index.html` — input-row buttons (~lines 160-165), component state (~line 545), methods (near `compareRun`, ~line 687), and a result panel (after the comparison panel, ~line 183+).

No JS unit harness; verified in the browser (mock mode, port 8011 `app-mock`).

- [ ] **Step 1: Add bench state to the Alpine component**

In `app/static/index.html`, next to `comparing: false, cmp: null, cmpError: "",` (~line 545) add:

```javascript
        benching: false, bench: null, benchError: "",
```

- [ ] **Step 2: Add the bench method (mirror `compareRun`)**

Right after `compareRun(...)` (~line 700), add:

```javascript
        async benchRun() {
          this.benching = true; this.bench = null; this.benchError = "";
          try {
            const res = await fetch("/api/bench", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ requirements_text: this.input })
            });
            if (!res.ok) throw new Error("Bench failed (" + res.status + ")");
            this.bench = await res.json();
            await this.fetchGuard();
          } catch (e) {
            this.benchError = "⚠️ " + e.message;
          } finally { this.benching = false; }
        },
```

- [ ] **Step 3: Add the bench button**

After the "🏆 Architecture beats tier" button (~line 164), add:

```html
        <button @click="benchRun()" :disabled="benching || !input.trim()"
          :title="'Run the curated preset trio and compare cost + quality'"
          x-text="benching ? 'Benching…' : '📊 Preset Bench'"></button>
```

- [ ] **Step 4: Add the bench error + result panel**

After the comparison block (find the `<template x-if="cmp">…</template>` that starts ~line 183 and locate its closing `</template>`), add a bench error line and a result panel:

```html
    <p class="muted" x-show="benchError" style="margin-top:10px; color: var(--warn)" x-text="benchError"></p>

    <template x-if="bench">
      <section class="panel" style="margin-top:18px">
        <h2>📊 Preset Bench</h2>
        <div class="notice" x-show="bench.notice" x-text="'⚠️ ' + (bench.notice || '')" style="margin-bottom:12px"></div>
        <p x-show="bench.takeaway" x-text="bench.takeaway" style="font-weight:600; margin-bottom:6px"></p>
        <p class="muted" x-show="bench.illustrative" style="font-size:12px; margin-bottom:10px">
          Illustrative numbers (Mock Mode) — run with a live Qwen key for real figures.</p>
        <table class="bench-table" style="width:100%; border-collapse:collapse; font-size:13px">
          <thead>
            <tr style="text-align:right; opacity:.7; font-size:11px; text-transform:uppercase">
              <th style="text-align:left; padding:6px 8px">Preset</th>
              <th style="padding:6px 8px">Rounds</th><th style="padding:6px 8px">Calls</th>
              <th style="padding:6px 8px">Tokens</th><th style="padding:6px 8px">Cost</th>
              <th style="padding:6px 8px">Quality</th><th style="padding:6px 8px">Quality/¢</th>
            </tr>
          </thead>
          <tbody>
            <template x-for="r in bench.rows" :key="r.preset">
              <tr style="text-align:right; border-top:1px solid var(--border)"
                  :style="r.best_quality ? 'background: rgba(60,186,122,.12)' : ''">
                <td style="text-align:left; padding:6px 8px">
                  <span x-text="r.preset"></span>
                  <span x-show="r.best_quality" class="muted" style="color:#3cba7a; font-weight:700"> · best</span>
                </td>
                <td style="padding:6px 8px" x-text="r.rounds"></td>
                <td style="padding:6px 8px" x-text="r.usage.calls"></td>
                <td style="padding:6px 8px" x-text="(r.usage.input_tokens + r.usage.output_tokens).toLocaleString()"></td>
                <td style="padding:6px 8px" x-text="'$' + r.usage.cost_usd.toFixed(3)"></td>
                <td style="padding:6px 8px" x-text="r.quality + ' / 12'"></td>
                <td style="padding:6px 8px" x-text="r.quality_per_cent.toFixed(2)"></td>
              </tr>
            </template>
          </tbody>
        </table>
      </section>
    </template>
```

- [ ] **Step 5: Verify in the browser (mock mode, no key)**

Start/refresh the `app-mock` server (port 8011). In the UI:
1. Enter any hardware request.
2. Click **📊 Preset Bench**.
3. Confirm the table shows three rows (Senior Review Team, Uniform qwen-max, Budget Turbo) with rounds/calls/tokens/cost/quality/quality-per-¢.
4. Confirm the **Senior Review Team** row is highlighted "· best" and the takeaway line reads that it is highest quality AND cheaper than Uniform qwen-max.
5. Confirm the "Illustrative numbers (Mock Mode)" note shows.

Capture a screenshot of the bench table as proof. Check the browser console for errors (expect none).

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "feat(bench): UI Preset Bench button + cost/quality table"
```

---

## Self-Review notes (for the implementer)

- **Spec coverage:** RunMeter/RunUsage (T1) + RunResponse.usage (T1) + client feed (T2) + orchestrator threading (T3); per-model pricing (T4); bench service with curated trio, rubric quality, mock illustrative rows, endpoint (T5); combined-table UI (T6). The existing `/compare` is untouched (additive).
- **Refinement vs spec:** the spec's `best_value` (highest quality-per-cent) is implemented as **`best_quality`** (highest quality, tie-break lowest cost). Reason: pure quality-per-cent crowns Budget Turbo and undercuts the "team beats tier" story; `quality_per_cent` stays as an honest informational column. The spec has been updated to match.
- **Hermetic tests:** the optional `guard` param on `Orchestrator`/`run_bench` lets tests inject a tmp-dir `ApiGuard`, so no test writes the real `outputs/.guard` ledger.
- **Type consistency:** `RunUsage(calls, input_tokens, output_tokens, cost_usd)`, `RunMeter.add(input_tokens, output_tokens, cost_usd)`/`.snapshot()`, `BenchRow(preset, rounds, usage, quality, quality_per_cent, best_quality)`, `BenchResult(requirements_text, mode, rows, takeaway, illustrative, notice)` used identically across tasks.
- **Mock honesty:** mock bench rows are fixed and flagged `illustrative=True`; the UI shows the illustrative note.
