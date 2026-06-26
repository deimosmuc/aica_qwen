# Agent Roster — Per-Agent Models + Review-and-Rework Loop — Design

**Date:** 2026-06-26
**Status:** Approved (design), pending implementation plan
**Builds on:** the merged `feat/model-selection` work (single-model dropdown, `Settings.resolve_model`, per-side comparison models).

## Problem / motivation

The model switcher applies ONE model to the whole pipeline. Robert wants to compose the agent team like a real engineering org: a strong **supervisor** (senior engineer) on a premium model that holds cheaper junior sub-agents to account and **demands rework**. Two capabilities follow:

1. **Per-agent models** — assign a model per agent role (e.g. Critic/Arbitration on `qwen-max`, Requirements/Architect on `qwen-plus`/`qwen-turbo`), selected via named **run profiles**.
2. **Review-and-rework loop** — after the Critic reviews the Architect's design, if it found missing blocks the design is sent back to the Architect to revise, re-reviewed, and so on up to a bounded number of rounds. This turns the linear pipeline into a visible self-correcting loop — the project's previously-deferred "self-correction loop" idea — and is the demo centrepiece ("round 1: 4 missing blocks → round 2: 0").

This is the largest feature so far: the orchestrator changes from linear to iterative.

## Scope

In scope:
- **Run profiles**: a named registry mapping each agent role → model, plus a rework flag and round cap. The previous single-model dropdown generalises into a profile selector; the old uniform behaviour survives as "Uniform qwen-plus/max/turbo" profiles.
- **Per-agent model wiring** in the orchestrator (one `QwenClient` per role via `settings.model_copy`).
- **Rework loop**: Critic → Architect, triggered by non-empty `missing_blocks`, max 2 rework rounds, early stop when no missing blocks remain.
- **Trace visibility**: each rework round emits its own Architect/Critic trace steps labelled with the round number.
- **Mock mode**: a scripted two-round rework so the demo works without a key.
- **Guard**: raise `guard_max_calls_per_run` so the loop has headroom (the $ budget stays the real cap).
- **Routes/UI**: `/run` accepts a profile; the UI offers a profile selector and shows the rounds in the trace.

Explicitly **out of scope** (YAGNI / later features):
- A brand-new dedicated "Supervisor" agent role (the existing Critic plays supervisor).
- Rework loops on stages other than Architect↔Critic (Requirements and Arbitration stay single-pass).
- Profile-vs-profile comparison (the comparison feature can adopt profiles later; not now).
- Free per-agent model configuration in the UI (presets only; manual mix is a possible later add).

## Design

### 1. Run profiles (config registry)

A profile is a small immutable record: a model per role plus loop settings.

```
RunProfile:
  name: str                  # e.g. "Senior Review Team"
  models: { requirements, architect, critic, arbitration }  # each an allow-listed model
  rework: bool               # whether the Critic→Architect loop runs
  max_rounds: int            # total review rounds, bounded (default 2 = initial + 1 rework)
```

A registry in `config.py` defines the presets:
- **Uniform qwen-plus** / **Uniform qwen-max** / **Uniform qwen-turbo** — every role the same model, `rework=False`. These reproduce today's single-model behaviour (so nothing is lost when the dropdown becomes a profile selector).
- **Senior Review Team** — requirements/architect = `qwen-plus`, critic/arbitration = `qwen-max`, `rework=True`, `max_rounds=2`. The headline profile.
- **Budget Turbo** — every role `qwen-turbo`, `rework=False`.

Every model passes through `Settings.resolve_model`, so an unknown model in any slot degrades to the default. Profiles are resolved by name; an unknown profile name falls back to a uniform-default profile.

### 2. Per-agent model wiring (orchestrator)

The orchestrator builds one client per role from the profile:
`client_for(role) = QwenClient(settings.model_copy(update={"qwen_model": profile.models[role]}))`.
Each agent is called with its role's client. The agents themselves are unchanged — they already accept a `client` and a `guidance` list.

### 3. Review-and-rework loop

Replaces the linear Architect→Critic section:

```
architecture = Architect(client_architect).run(requirements, guidance)
critique      = Critic(client_critic).run(requirements, architecture, guidance)   # round 1
round = 1
while profile.rework and critique.missing_blocks and round < profile.max_rounds:
    round += 1
    rework_guidance = guidance + [
        "Revise the architecture to address these review findings:",
        *critique.missing_blocks,
        *critique.recommendations,
    ]
    architecture = Architect(client_architect).run(requirements, rework_guidance)   # round N
    critique      = Critic(client_critic).run(requirements, architecture, rework_guidance)
arbitration = Arbitration(client_arbitration).run(requirements, architecture, critique, guidance)
```

With the default `max_rounds=2`: round 1 is the initial design+review, and at most one rework produces round 2 — matching "max 2 rounds".

