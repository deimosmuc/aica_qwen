# app/services/comparison.py
"""Multi-agent vs single-agent efficiency comparison.

Runs the same requirement through the existing multi-agent Orchestrator and the
single-agent baseline, scores both with the deterministic rubric, and returns a
Comparison. In Mock Mode (or if the guard blocks the baseline) it produces a
clearly-labelled illustrative result so the demo always works.
"""
from __future__ import annotations

from app.agents.baseline import SingleAgentBaseline
from app.models.schemas import (
    BaselineResult,
    Comparison,
    ConcernResult,
    RunResponse,
)
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.orchestrator import Orchestrator
from app.services.qwen_client import QwenClient, QwenError
from app.services.rubric import RUBRIC, score

_MOCK_NOTICE = "Illustrative comparison (Mock Mode) — set a Qwen API key for a live measurement."


def mock_baseline() -> BaselineResult:
    """A representative single-pass output: gets the obvious blocks, misses much
    of the review (no surge/reset/clock/decoupling/isolation). Used in Mock Mode."""
    return BaselineResult(
        architecture=[
            "MCU block with an STM32",
            "Power supply: 24V to 5V and 3V3 rails",
            "USB-C connector for configuration",
            "RS485 interface",
            "Status LEDs",
        ],
        concerns=["Make sure the power supply can deliver enough current."],
        todos=["TODO: choose an STM32 variant.", "TODO: add the connectors."],
        human_review=[],
        assumptions=["Assumption: single-board design."],
        notes=["SWD can be used for programming."],
    )


def _flatten_multi(r: RunResponse) -> str:
    a, c, arb, req = r.architecture, r.critique, r.arbitration, r.requirements
    parts: list[str] = []
    parts += req.requirements + req.constraints + req.assumptions + req.questions
    parts += [f"{b.name} {b.purpose}" for b in a.blocks]
    parts += a.interfaces + a.signals + a.power + a.placeholder_components + a.notes
    parts += c.warnings + c.risks + c.missing_blocks + c.recommendations
    parts += arb.todo + arb.human_review + arb.accepted_assumptions
    return "\n".join(parts)


def _flatten_baseline(b: BaselineResult) -> str:
    return "\n".join(
        b.architecture + b.concerns + b.todos + b.human_review + b.assumptions + b.notes
    )


def _multi_stats(r: RunResponse) -> tuple[int, int, int]:
    """blocks, review findings, honesty markers — from the multi-agent output."""
    blocks = len(r.architecture.blocks)
    findings = len(r.critique.warnings) + len(r.critique.risks) + len(r.critique.missing_blocks)
    honesty = len(r.arbitration.todo) + len(r.arbitration.human_review) + len(r.arbitration.accepted_assumptions)
    return blocks, findings, honesty


def _single_stats(b: BaselineResult) -> tuple[int, int, int]:
    """blocks, review findings, honesty markers — from the single-agent output."""
    blocks = len(b.architecture)
    findings = len(b.concerns)
    honesty = len(b.todos) + len(b.human_review) + len(b.assumptions)
    return blocks, findings, honesty


def run_comparison(
    requirements_text: str,
    settings: Settings,
    multi_model: str | None = None,
    single_model: str | None = None,
) -> Comparison:
    multi_name = settings.resolve_model(multi_model)
    single_name = settings.resolve_model(single_model)

    multi = Orchestrator(settings.model_copy(update={"qwen_model": multi_name})).run(requirements_text)
    notice = multi.notice

    if settings.mock_mode:
        baseline = mock_baseline()
        single_calls = 0
        notice = notice or _MOCK_NOTICE
    else:
        try:
            single_settings = settings.model_copy(update={"qwen_model": single_name})
            baseline = SingleAgentBaseline().run(QwenClient(single_settings), requirements_text)
            single_calls = 1
        except (GuardBlocked, QwenError) as e:
            baseline = mock_baseline()
            single_calls = 0
            notice = (f"{notice} " if notice else "") + (
                f"Single-agent side ({single_name}) fell back to example data ({e})."
            )

    multi_scores = score(_flatten_multi(multi))
    single_scores = score(_flatten_baseline(baseline))
    concerns = [
        ConcernResult(
            id=c.id,
            label=c.label,
            covered_multi=multi_scores[c.id],
            covered_single=single_scores[c.id],
        )
        for c in RUBRIC
    ]
    multi_score = sum(multi_scores.values())
    single_score = sum(single_scores.values())
    mb, mf, mh = _multi_stats(multi)
    sb, sf, sh = _single_stats(baseline)

    return Comparison(
        requirements_text=requirements_text,
        mode=multi.mode,
        concerns=concerns,
        multi_score=multi_score,
        single_score=single_score,
        total=len(RUBRIC),
        delta=multi_score - single_score,
        multi_calls=len(multi.trace),
        single_calls=single_calls,
        multi_output=multi,
        single_output=baseline,
        notice=notice,
        multi_model=multi_name,
        single_model=single_name,
        multi_blocks=mb,
        single_blocks=sb,
        multi_findings=mf,
        single_findings=sf,
        multi_honesty=mh,
        single_honesty=sh,
    )
