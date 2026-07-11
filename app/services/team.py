"""Static registry describing the AI engineering team for the UI.

Name, role and system prompt come straight from the agent modules (single
source of truth — what the UI shows is exactly what runs). Description and
the reads/delivers handoffs are pipeline-level knowledge, so they live here
next to the orchestration code rather than inside the individual agents.
"""
from __future__ import annotations

from app.agents import (
    arbitration,
    architect,
    baseline,
    critic,
    pcb_critic,
    pcb_engineer,
    requirements,
)

AGENT_REGISTRY = [
    {
        "key": "requirements",
        "module": requirements,
        "description": (
            "Turns your plain-English idea into structured engineering "
            "requirements — flagging assumptions and open questions instead "
            "of guessing."
        ),
        "reads": "Your request + hard constraints",
        "delivers": "Structured requirements → System Architect",
    },
    {
        "key": "architecture",
        "module": architect,
        "description": (
            "Designs the hardware architecture as hierarchical KiCad sheets: "
            "functional blocks, interfaces and power domains. Revises the "
            "design when the critic sends it back."
        ),
        "reads": "Requirements, critic findings",
        "delivers": "Block architecture → Design Critic",
    },
    {
        "key": "critique",
        "module": critic,
        "description": (
            "Attacks the proposed architecture: missing protection, debug "
            "access, testability, power domains. Can send the design back to "
            "the architect for rework."
        ),
        "reads": "Proposed architecture + requirements",
        "delivers": "Findings + verdict → Arbitration (or rework → Architect)",
    },
    {
        "key": "arbitration",
        "module": arbitration,
        "description": (
            "Triages the critic's findings: each one becomes a concrete TODO "
            "or is escalated as a decision only a human engineer can make."
        ),
        "reads": "Architecture + critique + assumptions",
        "delivers": "TODOs + human-review items → PCB Engineer",
    },
    {
        "key": "pcb_engineer",
        "module": pcb_engineer,
        "description": (
            "Prepares the PCB-readiness pack for a layout designer: layer "
            "stackup, net classes, board-level design rules and a floorplan "
            "sketch."
        ),
        "reads": "Approved architecture + requirements",
        "delivers": "PCB-readiness pack → PCB Critic",
    },
    {
        "key": "pcb_critic",
        "module": pcb_critic,
        "description": (
            "Reviews the PCB-readiness pack against the requirements: via "
            "sizes vs. current, clearance vs. voltage, missing net classes, "
            "DFX gaps."
        ),
        "reads": "PCB-readiness pack + requirements",
        "delivers": "Review verdict (or rework → PCB Engineer)",
    },
    {
        "key": "baseline",
        "module": baseline,
        "description": (
            "One AI playing the whole team at once — the one-shot design the "
            "multi-agent team is benchmarked against in compare and benchmark "
            "mode."
        ),
        "reads": "Your request (nothing else)",
        "delivers": "One-shot design — used only for comparison",
    },
]


def agents_payload() -> list[dict]:
    """JSON-safe team description for GET /api/agents."""
    return [
        {
            "key": entry["key"],
            "name": entry["module"].NAME,
            "role": entry["module"].ROLE,
            "description": entry["description"],
            "reads": entry["reads"],
            "delivers": entry["delivers"],
            "prompt": entry["module"].SYSTEM_PROMPT,
        }
        for entry in AGENT_REGISTRY
    ]
