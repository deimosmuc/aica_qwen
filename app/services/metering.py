"""Per-run usage meter — sums token/cost across every stage client of one run.

The Orchestrator creates one RunMeter per run() and shares it with every stage
QwenClient, so usage accumulates across stages AND rework rounds without any
per-stage bookkeeping. The snapshot rides home on RunResponse.usage.
"""
from __future__ import annotations

from app.models.schemas import RunUsage


class RunMeter:
    def __init__(self) -> None:
        self._calls = 0
        self._in = 0
        self._out = 0
        self._cost = 0.0

    def add(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self._calls += 1
        self._in += input_tokens
        self._out += output_tokens
        self._cost += cost_usd

    def snapshot(self) -> RunUsage:
        return RunUsage(
            calls=self._calls,
            input_tokens=self._in,
            output_tokens=self._out,
            cost_usd=round(self._cost, 6),
        )
