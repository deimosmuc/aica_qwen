"""JSON contracts exchanged between the orchestrator and the agents.

Markdown is never exchanged internally — only these structured objects.
Each agent is stateless; only the orchestrator owns state.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


# --- Request -----------------------------------------------------------------


class RunRequest(BaseModel):
    requirements_text: str = Field(..., description="Natural-language hardware requirements from the user.")
    guidance: list[str] = Field(
        default=[], description="Hard user constraints (e.g. mandated parts) every agent must honor."
    )
    model: str | None = Field(
        default=None, description="Optional Qwen model override; ignored unless allow-listed."
    )
    profile: str | None = Field(default=None, description="Named run profile; overrides `model` when set.")


# --- Requirements Agent ------------------------------------------------------


class ClarifyOption(BaseModel):
    """One proposed, selectable answer to a clarifying question."""

    label: str            # short, e.g. "USB-C, 5V"
    detail: str = ""      # one-line rationale shown under the label


class ClarifyingQuestion(BaseModel):
    """An ambiguity the Requirements Agent surfaces with concrete options.
    The user picks an option / types their own / skips (keeping `assumption`)."""

    id: str
    text: str
    options: list[ClarifyOption] = []
    select: Literal["single", "multi"] = "single"
    assumption: str = ""  # what the agent assumes if the user skips


class Requirements(BaseModel):
    requirements: list[str] = []
    constraints: list[str] = []
    questions: list[str] = []
    assumptions: list[str] = []
    confidence: float = 0.0
    clarifications: list[ClarifyingQuestion] = []

    @model_validator(mode="after")
    def _backfill_questions(self):
        # Keep the legacy plain-text "Open questions" list working when only the
        # new structured clarifications are provided.
        if self.clarifications and not self.questions:
            self.questions = [c.text for c in self.clarifications]
        return self


# --- System Architect Agent --------------------------------------------------


class Block(BaseModel):
    name: str
    sheet: str
    purpose: str


class Connection(BaseModel):
    """A directed link between two blocks, used to draw the architecture diagram.
    `source`/`target` reference block names; `type` drives the connection colour."""

    source: str
    target: str
    type: Literal["power", "data", "control", "debug"] = "data"


class Architecture(BaseModel):
    blocks: list[Block] = []
    interfaces: list[str] = []
    signals: list[str] = []
    power: list[str] = []
    placeholder_components: list[str] = []
    connections: list[Connection] = []
    notes: list[str] = []


# --- Design Critic Agent -----------------------------------------------------


class Critique(BaseModel):
    warnings: list[str] = []
    risks: list[str] = []
    missing_blocks: list[str] = []
    recommendations: list[str] = []


# --- Arbitration Agent -------------------------------------------------------


class Arbitration(BaseModel):
    approved_architecture: Architecture
    todo: list[str] = []
    human_review: list[str] = []
    accepted_assumptions: list[str] = []


# --- PCB-Readiness Pack (Feature D) -----------------------------------------


class NetClass(BaseModel):
    name: str
    min_width_mm: float
    clearance_mm: float
    nets: list[str] = []


class ConstraintSet(BaseModel):
    min_clearance_mm: float
    min_track_width_mm: float
    via_drill_mm: float
    via_annular_ring_mm: float


class PackageHint(BaseModel):
    component_type: str
    recommended_package: str
    reason: str


class PcbReadiness(BaseModel):
    layerstack: Literal["2-layer", "4-layer", "6-layer"]
    layerstack_reason: str
    netclasses: list[NetClass]
    constraints: ConstraintSet
    floorplan_text: str
    floorplan_ascii: str
    package_hints: list[PackageHint]


class PcbCritique(BaseModel):
    missing_blocks: list[str] = []
    warnings: list[str] = []
    risks: list[str] = []


# --- Agent trace (what the UI visualises) ------------------------------------


class TraceStep(BaseModel):
    agent: str
    role: str
    status: Literal["ok", "warning", "skipped"] = "ok"
    summary: str
    # Wall-clock time the agent took (live mode only; None in Mock Mode).
    duration_ms: int | None = None
    # Review round this step belongs to (1 = initial; >1 = rework round).
    round: int = 1


# --- Full pipeline response --------------------------------------------------


class RunUsage(BaseModel):
    """Real token/cost totals for one pipeline run (live mode only)."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class RunResponse(BaseModel):
    mode: Literal["mock", "qwen"]
    requirements: Requirements
    architecture: Architecture
    critique: Critique
    arbitration: Arbitration
    trace: list[TraceStep]
    needs_approval: bool = True
    # Set when the API Guard blocked a live call (or Qwen was unreachable) and
    # the result fell back to example data. The UI surfaces this to the user.
    notice: str | None = None
    # Real token/cost usage for this run (None in Mock Mode).
    usage: RunUsage | None = None
    pcb_readiness: PcbReadiness | None = None


# --- Validation Agent --------------------------------------------------------


class Check(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class Validation(BaseModel):
    ok: bool = True
    checks: list[Check] = []
    # Real KiCad checks (None when kicad-cli is not available).
    kicad_cli_available: bool = False
    kicad_opens: bool | None = None
    kicad_version: str | None = None
    erc_violations: int | None = None
    erc_by_severity: dict[str, int] = {}
    notes: list[str] = []


# --- Generation (post human-approval) ----------------------------------------


class GenerateRequest(BaseModel):
    """Sent after the human approves the plan. The approved result is passed
    back so we never re-call Qwen (and never pay) just to generate files."""

    requirements_text: str = Field(..., description="The original natural-language request.")
    result: RunResponse = Field(..., description="The approved pipeline result from /api/run.")


class GenerateResponse(BaseModel):
    project_id: str
    validation: Validation
    preview_svg_url: str | None = None
    download_url: str | None = None
    report_url: str | None = None
    files: list[str] = []


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
    multi_model: str | None = None
    single_model: str | None = None


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
    # Per-side model + simple metrics (additive — existing fields unchanged).
    multi_model: str = "qwen-plus"
    single_model: str = "qwen-plus"
    multi_findings: int = 0
    single_findings: int = 0
    multi_honesty: int = 0
    single_honesty: int = 0


# --- Stepwise pipeline (one agent at a time, human sign-off between steps) ----

Stage = Literal["requirements", "architecture", "critique", "arbitration", "pcb_engineer"]


class StepRequest(BaseModel):
    """Run a single agent stage. The already-approved prior results are passed
    back so each stage has what it needs (the client owns the running state)."""

    stage: Stage
    requirements_text: str
    guidance: list[str] = []
    model: str | None = None
    profile: str | None = None
    requirements: Requirements | None = None
    architecture: Architecture | None = None
    critique: Critique | None = None
    arbitration: Arbitration | None = None


class StepResponse(BaseModel):
    stage: Stage
    mode: Literal["mock", "qwen"]
    trace_step: TraceStep
    notice: str | None = None
    # Only the field for this stage is populated.
    requirements: Requirements | None = None
    architecture: Architecture | None = None
    critique: Critique | None = None
    arbitration: Arbitration | None = None
    pcb_readiness: PcbReadiness | None = None


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
