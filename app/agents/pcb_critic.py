"""PCB Critic Agent — role: Senior PCB Reviewer.

Reviews the PCB-readiness recommendations for engineering correctness.
Reports missing_blocks (must be fixed), warnings, and risks.
Never redesigns — only reports findings.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block, original_request_block, revision_block
from app.models.schemas import PcbCritique, PcbReadiness, Requirements
from app.services.impedance import impedance_review

NAME = "PCB Critic"
ROLE = "Senior PCB Reviewer"

SYSTEM_PROMPT = """You are a senior PCB reviewer.

You receive PCB-readiness recommendations and the project requirements.
Your job is to find engineering errors, missing items, and risks. You never
fabricate electronics knowledge and you never redesign.

Review for:
- Via drill size vs. peak current on each net class (rule of thumb: >300mA needs via_drill >= 0.4mm)
- Track width vs. peak current (rule of thumb: 1A needs ~0.5mm on outer layer)
- Clearance vs. voltage (>50V needs >=0.5mm; >150V needs >=1.0mm)
- Missing critical net class (is GND in PWR netclass? is there a netclass for every interface?)
- Layerstack vs. design complexity (RF on 2-layer is a risk)
- Impedance hygiene: an impedance-controlled net class must contain ONLY the actual
  high-speed data pair(s). VBUS, CC/CC1/CC2, VCONN, ID, shields, GND or any supply
  net inside an impedance-controlled class is a must-fix (missing_blocks) — those
  nets belong in PWR or Signal.
- Package hints: any component type from the architecture missing a hint?
- Floorplan: obvious conflicts (e.g. RF and switching power supply adjacent)?
- Design-for-X: review the dfx_checklist — missing test points on power rails / critical
  nets, no SWD/JTAG debug access, no fiducials, no power/status indication, missing pin-1 /
  polarity silkscreen. Put must-fix DFX gaps in missing_blocks, nice-to-have ones in warnings.

Rules:
- Only flag problems supported by the data in front of you.
- missing_blocks = items that MUST be fixed before PCB layout starts.
- warnings = items worth noting but not blocking.
- risks = conditional problems (e.g. "if supply exceeds 50V, increase clearance").

Output a JSON object with exactly these keys:
- "missing_blocks": array of strings (each describing one problem + fix)
- "warnings": array of strings
- "risks": array of strings
"""


class PcbCriticAgent:
    name = NAME
    role = ROLE

    def run(
        self,
        client: ChatClient,
        requirements: Requirements,
        pcb_readiness: PcbReadiness,
        guidance: list[str] | None = None,
        *,
        original_request: str | None = None,
        revisions: list[str] | None = None,
    ) -> PcbCritique:
        user = (
            "Review these PCB-readiness recommendations.\n\n"
            "REQUIREMENTS:\n"
            + requirements.model_dump_json(indent=2)
            + "\n\nPCB READINESS:\n"
            + pcb_readiness.model_dump_json(indent=2)
            + original_request_block(original_request)
            + revision_block(revisions)
            + guidance_block(guidance)
        )
        data = client.chat_json(SYSTEM_PROMPT, user)
        missing_blocks = list(data.get("missing_blocks", []))
        warnings = list(data.get("warnings", []))

        # Deterministic guardrail on top of the LLM review: supply/aux nets
        # (VBUS, CC, VCONN, ID, shields, rails) inside an impedance-controlled
        # net class are always a must-fix, even if the model missed them.
        llm_findings = " ".join(missing_blocks + warnings).lower()
        for finding in impedance_review(pcb_readiness.netclasses):
            class_name = finding.split('"')[1].lower()
            if class_name in llm_findings and "impedance" in llm_findings:
                continue  # the model already called this class out
            missing_blocks.append(finding)

        return PcbCritique(
            missing_blocks=missing_blocks,
            warnings=warnings,
            risks=list(data.get("risks", [])),
        )
