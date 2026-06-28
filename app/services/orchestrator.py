"""Orchestrator — owns all state and runs agents in sequence.

Agents never talk to each other directly. The orchestrator calls each agent,
holds the resulting JSON, and passes what is needed to the next one. Each stage
runs on the model assigned by the active RunProfile, so a senior supervisor can
run on a stronger model than the junior sub-agents.
"""
from __future__ import annotations

from time import perf_counter

from pydantic import ValidationError

from app.agents.arbitration import ArbitrationAgent
from app.agents.architect import SystemArchitectAgent
from app.agents.base import ChatClient
from app.agents.critic import DesignCriticAgent
from app.agents.pcb_critic import PcbCriticAgent
from app.agents.pcb_engineer import PcbEngineerAgent
from app.agents.requirements import RequirementsAgent
from app.models.schemas import (
    Arbitration, Architecture, Critique, PcbCritique, PcbReadiness, Requirements,
    RunResponse, StreamEvent, TraceStep,
)
from app.services.config import Settings
from app.services.guard import ApiGuard, GuardBlocked
from app.services.metering import RunMeter
from app.services.mock import mock_run, mock_run_rework
from app.services.profiles import RunProfile, default_profile
from app.services.qwen_client import QwenClient, QwenError, QwenTruncatedError


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        profile: RunProfile | None = None,
        client: ChatClient | None = None,
        guard: ApiGuard | None = None,
    ):
        self.settings = settings
        self.profile = profile or default_profile(settings)
        self._client = client  # test override: when set, used for every role
        self._guard = guard    # optional shared ApiGuard for all stage clients
        self._meter = RunMeter()

    def _client_for(self, role: str) -> ChatClient:
        if self._client is not None:
            return self._client
        model = self.profile.models[role]
        return QwenClient(
            self.settings.model_copy(update={"qwen_model": model}),
            guard=self._guard,
            meter=self._meter,
        )

    @staticmethod
    def _arch_step(architecture: Architecture, round_no: int, ms: int) -> TraceStep:
        if round_no == 1:
            summary = (
                f"Live Qwen: proposed {len(architecture.blocks)} functional blocks, "
                f"{len(architecture.power)} power domains across hierarchical sheets."
            )
        else:
            summary = (
                f"Live Qwen (rework round {round_no}): revised the architecture to "
                f"{len(architecture.blocks)} blocks addressing the critic's findings."
            )
        return TraceStep(
            agent=SystemArchitectAgent.name, role=SystemArchitectAgent.role,
            status="ok", duration_ms=ms, round=round_no, summary=summary,
        )

    @staticmethod
    def _critic_step(critique: Critique, round_no: int, ms: int) -> TraceStep:
        n = len(critique.warnings) + len(critique.risks) + len(critique.missing_blocks)
        return TraceStep(
            agent=DesignCriticAgent.name, role=DesignCriticAgent.role,
            status="warning" if n else "ok", duration_ms=ms, round=round_no,
            summary=(
                f"Live Qwen (round {round_no}): flagged {len(critique.warnings)} warnings, "
                f"{len(critique.risks)} risks, {len(critique.missing_blocks)} missing blocks."
            ),
        )

    @staticmethod
    def _pcb_step(pcb: PcbReadiness, round_no: int, ms: int) -> TraceStep:
        return TraceStep(
            agent=PcbEngineerAgent.name, role=PcbEngineerAgent.role,
            status="ok", duration_ms=ms, round=round_no,
            summary=(
                f"Live Qwen (round {round_no}): {pcb.layerstack}, "
                f"{len(pcb.netclasses)} net classes, "
                f"{len(pcb.package_hints)} package hints."
            ),
        )

    @staticmethod
    def _pcb_critic_step(critique: PcbCritique, round_no: int, ms: int) -> TraceStep:
        n = len(critique.missing_blocks) + len(critique.warnings) + len(critique.risks)
        return TraceStep(
            agent=PcbCriticAgent.name, role=PcbCriticAgent.role,
            status="warning" if n else "ok", duration_ms=ms, round=round_no,
            summary=(
                f"Live Qwen (round {round_no}): "
                f"{len(critique.missing_blocks)} must-fix, "
                f"{len(critique.warnings)} warnings, "
                f"{len(critique.risks)} risks."
            ),
        )

    def _design_and_review_stream(self, requirements: Requirements, guidance: list[str]):
        """Design + review with optional Critic->Architect rework. Yields one
        StreamEvent per finished step; returns (architecture, critique, steps)."""
        steps: list[TraceStep] = []
        t = perf_counter()
        architecture = SystemArchitectAgent().run(self._client_for("architecture"), requirements, guidance)
        step = self._arch_step(architecture, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)
        t = perf_counter()
        critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, guidance)
        step = self._critic_step(critique, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)

        round_no = 1
        while self.profile.rework and critique.missing_blocks and round_no < self.profile.max_rounds:
            round_no += 1
            rework_guidance = guidance + [
                "Revise the architecture to address these review findings:",
                *critique.missing_blocks,
                *critique.recommendations,
            ]
            t = perf_counter()
            architecture = SystemArchitectAgent().run(self._client_for("architecture"), requirements, rework_guidance)
            step = self._arch_step(architecture, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)
            t = perf_counter()
            critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, rework_guidance)
            step = self._critic_step(critique, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)

        return architecture, critique, steps

    def _pcb_design_and_review_stream(self, requirements, architecture, arbitration, guidance: list[str]):
        """PCB Engineer + PCB Critic rework loop. Yields one StreamEvent per
        finished step; returns (pcb, pcb_critique, steps)."""
        steps: list[TraceStep] = []
        t = perf_counter()
        pcb = PcbEngineerAgent().run(self._client_for("pcb_engineer"), requirements, architecture, arbitration, guidance)
        step = self._pcb_step(pcb, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)
        t = perf_counter()
        pcb_critique = PcbCriticAgent().run(self._client_for("pcb_critique"), requirements, pcb, guidance)
        step = self._pcb_critic_step(pcb_critique, 1, int((perf_counter() - t) * 1000))
        steps.append(step); yield StreamEvent(type="stage", step=step)

        round_no = 1
        while self.profile.rework and pcb_critique.missing_blocks and round_no < self.profile.max_rounds:
            round_no += 1
            rework_guidance = guidance + [
                "Revise the PCB recommendations to address these review findings:",
                *pcb_critique.missing_blocks,
            ]
            t = perf_counter()
            pcb = PcbEngineerAgent().run(self._client_for("pcb_engineer"), requirements, architecture, arbitration, rework_guidance)
            step = self._pcb_step(pcb, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)
            t = perf_counter()
            pcb_critique = PcbCriticAgent().run(self._client_for("pcb_critique"), requirements, pcb, rework_guidance)
            step = self._pcb_critic_step(pcb_critique, round_no, int((perf_counter() - t) * 1000))
            steps.append(step); yield StreamEvent(type="stage", step=step)

        return pcb, pcb_critique, steps

    def run_stream(self, requirements_text: str, guidance: list[str] | None = None):
        """Stream the pipeline: one `stage` StreamEvent per finished agent, then
        a single `final` event with the full RunResponse. On a guard/Qwen/
        validation failure, emit an `error` event then a `final` with the
        example-data fallback (same honest degradation as the blocking path)."""
        self._meter = RunMeter()
        if self.settings.mock_mode:
            result = mock_run_rework(requirements_text) if self.profile.rework else mock_run(requirements_text)
            for step in result.trace:
                yield StreamEvent(type="stage", step=step)
            yield StreamEvent(type="final", result=result)
            return

        guidance = guidance or []
        steps: list[TraceStep] = []
        try:
            t = perf_counter()
            requirements = RequirementsAgent().run(self._client_for("requirements"), requirements_text, guidance)
            req_step = TraceStep(
                agent=RequirementsAgent.name, role=RequirementsAgent.role, status="ok",
                duration_ms=int((perf_counter() - t) * 1000),
                summary=(
                    f"Live Qwen: structured {len(requirements.requirements)} requirements, "
                    f"raised {len(requirements.questions)} clarification questions "
                    f"(confidence {requirements.confidence:.0%})."
                ),
            )
            steps.append(req_step); yield StreamEvent(type="stage", step=req_step)

            architecture, critique, design_steps = yield from self._design_and_review_stream(requirements, guidance)
            steps.extend(design_steps)

            t = perf_counter()
            arbitration = ArbitrationAgent().run(self._client_for("arbitration"), requirements, architecture, critique, guidance)
            arb_step = TraceStep(
                agent=ArbitrationAgent.name, role=ArbitrationAgent.role, status="ok",
                duration_ms=int((perf_counter() - t) * 1000),
                summary=(
                    f"Live Qwen: approved the architecture; logged {len(arbitration.todo)} TODOs "
                    f"and {len(arbitration.human_review)} human-review items."
                ),
            )
            steps.append(arb_step); yield StreamEvent(type="stage", step=arb_step)

            pcb, pcb_critique, pcb_steps = yield from self._pcb_design_and_review_stream(
                requirements, architecture, arbitration, guidance)
            steps.extend(pcb_steps)
        except GuardBlocked as e:
            yield from self._error_then_fallback(
                requirements_text, f"API limit reached ({e.reason}). Showing example data instead — no charge.")
            return
        except QwenTruncatedError as e:
            yield from self._error_then_fallback(
                requirements_text,
                f"Qwen's answer was cut off ({e}). Showing example data instead — "
                "try a simpler request or raise GUARD_MAX_OUTPUT_TOKENS.")
            return
        except QwenError as e:
            yield from self._error_then_fallback(
                requirements_text, f"Qwen was unreachable ({e}). Showing example data instead.")
            return
        except ValidationError as e:
            yield from self._error_then_fallback(
                requirements_text,
                f"Qwen returned a malformed answer ({e.error_count()} field error(s)). "
                "Showing example data instead.")
            return

        result = RunResponse(
            mode="qwen", requirements=requirements, architecture=architecture,
            critique=critique, arbitration=arbitration, pcb_readiness=pcb,
            trace=steps, needs_approval=True, usage=self._meter.snapshot(),
        )
        yield StreamEvent(type="final", result=result)

    def _error_then_fallback(self, requirements_text: str, notice: str):
        result = mock_run(requirements_text)
        result.notice = notice
        yield StreamEvent(type="error", notice=notice)
        yield StreamEvent(type="final", result=result)

    def run(self, requirements_text: str, guidance: list[str] | None = None) -> RunResponse:
        """Blocking pipeline — drains run_stream() and returns the final result.
        Kept for /api/run, comparison, bench and the existing test-suite."""
        result: RunResponse | None = None
        for event in self.run_stream(requirements_text, guidance):
            if event.type == "final":
                result = event.result
        assert result is not None  # run_stream always ends with a final event
        return result
