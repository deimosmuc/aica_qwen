"""Orchestrator — owns all state and runs agents in sequence.

Agents never talk to each other directly. The orchestrator calls each agent,
holds the resulting JSON, and passes what is needed to the next one. Each stage
runs on the model assigned by the active RunProfile, so a senior supervisor can
run on a stronger model than the junior sub-agents.
"""
from __future__ import annotations

from time import perf_counter

from app.agents.arbitration import ArbitrationAgent
from app.agents.architect import SystemArchitectAgent
from app.agents.base import ChatClient
from app.agents.critic import DesignCriticAgent
from app.agents.requirements import RequirementsAgent
from app.models.schemas import Architecture, Critique, Requirements, RunResponse, TraceStep
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.mock import mock_run
from app.services.profiles import RunProfile, default_profile
from app.services.qwen_client import QwenClient, QwenError, QwenTruncatedError


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        profile: RunProfile | None = None,
        client: ChatClient | None = None,
    ):
        self.settings = settings
        self.profile = profile or default_profile(settings)
        self._client = client  # test override: when set, used for every role

    def _client_for(self, role: str) -> ChatClient:
        if self._client is not None:
            return self._client
        model = self.profile.models[role]
        return QwenClient(self.settings.model_copy(update={"qwen_model": model}))

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

    def _design_and_review(
        self, requirements: Requirements, guidance: list[str]
    ) -> tuple[Architecture, Critique, list[TraceStep]]:
        """Design + review, with an optional Critic->Architect rework loop.

        Round 1 is the initial design + review. While rework is enabled and the
        Critic still reports missing blocks, the findings are fed back to the
        Architect (via the existing guidance mechanism) and re-reviewed, up to
        max_rounds total rounds. missing_blocks is the trigger (warnings/risks
        are softer and would never converge).
        """
        steps: list[TraceStep] = []
        t = perf_counter()
        architecture = SystemArchitectAgent().run(self._client_for("architecture"), requirements, guidance)
        steps.append(self._arch_step(architecture, 1, int((perf_counter() - t) * 1000)))
        t = perf_counter()
        critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, guidance)
        steps.append(self._critic_step(critique, 1, int((perf_counter() - t) * 1000)))

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
            steps.append(self._arch_step(architecture, round_no, int((perf_counter() - t) * 1000)))
            t = perf_counter()
            critique = DesignCriticAgent().run(self._client_for("critique"), requirements, architecture, rework_guidance)
            steps.append(self._critic_step(critique, round_no, int((perf_counter() - t) * 1000)))

        return architecture, critique, steps

    def run(self, requirements_text: str, guidance: list[str] | None = None) -> RunResponse:
        if self.settings.mock_mode:
            return mock_run(requirements_text)
        guidance = guidance or []
        try:
            t = perf_counter()
            requirements = RequirementsAgent().run(
                self._client_for("requirements"), requirements_text, guidance
            )
            req_ms = int((perf_counter() - t) * 1000)

            architecture, critique, design_steps = self._design_and_review(requirements, guidance)

            t = perf_counter()
            arbitration = ArbitrationAgent().run(
                self._client_for("arbitration"), requirements, architecture, critique, guidance
            )
            arb_ms = int((perf_counter() - t) * 1000)
        except GuardBlocked as e:
            return self._guarded_fallback(
                requirements_text,
                f"API limit reached ({e.reason}). Showing example data instead — no charge.",
            )
        except QwenTruncatedError as e:
            return self._guarded_fallback(
                requirements_text,
                f"Qwen's answer was cut off ({e}). Showing example data instead — "
                "try a simpler request or raise GUARD_MAX_OUTPUT_TOKENS.",
            )
        except QwenError as e:
            return self._guarded_fallback(
                requirements_text,
                f"Qwen was unreachable ({e}). Showing example data instead.",
            )

        req_step = TraceStep(
            agent=RequirementsAgent.name, role=RequirementsAgent.role, status="ok",
            duration_ms=req_ms,
            summary=(
                f"Live Qwen: structured {len(requirements.requirements)} requirements, "
                f"raised {len(requirements.questions)} clarification questions "
                f"(confidence {requirements.confidence:.0%})."
            ),
        )
        arb_step = TraceStep(
            agent=ArbitrationAgent.name, role=ArbitrationAgent.role, status="ok",
            duration_ms=arb_ms,
            summary=(
                f"Live Qwen: approved the architecture; logged {len(arbitration.todo)} TODOs "
                f"and {len(arbitration.human_review)} human-review items."
            ),
        )

        return RunResponse(
            mode="qwen",
            requirements=requirements,
            architecture=architecture,
            critique=critique,
            arbitration=arbitration,
            trace=[req_step, *design_steps, arb_step],
            needs_approval=True,
        )

    def _guarded_fallback(self, requirements_text: str, notice: str) -> RunResponse:
        result = mock_run(requirements_text)
        result.notice = notice
        return result
