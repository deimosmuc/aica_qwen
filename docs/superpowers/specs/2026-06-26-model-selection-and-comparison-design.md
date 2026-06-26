# Model Selection + Model Comparison — Design

**Date:** 2026-06-26
**Status:** Approved (design), pending implementation plan
**Origin:** Robert asked for low-hanging fruit before deployment. Two ideas from the
ChatGPT UI mockup: (1) switch the LLM model in the UI, (2) test a higher-tier model
and compare it against the current one. Deployment (M9) is deliberately deferred to
the end — it is delivery, not a jury-impressing feature.

## Problem / motivation

The app currently hardcodes one model (`qwen-plus`, via `Settings.qwen_model`).
The plumbing for per-call model choice already half-exists: `QwenClient.chat_json`
accepts a `model` argument, and the OpenAI-compatible DashScope endpoint serves
several models from the same key. Two cheap, high-value wins:

1. **Model switcher** — let the user run the whole pipeline on a chosen model
   (qwen-plus / qwen-max / qwen-turbo). This alone lets them eyeball a stronger
   model's output. Highest value-per-effort ("Gold", per Robert).
2. **Lean model comparison** — the existing `/compare` already scores a
   multi-agent side against a single-agent side with a deterministic 12-point
   rubric. By **parametrising the model of each existing side** (additive, no
   schema reshape) we get the headline narrative almost for free:
   **multi-agent on the cheaper qwen-plus vs a single agent on the premium
   qwen-max** — i.e. *agent collaboration beats raw model tier*. A strong
   "Agent Society" story.

An earlier, broader design (arbitrary A/B cross-product of {pipeline × model})
was rejected as too heavy for the remaining time — it required reshaping the
`Comparison` schema and UI. This design stays lean: additive fields only, reuse
the existing multi/single comparison shape, no new scoring machine.

## Scope

In scope:
- **Part 1 — Model switcher:** a curated model allowlist in config; thread an
  optional `model` through `POST /api/run` and `POST /api/step`; a model dropdown
  in the UI sent with run/step requests.
- **Part 2 — Lean comparison upgrade:** parametrise the two existing comparison
  sides with `multi_model` / `single_model`; two one-click presets in the UI
  ("Fair — same model" and "Architecture beats tier — Multi@plus vs Single@max");
  a few simple per-side metrics derived from existing data.

Explicitly **out of scope** (YAGNI):
- Arbitrary A/B cross-product (e.g. Multi@plus vs Multi@max, both multi). The
  model switcher lets a user inspect that manually; a formal both-multi
  comparison would require the rejected schema reshape.
- "Thinking" Qwen models (they don't support `json_object` output — the whole
  pipeline relies on it). The allowlist contains only json-capable models.
- Per-call cost display / token accounting in the comparison (the guard already
  tracks spend; surfacing it per side is extra plumbing, not needed for the story).

## Design

### Part 1 — Model switcher

**Config** (`app/services/config.py`):
- Add `qwen_models: list[str] = ["qwen-plus", "qwen-max", "qwen-turbo"]` — the
  curated, json-capable allowlist. `qwen_model` stays the default (`qwen-plus`).
- Add a resolver: `resolve_model(requested: str | None) -> str` returning the
  requested model when it is in `qwen_models`, otherwise the default. This makes
  an unknown/empty/malicious value degrade silently to the default (no error).

**Applying a model** is minimally invasive: rather than thread a model parameter
through every agent, build a settings copy with the chosen model and let the
existing construction use it:
`settings.model_copy(update={"qwen_model": resolve_model(model)})`. `Orchestrator`
and `QwenClient` already read `settings.qwen_model`, so this re-points the whole
pipeline at one model with no agent changes.

**Request plumbing** (`app/models/schemas.py`, `app/api/routes.py`):
- `RunRequest` and `StepRequest` gain `model: str | None = None`.
- `/run` and `/step` resolve the model and construct `Orchestrator` (or the step
  client) from the model-overridden settings. Mock mode is unaffected (no key →
  example data regardless of model).

**UI** (`app/static/index.html`):
- A `<select>` bound to a new `selectedModel` (default `qwen-plus`), populated
  from the allowlist (hardcoded in the template is acceptable; it mirrors config).
- `selectedModel` is included in the body of the run/step fetches. (The compare
  presets carry their own per-side models — see Part 2 — and do not use
  `selectedModel`.)

### Part 2 — Lean comparison upgrade

**Request** (`CompareRequest`): add `multi_model: str | None = None` and
`single_model: str | None = None`. Presets are pure UI — they just set these two
fields; the server stays generic and simply honours whatever models arrive
(resolved through `resolve_model`).

