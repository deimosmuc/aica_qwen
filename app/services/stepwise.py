"""Stepwise pipeline — run one agent stage at a time for human sign-off.

The full multi-agent run lives in the Orchestrator. This module exposes the same
agents one stage at a time so the UI can stop after each agent, show its output,
and wait for the user to approve / re-run / stop. The client owns the running
state and passes the approved prior results back into each call.

Every live stage goes through the same guarded QwenClient as the rest of the app;
on a guard block or Qwen error a stage falls back to the example data for that
stage (with a notice), so the demo never breaks. In Mock Mode every stage simply
returns its slice of the prepared example pipeline.
"""
from __future__ import annotations

from time import perf_counter

from app.agents.arbitration import ArbitrationAgent
from app.agents.architect import SystemArchitectAgent
from app.agents.critic import DesignCriticAgent
from app.agents.pcb_critic import PcbCriticAgent
from app.agents.pcb_engineer import PcbEngineerAgent
from app.agents.requirements import RequirementsAgent
from app.models.schemas import (
    Arbitration,
    Architecture,
    Critique,
    PcbCritique,
    PcbReadiness,
    Requirements,
    StepRequest,
    StepResponse,
    TraceStep,
)
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.mock import mock_run
from app.services.qwen_client import QwenClient, QwenError

_STAGE_ORDER = ["requirements", "architecture", "critique", "arbitration", "pcb_engineer"]


def _mock_step(stage: str, notice: str | None = None) -> StepResponse:
    """Return the example-data slice for a stage (Mock Mode or live fallback)."""
    mock = mock_run("")
    trace_step = mock.trace[_STAGE_ORDER.index(stage)]
    resp = StepResponse(stage=stage, mode="mock", trace_step=trace_step, notice=notice)
    # pcb_engineer stage maps to pcb_readiness on RunResponse
    field = "pcb_readiness" if stage == "pcb_engineer" else stage
    setattr(resp, field, getattr(mock, field))
    return resp


def _trace(agent, status: str, summary: str, duration_ms: int | None = None) -> TraceStep:
    return TraceStep(
        agent=agent.name, role=agent.role, status=status, summary=summary, duration_ms=duration_ms
    )


def run_stage(req: StepRequest, settings: Settings) -> StepResponse:
    """Run a single agent stage and return its output plus a trace step.

    Raises ValueError if a required prior result is missing (the endpoint maps
    this to HTTP 400).
    """
    if settings.mock_mode:
        return _mock_step(req.stage)

    client = QwenClient(settings)
    try:
        if req.stage == "requirements":
            t = perf_counter()
            out: Requirements = RequirementsAgent().run(client, req.requirements_text, req.guidance)
            ms = int((perf_counter() - t) * 1000)
            step = _trace(
                RequirementsAgent,
                "ok",
                f"Structured {len(out.requirements)} requirements, raised "
                f"{len(out.questions)} clarification questions (confidence {out.confidence:.0%}).",
                ms,
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, requirements=out)

        if req.stage == "architecture":
            if req.requirements is None:
                raise ValueError("The architecture stage needs the approved requirements.")
            t = perf_counter()
            arch: Architecture = SystemArchitectAgent().run(client, req.requirements, req.guidance)
            ms = int((perf_counter() - t) * 1000)
            step = _trace(
                SystemArchitectAgent,
                "ok",
                f"Proposed {len(arch.blocks)} functional blocks, "
                f"{len(arch.power)} power domains across hierarchical sheets.",
                ms,
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, architecture=arch)

        if req.stage == "critique":
            if req.requirements is None or req.architecture is None:
                raise ValueError("The critique stage needs the approved requirements and architecture.")
            t = perf_counter()
            crit: Critique = DesignCriticAgent().run(
                client, req.requirements, req.architecture, req.guidance
            )
            ms = int((perf_counter() - t) * 1000)
            n = len(crit.warnings) + len(crit.risks) + len(crit.missing_blocks)
            step = _trace(
                DesignCriticAgent,
                "warning" if n else "ok",
                f"Flagged {len(crit.warnings)} warnings, {len(crit.risks)} risks, "
                f"{len(crit.missing_blocks)} missing blocks.",
                ms,
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, critique=crit)

        if req.stage == "arbitration":
            if req.requirements is None or req.architecture is None or req.critique is None:
                raise ValueError(
                    "The arbitration stage needs the approved requirements, architecture and critique."
                )
            t = perf_counter()
            arb: Arbitration = ArbitrationAgent().run(
                client, req.requirements, req.architecture, req.critique, req.guidance
            )
            ms = int((perf_counter() - t) * 1000)
            step = _trace(
                ArbitrationAgent,
                "ok",
                f"Approved the architecture; logged {len(arb.todo)} TODOs and "
                f"{len(arb.human_review)} human-review items.",
                ms,
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, arbitration=arb)

        if req.stage == "pcb_engineer":
            if req.requirements is None or req.architecture is None or req.arbitration is None:
                raise ValueError(
                    "The pcb_engineer stage needs the approved requirements, architecture and arbitration."
                )
            t = perf_counter()
            pcb: PcbReadiness = PcbEngineerAgent().run(
                client, req.requirements, req.architecture, req.arbitration, req.guidance
            )
            ms = int((perf_counter() - t) * 1000)
            step = _trace(
                PcbEngineerAgent,
                "ok",
                f"{pcb.layerstack} recommended. "
                f"{len(pcb.netclasses)} net classes, {len(pcb.package_hints)} package hints.",
                ms,
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, pcb_readiness=pcb)

        raise ValueError(f"Unknown stage: {req.stage}")  # pragma: no cover - guarded by schema

    except GuardBlocked as e:
        return _mock_step(req.stage, f"API limit reached ({e.reason}). Showing example data for this step.")
    except QwenError as e:
        return _mock_step(req.stage, f"Qwen was unreachable ({e}). Showing example data for this step.")
