# app/agents/baseline.py
"""Single-Agent Baseline — the comparison's control group.

ONE LLM call asked to do, in a single pass, what the whole agent team does. The
prompt is competent and fair (not a strawman) and explicitly stays high-level —
a scaffold plus review with placeholder blocks only, no part values or placement —
so the comparison measures review thoroughness at the same altitude.
"""
from __future__ import annotations

from app.agents.base import ChatClient
from app.models.schemas import BaselineResult

NAME = "Single-Agent Baseline"
ROLE = "Generalist (one-shot)"

SYSTEM_PROMPT = """You are a single AI assistant acting as an entire hardware
engineering team at once. From a natural-language hardware request you produce, in
ONE response, a high-level engineering scaffold.

Stay HIGH-LEVEL, like a project scaffold:
- Identify functional blocks, power domains and interfaces; recommend PLACEHOLDER
  components only (e.g. DUMMY_MCU). Do NOT choose real parts or values, and do NOT
  place or wire components. No finished schematic.
- Surface engineering concerns (protection, debug, testability, interfaces, power,
  documentation) as review findings and TODOs.
- Be honest: where something is uncertain, record an ASSUMPTION or a
  "NEEDS HUMAN REVIEW" item instead of fabricating.

Output a JSON object with exactly these keys:
- "architecture": array of strings (functional blocks / power domains / interfaces)
- "concerns": array of strings (design review findings)
- "todos": array of strings
- "human_review": array of strings
- "assumptions": array of strings
- "notes": array of strings
"""


class SingleAgentBaseline:
    name = NAME
    role = ROLE

    def run(self, client: ChatClient, requirements_text: str) -> BaselineResult:
        data = client.chat_json(SYSTEM_PROMPT, requirements_text)
        return BaselineResult.model_validate(data)