**Service** (`app/services/comparison.py`): `run_comparison` gains the two model
arguments. The multi side runs through `Orchestrator` built from settings
overridden with `multi_model`; the single side runs `SingleAgentBaseline` with a
`QwenClient` built from settings overridden with `single_model`. Each side keeps
its **existing independent guard + fallback**: if the single side's model errors
(e.g. the key lacks qwen-max access), only that side falls back to
`mock_baseline()` with a notice naming the model — the demo never breaks. The
12-point rubric scoring is unchanged.

**Schema** (`Comparison`, additive only — existing fields and the
`ConcernResult.covered_multi/covered_single` shape are untouched, so the current
UI/report/tests keep working):
- `multi_model: str` and `single_model: str` — for display.
- Simple per-side metric counts, all derived from data already present in the
  outputs (no new scoring logic):
  - `multi_blocks` / `single_blocks` — functional blocks identified.
  - `multi_findings` / `single_findings` — review findings.
  - `multi_honesty` / `single_honesty` — honesty markers (TODO / assumption /
    human-review items).

  Derivations:
  - multi (RunResponse): `blocks = len(architecture.blocks)`;
    `findings = len(critique.warnings) + len(critique.risks) + len(critique.missing_blocks)`;
    `honesty = len(arbitration.todo) + len(arbitration.human_review) + len(arbitration.accepted_assumptions)`.
  - single (BaselineResult): `blocks = len(architecture)`;
    `findings = len(concerns)`;
    `honesty = len(todos) + len(human_review) + len(assumptions)`.

**UI** (`app/static/index.html`): replace the single "Compare: multi vs single
agent" button with two preset buttons:
1. **Fair (same model)** — posts no model overrides (both default).
2. **Architecture beats tier 🏆** — posts `single_model: "qwen-max"`.

The comparison result shows each side's model name in its header plus the three
new metric numbers beside the existing rubric score, e.g.
"Multi-agent @ qwen-plus: 11/12 · 7 blocks · 9 findings" vs
"Single-agent @ qwen-max: 8/12 · 5 blocks · 2 findings".

**Report tool** (`tools/compare_report.py`): include the side model names and the
three new metrics in the generated Markdown so the deck can quote them.

## Data flow

```
/run, /step  →  resolve_model(model)  →  settings.model_copy(qwen_model=…)
             →  Orchestrator / step client  (mock mode bypasses, as today)

/compare {multi_model, single_model}
   → run_comparison(text, settings, multi_model, single_model)
        multi  = Orchestrator(settings⊕multi_model).run(text)      [guarded, own fallback]
        single = SingleAgentBaseline().run(QwenClient(settings⊕single_model), text)  [guarded, own fallback]
        score(flatten(multi)), score(flatten(single))   # unchanged rubric
        + simple counts from each output
   → Comparison(existing fields + model names + per-side counts)
```

## Error handling

- Unknown/empty `model` anywhere → `resolve_model` returns the default; no error.
- A side's model unavailable / API error → that side alone falls back to example
  data with a notice naming the model (existing per-side fallback pattern). The
  other side is unaffected.
- Guard budget reached → existing `GuardBlocked` handling (mock + clear notice).
- Mock mode (no key) → both sides illustrative as today; model names still shown
  for honesty, notice marks it illustrative.

## Testing

- `resolve_model`: returns default for unknown/empty; passes through each allowed
  model.
- Model threading: a helper that builds the model-overridden settings/QwenClient
  yields a client whose effective model equals the resolved model; an invalid
  request model resolves to the default.
- Comparison metrics: from a known mock `RunResponse` / `BaselineResult`, the
  per-side `blocks` / `findings` / `honesty` counts equal the hand-computed
  values.
- Comparison models: `run_comparison(..., single_model="qwen-max")` sets
  `single_model` on the result; mock mode still returns an illustrative comparison
  with the model names populated.
- Per-side fallback: a fake single-side client that raises `QwenError` makes only
  the single side fall back (multi side intact), with a notice mentioning the
  model.
- Existing comparison/route tests continue to pass unchanged (additive schema).

## Definition of done

- A model dropdown in the UI runs the whole pipeline on the selected model
  (verified live for at least qwen-plus and qwen-max, or gracefully reported if a
  model isn't accessible on the key).
- `/compare` honours per-side models; the "Architecture beats tier" preset runs
  Multi@plus vs Single@max and shows both models + the rubric score + the three
  simple metrics per side.
- Every path degrades gracefully (unknown model, unavailable model, guard block,
  mock mode) with honest notices.
- Tests pass with and without a live key; no unqualified production-ready claim
  introduced.
