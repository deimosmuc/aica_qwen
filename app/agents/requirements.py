"""Requirements Agent — role: Senior Systems Engineer.

Transforms ambiguous user input into structured engineering requirements.
It must never invent missing requirements; where information is missing it
raises clarification questions or records explicit assumptions instead.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block, revision_block
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
- For each genuine, decision-changing ambiguity, prefer a "clarifications" entry
  with 2-3 concrete options over a bare question. Keep clarifications few (about
  2-4) — only the ambiguities that would actually change the design. Use
  "select": "multi" only when multiple options can legitimately be combined.

Output a JSON object with exactly these keys:
- "title": a concise project name of 2-4 words derived from the request, suitable
  as a document title (e.g. "Bat Detection Device", "Solar Soil Sensor"). Title
  case, no trailing punctuation, no leading verbs like "Design" or "Build".
- "requirements": array of strings (the structured functional requirements)
- "constraints": array of strings (environmental, mechanical, regulatory, etc.)
- "questions": array of strings (plain clarification questions; may be empty if you use clarifications)
- "assumptions": array of strings, each prefixed with "ASSUMPTION:"
- "confidence": number between 0 and 1
- "clarifications": array of objects, each:
    {"id": short-stable-id, "text": the question,
     "options": [{"label": short choice, "detail": one-line rationale}, ...] (2-3 options),
     "select": "single" (default) or "multi" (only when several options can sensibly combine),
     "assumption": what you would assume if the user skips this question}
"""


class RequirementsAgent:
    name = NAME
    role = ROLE

    def run(
        self,
        client: ChatClient,
        requirements_text: str,
        guidance: list[str] | None = None,
        *,
        revisions: list[str] | None = None,
    ) -> Requirements:
        user = requirements_text + revision_block(revisions) + guidance_block(guidance)
        data = client.chat_json(SYSTEM_PROMPT, user)
        return Requirements.model_validate(data)
