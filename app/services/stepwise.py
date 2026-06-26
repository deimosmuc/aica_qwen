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

from app.agents.arbitration import ArbitrationAgent
from app.agents.architect import SystemArchitectAgent
from app.agents.critic import DesignCriticAgent
from app.agents.requirements import RequirementsAgent
from app.models.schemas import (
    Arbitration,
    Architecture,
    Critique,
    Requirements,
    StepRequest,
    StepResponse,
    TraceStep,
)
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.mock import mock_run
from app.services.qwen_client import QwenClient, QwenError

_STAGE_ORDER = ["requirements", "architecture", "critique", "arbitration"]


def _mock_step(stage: str, notice: str | None = None) -> StepResponse:
    """Return the example-data slice for a stage (Mock Mode or live fallback)."""
    mock = mock_run("")
    trace_step = mock.trace[_STAGE_ORDER.index(stage)]
    resp = StepResponse(stage=stage, mode="mock", trace_step=trace_step, notice=notice)
    setattr(resp, stage, getattr(mock, stage))
    return resp


def _trace(agent, status: str, summary: str) -> TraceStep:
    return TraceStep(agent=agent.name, role=agent.role, status=status, summary=summary)


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
            out: Requirements = RequirementsAgent().run(client, req.requirements_text)
            step = _trace(
                RequirementsAgent,
                "ok",
                f"Structured {len(out.requirements)} requirements, raised "
                f"{len(out.questions)} clarification questions (confidence {out.confidence:.0%}).",
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, requirements=out)

        if req.stage == "architecture":
            if req.requirements is None:
                raise ValueError("The architecture stage needs the approved requirements.")
            arch: Architecture = SystemArchitectAgent().run(client, req.requirements)
            step = _trace(
                SystemArchitectAgent,
                "ok",
                f"Proposed {len(arch.blocks)} functional blocks, "
                f"{len(arch.power)} power domains across hierarchical sheets.",
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, architecture=arch)

        if req.stage == "critique":
            if req.requirements is None or req.architecture is None:
                raise ValueError("The critique stage needs the approved requirements and architecture.")
            crit: Critique = DesignCriticAgent().run(client, req.requirements, req.architecture)
            n = len(crit.warnings) + len(crit.risks) + len(crit.missing_blocks)
            step = _trace(
                DesignCriticAgent,
                "warning" if n else "ok",
                f"Flagged {len(crit.warnings)} warnings, {len(crit.risks)} risks, "
                f"{len(crit.missing_blocks)} missing blocks.",
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, critique=crit)

        if req.stage == "arbitration":
            if req.requirements is None or req.architecture is None or req.critique is None:
                raise ValueError(
                    "The arbitration stage needs the approved requirements, architecture and critique."
                )
            arb: Arbitration = ArbitrationAgent().run(
                client, req.requirements, req.architecture, req.critique
            )
            step = _trace(
                ArbitrationAgent,
                "ok",
                f"Approved the architecture; logged {len(arb.todo)} TODOs and "
                f"{len(arb.human_review)} human-review items.",
            )
            return StepResponse(stage=req.stage, mode="qwen", trace_step=step, arbitration=arb)

        raise ValueError(f"Unknown stage: {req.stage}")  # pragma: no cover - guarded by schema

    except GuardBlocked as e:
        return _mock_step(req.stage, f"API limit reached ({e.reason}). Showing example data for this step.")
    except QwenError as e:
        return _mock_step(req.stage, f"Qwen was unreachable ({e}). Showing example data for this step.")
