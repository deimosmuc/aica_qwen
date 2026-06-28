# User Persona Selector (Design Spec)

**Date:** 2026-06-28
**Status:** Approved in brainstorming, pending written-spec review.
**Track:** Polish (from the polish-backlog: persona input). This is **Run B**.

## Summary

A "who are you?" selector at project-input time with three personas — **Professional**
(default), **Student**, **Maker** — that adapts the tone, level of detail, and
recommendations across **all** agent outputs. The persona is a single instruction
string threaded through the existing `guidance` channel, so every agent honours it
without any signature change. The effect is **live-Qwen only** (Mock-Mode fixtures stay
fixed); a visible persona label shows the chosen role in the UI and the report.

## Goals

- One new input field that meaningfully re-tones the whole pipeline in live mode.
- Zero change to agent `run()` signatures — reuse the `guidance` thread.
- Honest in Mock Mode: output unchanged, but the chosen persona is clearly labelled.
- English-only output (project directive).

## Non-goals / out of scope

- No persona-specific Mock fixtures (persona is a live-only enrichment).
- No per-agent individual persona texts — one shared instruction string per persona.
- No forced selection (Professional is preselected).
- No light theme / unrelated UI work.

## Locked design decisions (from brainstorming)

- **Personas:** `professional` (default), `student`, `maker`.
- **Mock behaviour:** live-only effect + a visible persona label (chosen over 3× fixtures
  or a single persona-tuned sentence).
- **Default:** Professional preselected (matches the engineer-facing tool; not forced).
- **Mechanism:** map persona → instruction string, **prepend to the `guidance` list**
  server-side before calling the orchestrator / `run_stage`. Not shown in the UI's
  "Active constraints (honored by every agent)" list — surfaced as its own label.

## Data model & module

New `app/services/persona.py` (single source of truth, pure, testable):

```python
Persona = Literal["professional", "student", "maker"]

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

PERSONA_LABELS = {"professional": "Professional", "student": "Student", "maker": "Maker"}

def resolve_persona(p: str | None) -> str:      # unknown / None -> "professional"
def persona_instruction(p: str | None) -> str:  # the instruction for the resolved persona
def persona_label(p: str | None) -> str:        # display label for the resolved persona
```

Schema: `RunRequest`, `StepRequest`, `GenerateRequest` each gain
`persona: str | None = None` (default resolves to `professional`).

## Threading

- **`routes.py /run`:** `guidance = [persona_instruction(req.persona)] + req.guidance`,
  pass to `Orchestrator.run(...)`. (Mock ignores guidance → output unchanged; live agents
  honour it.)
- **`routes.py /step`:** same prepend before `run_stage(req, settings)` — set
  `req.guidance = [persona_instruction(req.persona)] + req.guidance` (or pass a merged copy).
- No change to agent `run()` signatures or to the orchestrator/stepwise internals beyond
  receiving the already-merged guidance.
- The prepend happens server-side only; the client's displayed guidance (the user's own
  constraints) is untouched, so the persona does not appear in "Active constraints".

## UI (`app/static/index.html`)

- A persona selector near the project-input controls (alongside the profile selector),
  default **Professional**. State field `persona: "professional"`; sent as `persona` in the
  `/run`, `/step`, and `/generate` request bodies.
- A small label/chip at the result header: `Audience: {persona_label}`. Shown in both
  auto-run and step modes. English label.
- Reset in `_resetRun()` is not required (persona persists across runs like the profile),
  but the field is initialised to `professional`.

## Report (`app/generators/report.py`, `report.html.j2`)

- `GenerateRequest.persona` flows into `generate_report_pdf(..., persona=...)` →
  `_report_context` adds `"persona_label"`; the template renders an "Audience: {label}"
  line in the report meta. In live mode the agent content is already persona-toned; the
  label makes the lens explicit. Omitted/neutral when not provided.

## Graceful degradation
- Missing / unknown persona → `resolve_persona` returns `professional`; never raises.
- Mock Mode: fixtures unchanged; the label still renders from the persona field.
- Empty guidance + persona → guidance becomes just the persona instruction.

## Testing strategy
- **persona.py:** `resolve_persona` maps known values and falls back to `professional`;
  `persona_instruction` / `persona_label` return the right strings; unknown → professional.
- **routes:** `/run` and `/step` prepend the persona instruction to the guidance passed
  downstream (capture the orchestrator/run_stage guidance; assert the persona line is first
  and the user's constraints follow). A non-default persona (e.g. `student`) injects the
  student instruction.
- **report:** `_report_context` exposes `persona_label`; the template renders
  "Audience: Student" for `persona="student"`.
- **GUI (browser):** the selector defaults to Professional and the chosen persona is sent
  in the `/run` body; the result header shows the label. (No pytest for index.html.)
- WeasyPrint render stays skip-on-missing-libs.

## Affected files
- `app/services/persona.py` (new) — persona map + resolvers.
- `app/models/schemas.py` — `persona` on RunRequest / StepRequest / GenerateRequest.
- `app/api/routes.py` — prepend persona instruction to guidance in `/run` and `/step`;
  pass persona to `generate_report_pdf` in `/generate`.
- `app/generators/report.py`, `app/templates/report.html.j2` — persona label.
- `app/static/index.html` — selector + result-header label; send `persona` in the three
  request bodies.
- `tests/` — `test_persona.py` (new), `test_run_endpoint.py`, `test_report.py`.
