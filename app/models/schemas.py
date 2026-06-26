"""JSON contracts exchanged between the orchestrator and the agents.

Markdown is never exchanged internally — only these structured objects.
Each agent is stateless; only the orchestrator owns state.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Request -----------------------------------------------------------------


class RunRequest(BaseModel):
    requirements_text: str = Field(..., description="Natural-language hardware requirements from the user.")
    guidance: list[str] = Field(
        default=[], description="Hard user constraints (e.g. mandated parts) every agent must honor."
    )
    model: str | None = Field(
        default=None, description="Optional Qwen model override; ignored unless allow-listed."
    )


# --- Requirements Agent ------------------------------------------------------


class Requirements(BaseModel):
    requirements: list[str] = []
    constraints: list[str] = []
    questions: list[str] = []
    assumptions: list[str] = []
    confidence: float = 0.0


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


# --- Agent trace (what the UI visualises) ------------------------------------


class TraceStep(BaseModel):
    agent: str
    role: str
    status: Literal["ok", "warning", "skipped"] = "ok"
    summary: str
    # Wall-clock time the agent took (live mode only; None in Mock Mode).
    duration_ms: int | None = None


# --- Full pipeline response --------------------------------------------------


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


# --- Stepwise pipeline (one agent at a time, human sign-off between steps) ----

Stage = Literal["requirements", "architecture", "critique", "arbitration"]


class StepRequest(BaseModel):
    """Run a single agent stage. The already-approved prior results are passed
    back so each stage has what it needs (the client owns the running state)."""

    stage: Stage
    requirements_text: str
    guidance: list[str] = []
    model: str | None = None
    requirements: Requirements | None = None
    architecture: Architecture | None = None
    critique: Critique | None = None


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
