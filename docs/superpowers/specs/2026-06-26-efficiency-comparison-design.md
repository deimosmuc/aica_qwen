# Design: Multi-Agent vs. Single-Agent Efficiency Comparison

Date: 2026-06-26
Status: Approved (design); ready for implementation plan
Author: Robert + Claude

## Purpose

The Qwen Hackathon "Agent Society" track requires a **measurable efficiency
gain vs. a single-agent baseline**, demonstrated in the project. This feature
runs the same hardware requirement through two approaches and measures, with a
**deterministic, reproducible rubric**, how many engineering concerns each one
covers — showing that division of labour plus the Critic/Arbitration review
catch measurably more than a single one-shot pass.

The framing is **quality (engineering coverage), not cost**: the multi-agent
pipeline costs more tokens but produces a more complete, reviewed scaffold. The
comparison reports that honestly (coverage as the headline, token/call counts
shown alongside).

### Altitude — stays high-level (core product philosophy)

The product deliberately does **not** place components, choose parts, or draw a
finished schematic — it prepares engineering work and keeps the human in control.
The comparison must respect this. Therefore:

- A concern counts as **covered when it is *surfaced as engineering work*** — i.e.
  raised as a functional block, a `TODO`, an `ASSUMPTION`, a `NEEDS HUMAN REVIEW`
  item, or an explicit note. **Not** when a component is placed or a value chosen.
  ("Surge protection recognised and logged as a TODO" counts; "TVS diode placed"
  is out of scope for both sides.)
- Both approaches are scored at the **same altitude**. The single-agent baseline
  is explicitly instructed to stay high-level too (scaffold + review, placeholders
  only, no part values or placement), so the comparison measures the *review
  thoroughness* difference — not a difference in how literally each one designs.

This keeps the metric aligned with the human-in-the-loop philosophy: the
multi-agent advantage is that the Critic + Arbitration *surface more concerns to
hand to the engineer*, not that they design more.

## Success criteria

- Given the same requirement, the comparison produces a coverage score for the
  multi-agent pipeline and for the single-agent baseline (e.g. "11/12 vs 6/12"),
  plus a per-concern ✅/❌ matrix and both raw outputs side by side.
- Scoring is deterministic and reproducible — no LLM grades another LLM.
- Works live in the UI **and** as a script that emits a Markdown report for the
  public repo and the slide deck.
- Honest in Mock Mode: a representative comparison is shown but clearly labelled
  "illustrative (Mock)"; the real measurable claim requires a live Qwen run.
- All Qwen calls pass through the existing ApiGuard (cost stays capped).

## Components

Each unit has one clear purpose and a small interface.

### 1. Rubric — `app/services/rubric.py`

A pure, reproducible scorer. `RUBRIC` is a fixed list of engineering concerns,
each with an id, a human label, and detection patterns. `score(text) -> dict[id, bool]`
returns which concerns a piece of text **surfaces** (case-insensitive; word-boundary
regex for short tokens like "led"/"swd" to avoid false matches). `coverage(text)`
returns the count.

"Covered" means the concern is **raised as engineering work** (block / TODO /
assumption / review item / note) in the flattened output text — not that a
component was placed. The detection terms below are the vocabulary a high-level
review uses when it *flags* a concern, not part numbers.

Initial concern set (~12, approved):

| id | label | example detection terms |
|----|-------|--------------------------|
| `input_protection` | Surge/ESD protection on power input | tvs, surge, esd, overvoltage, varistor, transient |
| `reverse_polarity` | Reverse-polarity protection | reverse polarity, ideal diode, polarity protection |
| `overcurrent` | Overcurrent / fuse protection | fuse, overcurrent, ptc, current limit, efuse |
| `power_domains` | Defined power rails / domains | rail, power domain, ldo, dc-dc, buck, regulator, +3v3, +5v |
| `decoupling` | Decoupling / filtering | decoupl, bypass, ferrite, bulk capacit, filtering |
| `debug_access` | Debug / programming access | swd, jtag, debug, swclk, swdio, programming |
| `testability` | Test points / status indication | test point, testpoint, status led, led, test pad |
| `reset` | Reset circuit | reset, nrst, power-on reset, watchdog, por |
| `clock` | Clock source | clock, crystal, oscillator, xtal, hse, lse |
| `interface_protection` | Interface isolation / termination | isolation, termination, common-mode, choke, bus protection |
| `usb_protection` | USB ESD / protection | usb esd, vbus protection, cc resistor, usb protection |
| `documentation_honesty` | Docs, assumptions, explicit uncertainty | assumption, todo, needs human review, documentation, datasheet |

The rubric and method are documented openly so the metric is auditable.

### 2. Single-agent baseline — `app/agents/baseline.py`

