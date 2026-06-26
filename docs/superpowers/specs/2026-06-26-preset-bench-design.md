# Design: Preset Bench — cost & quality transparency

**Date:** 2026-06-26
**Status:** Approved (brainstorming complete)
**Track relevance:** Directly strengthens the Agent-Society pitch ("collaboration beats raw model tier") with hard, side-by-side numbers — quality *and* cost per preset.

## Problem

The app can already run the multi-agent pipeline under different **run profiles**
(`app/services/profiles.py`: Uniform qwen-plus/max, Budget Turbo, Senior Review Team),
and the API Guard records the cost of every Qwen call. But that cost is swallowed into a
single aggregate ledger (`spent_usd`); it is never surfaced *per run*, *per profile*, or
*per model*. There is no way to answer "which preset gives the best quality per cent?" —
the central claim of the submission.

## Goal

A **fair head-to-head bench**: send one request through a curated trio of presets and show
a single combined table with, per preset, the tokens, cost, and a deterministic quality
score — making the cost-vs-quality trade-off visible at a glance.

## Key decisions (from brainstorming)

1. **Fair bench, not a running tally.** One request → several presets → apples-to-apples.
   (Not a cross-session history/leaderboard.)
2. **Curated trio**, defined in one place: **Senior Review Team** (plus+max, rework) vs
   **Uniform qwen-max** (expensive single tier) vs **Budget Turbo** (qwen-turbo). Tells the
   "team beats tier AND is cheaper" story in three rows; bounded cost/time.
3. **One combined table** (cost AND quality together), living in its own "📊 Bench"
   section/tab — not two separate cost/quality tabs (which would split the story).
4. **Quality = the existing deterministic rubric** (`app/services/rubric.py`,
   `coverage()` → 0..12). No extra Qwen call; auditable.
5. **Per-model pricing** so cost reflects tier (turbo < plus < max). Required for the
   "cheaper" claim to be true.

## Out of scope (YAGNI)

- Persistent cross-session run history / leaderboard.
- User-selected preset subsets (the trio is fixed in code).
- LLM-judge quality scoring (the deterministic rubric is enough and free).
- Charts/graphs — a table only.
- Replacing the existing `/compare` (multi vs single) — Bench is **additive**.

## Components

### 1. Run telemetry — `RunMeter` + `RunUsage` (additive)

`app/services/metering.py` (new):

```python
class RunUsage(BaseModel):
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

class RunMeter:
    """Accumulates token/cost usage for ONE pipeline run across all stage clients."""
    def add(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None: ...
    def snapshot(self) -> RunUsage: ...
```

- `QwenClient.__init__` gains an optional `meter: RunMeter | None = None`. After the
  existing `self._guard.record(...)` call (which already returns the call's cost), the
  client calls `meter.add(input_tokens, output_tokens, cost)` when a meter is present.
- `Orchestrator` creates **one** `RunMeter` per `run()` and passes it to every client
  built in `_client_for(role)` (`QwenClient(settings_copy, meter=self._meter)`). Because
  all stage clients share the one meter, usage sums automatically across stages **and**
  rework rounds.
- `RunResponse` gains `usage: RunUsage | None = None` (additive). The orchestrator attaches
  `self._meter.snapshot()` on live runs; Mock Mode leaves it `None`.

### 2. Per-model pricing (additive)

`Settings` gains an estimated price map, e.g.:

```python
guard_prices_per_1k: dict[str, dict[str, float]] = {
    "qwen-turbo": {"in": 0.0003, "out": 0.0006},
    "qwen-plus":  {"in": 0.001,  "out": 0.002},
    "qwen-max":   {"in": 0.004,  "out": 0.012},
}
```

(Figures are ESTIMATES — confirm against the live Qwen price page before relying on exact
numbers; the existing disclaimer already covers this.) The Guard's `record()` and
`_estimate_cost()` look up the model's price, falling back to the existing flat
`guard_price_in_per_1k` / `guard_price_out_per_1k` for unknown models so nothing breaks.

### 3. Quality score — reuse the rubric

`app/services/rubric.py` already exposes `coverage(text) -> int` (0..12) over the flattened
run output. The bench flattens a `RunResponse` to text (the same way `comparison.py` /
`compare_report.py` already do) and calls `coverage()`. No new scoring logic, no Qwen call.

### 4. Bench service — `app/services/bench.py` (new)

```python
BENCH_PRESETS = ["Senior Review Team", "Uniform qwen-max", "Budget Turbo"]  # one place to edit

class BenchRow(BaseModel):
    preset: str
    rounds: int            # review rounds actually used (from the trace)
    usage: RunUsage
    quality: int           # 0..12
    quality_per_cent: float  # quality / (cost_usd * 100), 0 when cost is 0
    best_value: bool = False

class BenchResult(BaseModel):
    requirements_text: str
    mode: Literal["mock", "qwen"]
    rows: list[BenchRow]
    takeaway: str          # one-line summary, e.g. "Senior Review Team: best quality, cheaper than Uniform qwen-max"
    illustrative: bool     # True in mock mode
    notice: str | None = None
```

- **Live mode:** for each preset, resolve the profile (`resolve_profile`), run
  `Orchestrator(settings, profile).run(requirements_text)`, read `response.usage`, score
  `coverage(flatten(response))`, derive `rounds` from `max(step.round)` in the trace.
- **Mock mode:** no real calls happen, and all presets would otherwise yield identical mock
  output — so return **fixed, hand-crafted illustrative rows** (clearly labelled) that tell
  the intended story. `illustrative=True`.
- Compute `quality_per_cent` per row; mark the row with the highest value `best_value=True`;
  build the `takeaway` string from the winner.

### 5. Endpoint

`POST /api/bench` with `{ requirements_text }` → `BenchResult`. Mirrors the existing
`/api/compare` wiring in `app/api/routes.py`.

### 6. UI (`app/static/index.html`)

A new "📊 Bench" section, reached from a button next to the existing Compare buttons. It
runs `/api/bench` on the current input and renders the combined table:

| Preset | Rounds | Calls | Tokens | Cost | Quality | Quality/Cent |

- Highlight the `best_value` row.
- Show the `takeaway` line above the table.
- Show an "illustrative numbers — run with a live key for real figures" note when
  `illustrative` is true (consistent with the existing mock-comparison labelling).
- Reuse existing panel/table styling; no charts.

## Honesty / correctness

- Mock numbers are explicitly **illustrative**; real cost/tokens only appear with a live
  key.
- Prices are **estimates** (existing disclaimer extended to the per-model map).
- Quality is the **deterministic, auditable** rubric; the raw per-agent outputs remain
  viewable so a human can verify coverage.
- A live bench runs 3 full pipelines (~14 Qwen calls, ~$0.10–0.20) — bounded by the API
  Guard's budget cap and rate limits, exactly like normal runs.

## Testing

- `RunMeter.add` / `snapshot` accumulate correctly; `RunResponse.usage` is populated on a
  live (faked-client) run and sums across rework rounds.
- Guard per-model pricing: a `qwen-max` call costs more than a `qwen-turbo` call for the
  same tokens; unknown model falls back to the flat price.
- Bench service (faked orchestrator/clients): assembles one row per preset, computes
  `quality_per_cent`, marks exactly one `best_value`, builds a non-empty `takeaway`.
- Mock bench: returns the fixed illustrative rows with `illustrative=True` and `mode="mock"`.
- `POST /api/bench` smoke test returns a well-formed `BenchResult`.
- Full existing suite stays green.

## Sequencing

Open question for the user: build this **before C** (it reinforces the pitch and the demo
video) or **after C/D**. Does not block the spec.