- **Trigger:** non-empty `critique.missing_blocks` — the clearest "something is missing" signal. Warnings/risks are softer and would loop indefinitely, so they do not trigger rework (they still flow into the report).
- **Termination:** no missing blocks remain, or `max_rounds` (default 2) reached. Whichever first.
- The Critic's findings are fed back through the **existing `guidance` mechanism** — no new agent plumbing.

### 4. Trace visibility

`TraceStep` gains an additive `round: int = 1` field. Each rework iteration appends Architect and Critic steps with their round number; the UI renders "System Architect · round 2", "Design Critic · round 2", etc. The summary notes the change ("addressed 3 of 4 missing blocks; 1 remaining"). Arbitration appears once at the end. This makes the self-correction visible — the demo's whole point.

### 5. Mock mode (scripted rework)

When a profile has `rework=True`, mock mode returns a **scripted two-round** example: round 1's architecture omits a couple of blocks and the Critic flags them in `missing_blocks`; round 2's architecture includes them and the Critic returns empty `missing_blocks`. The trace shows both rounds. This keeps the "demo always works without a key" principle while still demonstrating self-correction. When `rework=False`, mock mode is the existing single-pass `mock_run`.

### 6. Cost / guard

Worst case with `max_rounds=2`: Requirements + (Architect+Critic)×2 + Arbitration = 6 calls. The loop is bounded **structurally by `max_rounds`** — it cannot run away regardless of what the Critic returns. The real cost backstops are the guard's **per-minute rate limit (15)** and the **$5 budget cap** (both enforced in `ApiGuard`). Note: `guard_max_calls_per_run` exists in config but is **not currently wired into `ApiGuard`** — do not rely on it as the loop's safety mechanism (the structural `max_rounds` bound + rate limit + budget are what actually protect cost). If the guard blocks mid-loop, the existing graceful fallback applies (the run falls back to example data with an honest notice).

### 7. Routes / UI

- `RunRequest` gains `profile: str | None`. If present it selects the named profile; otherwise the existing `model` field (uniform) or the default profile applies. `profile` takes precedence over `model`.
- `/step` keeps the single-`model` behaviour (the step-by-step flow stays single-pass and single-model — the rework loop is an auto-run concept; surfacing it per-step is out of scope).
- UI: the model dropdown becomes a **profile selector** populated from the registry. The trace panel shows the round labels. The "Senior Review Team" profile is the one to demo.

## Data flow

```
/run {profile?, model?}
  → resolve profile (named registry, or uniform from `model`, or default)
  → Orchestrator(settings, profile)
       client per role = QwenClient(settings.model_copy(qwen_model = profile.models[role]))
       Requirements → [Architect ⇄ Critic loop until no missing_blocks or max rounds] → Arbitration
       trace steps carry round numbers
  → RunResponse (+ multi-round trace)
  (mock mode: scripted single-pass or two-round example by profile.rework)
```

## Error handling

- Unknown profile name → uniform-default profile; unknown model in any slot → `resolve_model` default. No errors surface to the user.
- Guard block / Qwen error mid-loop → existing `_guarded_fallback` returns example data with an honest notice (no partial-charge surprises).
- A rework round that still leaves missing blocks after the cap → stop and proceed to Arbitration with the best result; the remaining gaps flow into TODO/human-review as today (honest, not hidden).
- Mock mode never calls the network regardless of profile.

## Testing

- Profile registry: each preset resolves; unknown profile → default; unknown model slot → `resolve_model` default.
- Orchestrator wiring (with a fake client capturing the model per role): the right model reaches each agent for a given profile.
- Rework loop (fake Critic returning missing_blocks on round 1, empty on round 2): the Architect is re-invoked exactly once, the loop stops, and the trace contains round-2 steps. A fake Critic that always returns missing_blocks stops at `max_rounds` (no infinite loop).
- Rework disabled: behaves exactly like today (single pass, no extra trace steps).
- Mock mode with a rework profile: returns the scripted two-round example; with a non-rework profile: returns the existing single-pass mock.
- Guard cap respected: the worst-case call count stays within `guard_max_calls_per_run`.
- Existing run/step/comparison tests still pass (additive `round` field; profile optional).

## Definition of done

- A profile selector in the UI runs the pipeline with per-agent models; "Senior Review Team" runs the Critic/Arbitration on qwen-max and the others on qwen-plus.
- With rework enabled, the Critic sends a design with missing blocks back to the Architect, and the trace visibly shows the rounds and the shrinking gap; the loop is bounded at 2 rounds.
- Every path degrades gracefully (unknown profile/model, guard block, mock mode) with honest notices; mock mode demonstrates the rework rounds without a key.
- Tests pass with and without a live key; no unqualified production-ready claim introduced.