`SingleAgentBaseline` makes **one** competent (non-strawman) LLM call: "act as a
complete hardware engineering team; from this requirement produce the full
architecture, a design review, engineering TODOs and assumptions, in one JSON
response." The prompt explicitly instructs it to **stay high-level** — a scaffold
plus review with placeholder blocks only, no part values, no component placement,
no finished schematic — exactly the altitude the multi-agent pipeline works at, so
the comparison is fair and on-philosophy. Returns a `BaselineResult`. Stateless,
like the other agents; uses the same `ChatClient` interface and is guarded.

### 3. Comparison service — `app/services/comparison.py`

`run_comparison(requirements_text, settings) -> Comparison`:
1. Run the multi-agent pipeline via the existing `Orchestrator` → `RunResponse`.
2. Run the single-agent baseline (guarded). In Mock Mode use `mock_baseline()`.
3. Flatten each side's output to text (multi: requirements + architecture +
   critique + arbitration; single: the baseline fields).
4. Score both with the rubric.
5. Return a `Comparison` with per-concern results, the two scores, the delta,
   call counts, both structured outputs, and any mock/guard `notice`.

If the guard blocks the baseline call (or Qwen errors), fall back to the mock
baseline with a clear notice — consistent with the rest of the app.

### 4. Schemas — `app/models/schemas.py`

- `BaselineResult`: `architecture: list[str]`, `concerns: list[str]`,
  `todos: list[str]`, `human_review: list[str]`, `assumptions: list[str]`,
  `notes: list[str]`.
- `ConcernResult`: `id: str`, `label: str`, `covered_multi: bool`, `covered_single: bool`.
- `Comparison`: `requirements_text`, `mode` ("mock"|"qwen"), `concerns: list[ConcernResult]`,
  `multi_score: int`, `single_score: int`, `total: int`, `delta: int`,
  `multi_calls: int`, `single_calls: int`, `multi_output: RunResponse`,
  `single_output: BaselineResult`, `notice: str | None`.
- `CompareRequest`: `requirements_text: str`.

### 5. API — `app/api/routes.py`

`POST /api/compare` with `CompareRequest` → `Comparison`. Independent of `/api/run`
(the comparison runs its own multi-agent pass).

### 6. UI — `app/static/index.html`

A second action in the input panel: **"Compare: multi-agent vs single-agent"**.
Running it shows a dedicated comparison panel:
- two coverage bars / scores (e.g. 11/12 vs 6/12) and the delta,
- a per-concern table with ✅/❌ for each approach,
- the two outputs side by side,
- an honest footnote: call counts ("4 agent calls vs 1") = more engineering value
  per extra cost,
- the mock/guard notice when present.

The existing run → approve → generate flow is unchanged.

### 7. Script + report — `tools/compare_report.py`

Runs `run_comparison` and writes a Markdown report (path as argument; prints the
summary table and per-concern matrix). Intended to be run in Qwen mode for the
real numbers used in the repo and slide deck; in Mock Mode it prints the
illustrative comparison with the label.

## Testing (TDD)

- `tests/test_rubric.py` — text containing / missing concern terms scores
  correctly; short-token false-match guard works ("scheduled" does not match "led").
- `tests/test_baseline_agent.py` — parses a valid baseline JSON via a fake client.
- `tests/test_comparison.py` — Mock Mode comparison returns both sides, correct
  per-concern flags, scores and delta; guard-blocked baseline falls back with notice.
- `tests/test_compare_endpoint.py` — `/api/compare` in Mock Mode returns 200 with
  both scores and the concern matrix.

## Design-time use: role sharpening (free by-product)

Beyond the live comparison, the same rubric doubles as a **development eval**.
Running `tools/compare_report.py` across a few representative requirements reveals
which concerns the agents *systematically* miss; we then sharpen the relevant
agent prompts/roles (e.g. tell the Critic to always check reset/clock). This needs
no new runtime code — it is just how we use the rubric output while building. The
per-concern matrix in the report is the signal.

## Out of scope (YAGNI)

- **Runtime self-correction loop** (score → feed gaps back to the Architect →
  revise → re-score). Valuable and a natural follow-up that builds on this rubric,
  but it is a separate feature with its own spec (extra LLM calls, less
  deterministic). Explicitly deferred.
- LLM-as-judge scoring (rejected for credibility; deterministic only).
- Cost/latency as the headline metric (single agent would "win"; wrong story).
- Deep design-quality checks (signal integrity, EMC, ERC on a populated
  schematic) — V2, needs real components.
- Persisting comparison history, multiple baseline variants, A/B prompt tuning.

## Honesty notes

- Keyword detection is intentionally simple and documented; the side-by-side raw
  outputs let a human verify every ✅/❌.
- Mock Mode comparisons are labelled illustrative; the measurable claim comes
  from a live Qwen run.
- The baseline prompt is competent and fair — not a strawman — so the comparison
  reflects a real architectural difference, not a rigged prompt.
