# Design: Adaptive Clarification (Feature B)

**Date:** 2026-06-26
**Status:** Approved (brainstorming complete)
**Track relevance:** Strengthens the "AI prepares, human decides" / human-in-the-loop story of the Agent Society submission.

## Problem

Today the Requirements Agent emits `questions: list[str]` — plain-text clarification
questions. The UI only *displays* them as a passive "Open questions" bullet list
(`app/static/index.html:246`, `:319`, `:445`). They are a dead end: the user cannot
answer them, and the answers never flow back into the pipeline. Ambiguity the agent
detected is surfaced but never resolved; the downstream agents proceed on the
Requirements Agent's silent assumptions.

## Goal

Turn detected ambiguity into **agent-proposed, user-resolvable choices** (Claude-Code
style A/B/C), and feed the user's decisions back into the rest of the pipeline — without
new endpoints and without breaking the existing flow.

## Key decisions (from brainstorming)

1. **Placement:** the clarification gate sits **after the Requirements Agent**, and
   lives **only in the step-by-step interactive flow** (`/api/step`). The one-click
   `/api/run` path is unchanged — it remains the fast "trust the assumptions" route.
2. **Source of options:** **extend the Requirements Agent** to propose the options
   itself (no separate "clarifier" pass, no extra Qwen call). The agent that detects the
   gap also proposes 2–3 concrete resolutions.
3. **Answer model:** **single-select by default**; the agent may mark a question
   `multi` when several answers are legitimately combinable (e.g. "which interfaces?").
   Every question also offers a **free-text** answer and is **skippable** (skip = keep
   the agent's assumption). Nothing is forced.
4. **Feedback path:** answers ride on the **existing `guidance` field** that already
   flows through every stage. No new endpoint, no new request/response type.

## Out of scope (YAGNI)

- Clarification in the one-click `/api/run` flow (would force a two-phase split).
- Hybrid gates after every agent (Option C in brainstorming — over-engineering).
- Persistent question/answer history across runs.

## Data model (`app/models/schemas.py`, additive)

```python
class ClarifyOption(BaseModel):
    label: str            # short, selectable, e.g. "USB-C, 5V"
    detail: str = ""      # one-line rationale shown under the label

class ClarifyingQuestion(BaseModel):
    id: str               # stable id for the answer mapping, e.g. "power-source"
    text: str             # the question
    options: list[ClarifyOption] = []
    select: Literal["single", "multi"] = "single"
    assumption: str = ""  # what the agent assumes if the user skips
```

Extend `Requirements`:

```python
class Requirements(BaseModel):
    requirements: list[str] = []
    constraints: list[str] = []
    questions: list[str] = []          # kept for backward-compat (display + existing tests)
    assumptions: list[str] = []
    confidence: float = 0.0
    clarifications: list[ClarifyingQuestion] = []   # NEW — the actionable structure
```

**Backward-compat rule:** if the agent emits `clarifications` but leaves `questions`
empty, auto-populate `questions = [c.text for c in clarifications]` (so the existing
"Open questions" chip/list keep working unchanged). Done in the agent's `run()` after
validation, or via a model validator.

## Requirements Agent (`app/agents/requirements.py`)

Extend the system prompt: for each genuine ambiguity, instead of only a plain question,
emit a `clarifications` entry with:

- a short `text`,
- 2–3 `options` (each `label` + one-line `detail`),
- `select` = `"single"` (default) or `"multi"` only when answers are combinable,
- the `assumption` the agent would otherwise record.

The agent still records `assumptions` as today (the skip-fallbacks). The number of
clarifications should stay small (≈2–4) — only real, decision-changing ambiguities.

## Flow & feedback (no new endpoint)

1. `/api/step` runs the `requirements` stage → response now carries `clarifications`.
2. The UI renders a clarification card per question (see UI below).
3. On "Continue with answers", the client turns each answered question into one
   `guidance` string and **appends it to the running `guidance` list** it already owns:
   - single: `"GEKLÄRT: <text> → <chosen label>"`
   - multi: `"GEKLÄRT: <text> → <label1>, <label2>"`
   - free-text: `"GEKLÄRT: <text> → <user text>"`
   - skipped: nothing appended (the agent's `assumption` stands).
4. The next `/step` call (`architecture`) and every following stage receive that
   `guidance` via the existing `StepRequest.guidance` field — Architect, Critic and
   Arbitration already consume `guidance`. No agent signature changes.

## UI (`app/static/index.html`, Alpine.js)

After the requirements step, when `clarifications.length > 0`, render between the
requirements output and the "approve / continue to Architect" control:

- One card per question: question text, the agent's fallback assumption (muted),
  option chips (single-select radio behaviour, or multi-select toggle when
  `select === "multi"`), an "✏︎ eigene Antwort" free-text input, and a "—
  überspringen" choice.
- A small progress line: "X von Y beantwortet".
- A "Mit Antworten fortfahren →" button that builds the `guidance` entries and triggers
  the architecture step. Unanswered questions are treated as skipped.

No new page; this fits the existing single-page step flow.

## Mock mode (`app/services/mock.py`)

The mock Requirements output gains 2 scripted `clarifications` (one `single`, one
`multi`) so the whole feature is demoable **without a Qwen key**. Pick questions that fit
the existing canned example so the downstream mock stays coherent.

## Testing

- Schema: `ClarifyOption` / `ClarifyingQuestion` validate; `Requirements.clarifications`
  defaults to `[]`.
- Backward-compat: when `questions` is empty but `clarifications` is set, `questions` is
  auto-populated; existing requirements tests still pass.
- Agent (mock path): the mock Requirements emits well-formed `clarifications`
  (single + multi).
- Guidance accumulation: a small unit test on the helper that maps answered questions →
  `guidance` strings (single / multi / free-text / skipped).
- Full existing suite (91 tests) stays green.

## Risks / notes

- **Keep clarifications few.** A pipeline that asks 8 questions is worse UX than one that
  asks 2 sharp ones. The prompt must bias toward only decision-changing ambiguities.
- **Honesty:** skipped questions must visibly fall back to the stated assumption, so the
  user always knows what the agent assumed on their behalf.
- The `guidance`-string format is the contract between UI and agents; keep the `GEKLÄRT:`
  prefix consistent so it reads naturally in the agents' guidance block.
