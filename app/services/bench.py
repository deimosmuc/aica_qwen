"""Preset Bench — run one request through a curated trio of presets and compare
cost and quality side by side.

Live mode runs each preset through the real Orchestrator (sharing one API guard
for consistent budget accounting) and scores the output with the deterministic
rubric. Mock Mode returns fixed, clearly-illustrative rows so the demo works
without an API key.
"""
from __future__ import annotations

from app.models.schemas import BenchResult, BenchRow, RunResponse, RunUsage
from app.services.comparison import flatten_multi
from app.services.config import Settings
from app.services.guard import ApiGuard
from app.services.orchestrator import Orchestrator
from app.services.profiles import resolve_profile
from app.services.rubric import coverage

# The curated trio — edit here to change what the bench compares.
BENCH_PRESETS = ["Senior Review Team", "Uniform qwen-max", "Budget Turbo"]

_MOCK_NOTICE = "Illustrative bench (Mock Mode) — set a Qwen API key for real cost/quality numbers."

# Fixed illustrative numbers for Mock Mode (no real calls happen). Tell the
# intended story: the team scores highest AND costs less than single qwen-max.
_MOCK_ROWS = {
    "Senior Review Team": dict(rounds=2, calls=6, input_tokens=9000, output_tokens=5200, cost_usd=0.087, quality=12),
    "Uniform qwen-max": dict(rounds=1, calls=4, input_tokens=5500, output_tokens=3600, cost_usd=0.109, quality=9),
    "Budget Turbo": dict(rounds=1, calls=4, input_tokens=5200, output_tokens=3200, cost_usd=0.021, quality=7),
}


def _quality_per_cent(quality: int, usage: RunUsage) -> float:
    cents = usage.cost_usd * 100
    return round(quality / cents, 4) if cents > 0 else 0.0


def _rounds(resp: RunResponse) -> int:
    return max((s.round for s in resp.trace), default=1)


def _mark_best_and_takeaway(rows: list[BenchRow]) -> str:
    if not rows:
        return ""
    # Only rows that actually ran live are eligible to win: a degraded row's
    # quality came from example data, not the real preset, so crowning it would
    # be dishonest.
    eligible = [r for r in rows if not r.degraded]
    if not eligible:
        return "All presets fell back to example data — no live comparison available."
    # Best quality wins; ties broken by lower cost.
    best = max(eligible, key=lambda r: (r.quality, -r.usage.cost_usd))
    best.best_quality = True
    # A $0-cost winner means cached / no fresh calls — not a real cost story, so
    # don't make a "cheaper than" claim off it.
    if best.usage.cost_usd <= 0:
        return f"{best.preset}: highest quality ({best.quality}/12) — cost not shown (cached / no fresh calls)."
    # Compare the winner's cost to the priciest other live preset for the pitch line.
    pricier = [r for r in eligible if r.preset != best.preset and r.usage.cost_usd > best.usage.cost_usd]
    if pricier:
        rival = max(pricier, key=lambda r: r.usage.cost_usd)
        return (
            f"{best.preset}: highest quality ({best.quality}/12) AND cheaper "
            f"(${best.usage.cost_usd:.3f}) than {rival.preset} (${rival.usage.cost_usd:.3f})."
        )
    return f"{best.preset}: highest quality ({best.quality}/12) at ${best.usage.cost_usd:.3f}."


def _mock_result(requirements_text: str) -> BenchResult:
    rows = []
    for name in BENCH_PRESETS:
        d = _MOCK_ROWS[name]
        usage = RunUsage(calls=d["calls"], input_tokens=d["input_tokens"],
                         output_tokens=d["output_tokens"], cost_usd=d["cost_usd"])
        rows.append(BenchRow(
            preset=name, rounds=d["rounds"], usage=usage, quality=d["quality"],
            quality_per_cent=_quality_per_cent(d["quality"], usage),
        ))
    takeaway = _mark_best_and_takeaway(rows)
    return BenchResult(requirements_text=requirements_text, mode="mock", rows=rows,
                       takeaway=takeaway, illustrative=True, notice=_MOCK_NOTICE)


def run_bench(requirements_text: str, settings: Settings, guard: ApiGuard | None = None) -> BenchResult:
    # `guard` is a test-injection hook (mirrors Orchestrator); the live endpoint
    # passes none, so a fresh shared ApiGuard is built per bench run.
    if settings.mock_mode:
        return _mock_result(requirements_text)

    shared_guard = guard or ApiGuard(settings)
    rows: list[BenchRow] = []
    notice = None
    for name in BENCH_PRESETS:
        profile = resolve_profile(name, settings)
        resp = Orchestrator(settings, profile=profile, guard=shared_guard).run(requirements_text)
        if resp.notice:
            notice = resp.notice  # surface the last guard/fallback notice, if any
        usage = resp.usage or RunUsage()
        quality = coverage(flatten_multi(resp))
        rows.append(BenchRow(
            preset=name, rounds=_rounds(resp), usage=usage, quality=quality,
            quality_per_cent=_quality_per_cent(quality, usage),
            degraded=resp.mode != "qwen",  # fell back to example data mid-bench
        ))
    takeaway = _mark_best_and_takeaway(rows)
    degraded = [r.preset for r in rows if r.degraded]
    if degraded:
        notice = (
            f"{len(degraded)} of {len(rows)} presets fell back to example data "
            f"({', '.join(degraded)}) and are excluded from the winner."
            + (f" Last fallback reason: {notice}" if notice else "")
        )
    return BenchResult(requirements_text=requirements_text, mode="qwen", rows=rows,
                       takeaway=takeaway, illustrative=False, notice=notice)
