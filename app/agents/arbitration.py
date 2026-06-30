"""Arbitration Agent — role: Chief Engineer.

Resolves the tension between the System Architect (who proposes) and the Design
Critic (who objects). It decides which critic findings become engineering TODOs,
which need a human decision, and which assumptions are accepted — producing the
approved plan the user signs off on before any KiCad project is generated.

The arbitrator does NOT redesign. The approved architecture is the architect's
output, attached deterministically by this agent so the model cannot corrupt the
structure the KiCad generator depends on in later milestones.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block, original_request_block, revision_block
from app.models.schemas import Arbitration, Architecture, Critique, Requirements

NAME = "Arbitration"
ROLE = "Chief Engineer"

SYSTEM_PROMPT = """You are the chief engineer arbitrating between a hardware
architect's proposal and a design critic's review.

You receive the requirements, the proposed architecture and the critic's
findings. You decide how to resolve them. You never fabricate electronics
knowledge and you never redesign the architecture yourself — the architecture is
approved as proposed; your job is only to triage the critic's findings and the
open assumptions.

For every critic warning, risk, missing block and recommendation, decide:
- it becomes a concrete engineering TODO (something to add/fix later), or
- it needs a human decision (an open question only the engineer can answer).

Then review the requirement assumptions and list those that are reasonable to
accept for the scaffold.

Rules:
- TODO items must start with "TODO:".
- Human-review items must start with "NEEDS HUMAN REVIEW:".
- Do not invent findings that the critic did not raise.
- Prefer "NEEDS HUMAN REVIEW" over guessing whenever a real engineering
  decision is involved (e.g. isolation, current budgets, safety).

Output a JSON object with exactly these keys:
- "todo": array of strings (each starting with "TODO:")
- "human_review": array of strings (each starting with "NEEDS HUMAN REVIEW:")
- "accepted_assumptions": array of strings
"""


class ArbitrationAgent:
    name = NAME
    role = ROLE

    def run(
        self,
        client: ChatClient,
        requirements: Requirements,
        architecture: Architecture,
        critique: Critique,
        guidance: list[str] | None = None,
        *,
        original_request: str | None = None,
        revisions: list[str] | None = None,
    ) -> Arbitration:
        user = (
            "Arbitrate this design. Decide TODOs, human-review items and "
            "accepted assumptions.\n\n"
            "REQUIREMENTS:\n"
            + requirements.model_dump_json(indent=2)
            + "\n\nARCHITECTURE:\n"
            + architecture.model_dump_json(indent=2)
            + "\n\nCRITIC FINDINGS:\n"
            + critique.model_dump_json(indent=2)
            + original_request_block(original_request)
            + revision_block(revisions)
            + guidance_block(guidance)
        )
        data = client.chat_json(SYSTEM_PROMPT, user)
        # The arbitrator triages findings; it does not redesign. We attach the
        # architect's architecture ourselves and ignore any version the model
        # may have echoed back, so the approved plan is always well-formed.
        return Arbitration(
            approved_architecture=architecture,
            todo=list(data.get("todo", [])),
            human_review=list(data.get("human_review", [])),
            accepted_assumptions=list(data.get("accepted_assumptions", [])),
        )
