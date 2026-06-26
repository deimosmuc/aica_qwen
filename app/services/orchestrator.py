"""Orchestrator — owns all state and runs agents in sequence.

Agents never talk to each other directly. The orchestrator calls each agent,
holds the resulting JSON, and passes what is needed to the next one.

Milestone 5: the Requirements, Architect, Critic and Arbitration agents all run
for real against Qwen (when an API key is configured), completing the live
multi-agent pipeline. The KiCad scaffold, validation and ZIP export land in the
following milestones; until then the result is the approved plan the user signs
off on.
"""
from __future__ import annotations

from app.agents.arbitration import ArbitrationAgent
from app.agents.architect import SystemArchitectAgent
from app.agents.base import ChatClient
from app.agents.critic import DesignCriticAgent
from app.agents.requirements import RequirementsAgent
from app.models.schemas import RunResponse, TraceStep
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.mock import mock_run
from app.services.qwen_client import QwenClient, QwenError


class Orchestrator:
    def __init__(self, settings: Settings, client: ChatClient | None = None):
        self.settings = settings
        self._client = client

    def run(self, requirements_text: str) -> RunResponse:
        # No API key -> Mock Mode: the whole demo works with example data.
        if self.settings.mock_mode:
            return mock_run(requirements_text)

        client = self._client or QwenClient(self.settings)

        # Live stages, all guarded against runaway cost. If any stage is blocked
        # or fails, we fall back to example data with a clear notice — no charge
        # surprises and the demo keeps working.
        try:
            requirements = RequirementsAgent().run(client, requirements_text)
            architecture = SystemArchitectAgent().run(client, requirements)
            critique = DesignCriticAgent().run(client, requirements, architecture)
            arbitration = ArbitrationAgent().run(client, requirements, architecture, critique)
        except GuardBlocked as e:
            return self._guarded_fallback(
                requirements_text,
                f"API limit reached ({e.reason}). Showing example data instead — no charge.",
            )
        except QwenError as e:
            return self._guarded_fallback(
                requirements_text,
                f"Qwen was unreachable ({e}). Showing example data instead.",
            )

        req_step = TraceStep(
            agent=RequirementsAgent.name,
            role=RequirementsAgent.role,
            status="ok",
            summary=(
                f"Live Qwen: structured {len(requirements.requirements)} requirements, "
                f"raised {len(requirements.questions)} clarification questions "
                f"(confidence {requirements.confidence:.0%})."
            ),
        )
        arch_step = TraceStep(
            agent=SystemArchitectAgent.name,
            role=SystemArchitectAgent.role,
            status="ok",
            summary=(
                f"Live Qwen: proposed {len(architecture.blocks)} functional blocks, "
                f"{len(architecture.power)} power domains across hierarchical sheets."
            ),
        )
        n_findings = len(critique.warnings) + len(critique.risks) + len(critique.missing_blocks)
        critic_step = TraceStep(
            agent=DesignCriticAgent.name,
            role=DesignCriticAgent.role,
            status="warning" if n_findings else "ok",
            summary=(
                f"Live Qwen: flagged {len(critique.warnings)} warnings, "
                f"{len(critique.risks)} risks, {len(critique.missing_blocks)} missing blocks."
            ),
        )

        arb_step = TraceStep(
            agent=ArbitrationAgent.name,
            role=ArbitrationAgent.role,
            status="ok",
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
            trace=[req_step, arch_step, critic_step, arb_step],
            needs_approval=True,
        )

    def _guarded_fallback(self, requirements_text: str, notice: str) -> RunResponse:
        """Return example data when a live call was blocked or failed."""
        result = mock_run(requirements_text)
        result.notice = notice
        return result
