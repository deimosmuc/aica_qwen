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
    persona: str | None = Field(default=None, description="Audience persona (professional|student|maker); re-tones output.")


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
    # Concise project name (2-4 words) the agent derives from the request; used
    # as the report title when the user leaves the project-name field blank.
    title: str = ""
    requirements: list[str] = []
    constraints: list[str] = []
    questions: list[str] = []
    assumptions: list[str] = []
    confidence: float = 0.0
    clarifications: list[ClarifyingQuestion] = []

    @model_validator(mode="before")
    @classmethod
    def _sanitize_clarifications(cls, data):
        # Live Qwen occasionally returns a malformed clarifications array
        # (truncated JSON turns "options" into a string, or loose option objects
        # get promoted into the array without id/text). Salvage the well-formed
        # entries instead of letting a ValidationError crash the whole run.
        if not isinstance(data, dict):
            return data
        raw = data.get("clarifications")
        if not isinstance(raw, list):
            if raw is not None:
                data["clarifications"] = []
            return data
        cleaned = []
        for entry in raw:
            if isinstance(entry, dict):
                if not entry.get("id") or not entry.get("text"):
                    continue  # drop loose/partial objects (e.g. promoted options)
                if not isinstance(entry.get("options"), list):
                    entry["options"] = []  # coerce truncated/garbled options to empty
                cleaned.append(entry)
            else:
                cleaned.append(entry)  # already a ClarifyingQuestion model — keep as-is
        data["clarifications"] = cleaned
        return data

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
    category: Literal[
        "mcu", "sensor", "power", "connectivity", "debug", "status", "other"
    ] = "other"


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
    impedance: str | None = None  # target controlled impedance, e.g. "90 Ω diff"


class ConstraintSet(BaseModel):
    min_clearance_mm: float
    min_track_width_mm: float
    via_drill_mm: float
    via_annular_ring_mm: float


class PackageHint(BaseModel):
    component_type: str
    recommended_package: str
    reason: str


class Candidate(BaseModel):
    """One concrete part option for a decision-worthy component."""

    part: str
    package: str
    score: float = 0.0            # overall 0–5, one decimal
    recommended: bool = False
    pros: list[str] = []
    cons: list[str] = []


class DfxItem(BaseModel):
    """One Design-for-X provision: a testability / DFM / bring-up item."""

    category: Literal["testability", "dfm", "bringup"] = "dfm"
    item: str
    status: Literal["present", "recommended", "missing"] = "recommended"
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_enums(cls, data):
        # Live Qwen sometimes returns an out-of-set status/category here (e.g.
        # status "ok"/"n/a", category "manufacturing"). This single non-critical
        # field must not collapse the whole run to example data — map it onto the
        # nearest valid value instead (same salvage philosophy as the Requirements
        # clarifications sanitizer above). Unknown values fall back to the default.
        if not isinstance(data, dict):
            return data
        status_map = {
            "present": "present", "ok": "present", "done": "present", "yes": "present",
            "pass": "present", "passed": "present", "complete": "present",
            "completed": "present", "implemented": "present", "included": "present",
            "missing": "missing", "absent": "missing", "no": "missing",
            "fail": "missing", "failed": "missing", "none": "missing",
            "recommended": "recommended", "suggested": "recommended",
            "advised": "recommended", "optional": "recommended", "todo": "recommended",
            "tbd": "recommended", "na": "recommended", "n/a": "recommended",
        }
        category_map = {
            "testability": "testability", "test": "testability", "testing": "testability",
            "dft": "testability", "test-points": "testability", "testpoints": "testability",
            "dfm": "dfm", "manufacturing": "dfm", "manufacturability": "dfm",
            "assembly": "dfm", "dfa": "dfm", "production": "dfm",
            "bringup": "bringup", "bring-up": "bringup", "bring up": "bringup",
            "debug": "bringup", "commissioning": "bringup", "power-on": "bringup",
        }
        if "status" in data:
            data["status"] = status_map.get(str(data.get("status") or "").strip().lower(), "recommended")
        if "category" in data:
            data["category"] = category_map.get(str(data.get("category") or "").strip().lower(), "dfm")
        return data


class ComponentChoice(BaseModel):
    """A decision-worthy component with a recommended part plus alternatives."""

    component_type: str
    category: str = "other"
    candidates: list[Candidate] = []


class FloorplanZone(BaseModel):
    """A placement zone the renderer lays out on a coarse board grid."""

    label: str
    category: str = "other"
    blocks: list[str] = []
    placement: str = "center"     # edge|center|corner|top|bottom|left|right
    separation: list[str] = []    # zone labels/categories to keep apart


class PcbReadiness(BaseModel):
    layerstack: Literal["2-layer", "4-layer", "6-layer"]
    layerstack_reason: str
    netclasses: list[NetClass]
    constraints: ConstraintSet
    floorplan_text: str
    floorplan_ascii: str
    package_hints: list[PackageHint]
    component_choices: list[ComponentChoice] = []
    floorplan_zones: list[FloorplanZone] = []
    dfx_checklist: list[DfxItem] = []


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
    # This step's own structured output (model_dump of the agent's result for
    # THIS round), so the UI can expand "key findings" per step — including the
    # round-specific state and the PCB Critic, which has no field on RunResponse.
    findings: dict | None = None


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


# --- Streaming pipeline events (live auto-mode progress) ---------------------


class StreamEvent(BaseModel):
    """One server-sent event from the streaming pipeline.

    `stage_start` fires just before an agent begins, carrying a TraceStep with
    that agent's name/role and an empty summary (drives the live "…typing"
    bubble). `stage` fires as each agent finishes, carrying that agent's full
    TraceStep. `final` carries the complete RunResponse the non-streaming path
    returns today. `error` carries the same honest notice used by the blocking
    fallback and is always followed by a `final` event whose result is the
    example-data fallback.
    """

    type: Literal["stage_start", "stage", "final", "error"]
    step: TraceStep | None = None
    result: RunResponse | None = None
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
    architecture_svg: str | None = Field(
        default=None, description="Client-rendered light-themed ELK block diagram SVG."
    )
    project_name: str | None = Field(
        default=None, description="Optional user-chosen project name; used as the PDF "
        "report title. Blank falls back to a title auto-derived from the request.",
    )
    persona: str | None = Field(default=None, description="Audience persona for the report label.")


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

Stage = Literal["requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critic"]


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
    pcb_readiness: PcbReadiness | None = None
    persona: str | None = None


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
    pcb_critique: PcbCritique | None = None


# --- Preset Bench (cost + quality across presets) ----------------------------


class BenchRow(BaseModel):
    preset: str
    rounds: int            # review rounds actually used (1 = no rework)
    usage: RunUsage
    quality: int           # rubric coverage, 0..12
    quality_per_cent: float  # quality points per USD-cent spent (0 when cost is 0)
    best_quality: bool = False  # highest quality (tie-break: lowest cost)
    degraded: bool = False  # this preset fell back to example data (mock) — excluded from the winner


class BenchRequest(BaseModel):
    requirements_text: str


class BenchResult(BaseModel):
    requirements_text: str
    mode: Literal["mock", "qwen"]
    rows: list[BenchRow]
    takeaway: str          # one-line headline built from the best-quality row
    illustrative: bool     # True in Mock Mode (numbers are not real)
    notice: str | None = None
