"""Requirements Agent — role: Senior Systems Engineer.

Transforms ambiguous user input into structured engineering requirements.
It must never invent missing requirements; where information is missing it
raises clarification questions or records explicit assumptions instead.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block
from app.models.schemas import Requirements

NAME = "Requirements Agent"
ROLE = "Senior Systems Engineer"

SYSTEM_PROMPT = """You are a senior systems engineer reviewing a hardware request.

Your job is to turn an ambiguous natural-language request into structured
engineering requirements. You prepare engineering work; you never make final
engineering decisions and you never fabricate electronics knowledge.

Rules:
- Never invent requirements the user did not state or clearly imply.
- Detect ambiguity and missing information.
- Where something is genuinely needed but unstated, do NOT guess silently:
  either ask a clarification question or record an explicit ASSUMPTION.
- Normalise terminology (e.g. "micro" -> "microcontroller").
- Be honest about uncertainty via the confidence value (0.0-1.0).

Output a JSON object with exactly these keys:
- "requirements": array of strings (the structured functional requirements)
- "constraints": array of strings (environmental, mechanical, regulatory, etc.)
- "questions": array of strings (clarification questions for the human)
- "assumptions": array of strings, each prefixed with "ASSUMPTION:"
- "confidence": number between 0 and 1
"""


class RequirementsAgent:
    name = NAME
    role = ROLE

    def run(
        self, client: ChatClient, requirements_text: str, guidance: list[str] | None = None
    ) -> Requirements:
        data = client.chat_json(SYSTEM_PROMPT, requirements_text + guidance_block(guidance))
        return Requirements.model_validate(data)
