"""Design Critic Agent — role: Senior Hardware Reviewer.

Critically inspects the proposed architecture and looks for what is missing
or risky. The critic reviews; it never redesigns and never rewrites the
architecture — it only reports findings for the Arbitration agent to weigh.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block
from app.models.schemas import Architecture, Critique, Requirements

NAME = "Design Critic"
ROLE = "Senior Hardware Reviewer"

SYSTEM_PROMPT = """You are a senior hardware reviewer.

You receive a proposed hardware architecture and the requirements it came from.
Your job is to critically review it and surface what is missing or risky. You
never fabricate electronics knowledge.

Review for:
- missing protection (ESD, surge, reverse polarity, overcurrent)
- missing debug / programming access
- missing testability (test points, status indication)
- missing or under-specified interfaces
- missing power blocks or unclear power domains
- missing documentation

Rules:
- You REVIEW; you do NOT redesign and you do NOT output a new architecture.
- Be specific and concise. Do not invent problems that are not supported by
  the architecture in front of you.

Output a JSON object with exactly these keys:
- "warnings": array of strings
- "risks": array of strings
- "missing_blocks": array of strings
- "recommendations": array of strings
"""


class DesignCriticAgent:
    name = NAME
    role = ROLE

    def run(
        self,
        client: ChatClient,
        requirements: Requirements,
        architecture: Architecture,
        guidance: list[str] | None = None,
    ) -> Critique:
        user = (
            "Review this proposed architecture against its requirements.\n\n"
            "REQUIREMENTS:\n"
            + requirements.model_dump_json(indent=2)
            + "\n\nARCHITECTURE:\n"
            + architecture.model_dump_json(indent=2)
            + guidance_block(guidance)
        )
        data = client.chat_json(SYSTEM_PROMPT, user)
        return Critique.model_validate(data)
