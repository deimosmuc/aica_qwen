"""Preset Bench: curated-trio cost+quality comparison."""
from app.services.bench import BENCH_PRESETS, run_bench
from app.services.config import Settings


def test_mock_bench_returns_illustrative_trio():
    s = Settings(qwen_api_key="")  # mock mode
    res = run_bench("A 24V industrial RS485 board with an STM32", s)
    assert res.mode == "mock"
    assert res.illustrative is True
    assert [r.preset for r in res.rows] == BENCH_PRESETS
    for r in res.rows:
        assert r.usage.calls > 0
        assert r.usage.cost_usd > 0
        assert 0 <= r.quality <= 12
    best = [r for r in res.rows if r.best_quality]
    assert len(best) == 1
    assert best[0].preset == "Senior Review Team"
    assert res.takeaway  # non-empty one-liner


def test_quality_per_cent_computed_and_zero_safe():
    from app.models.schemas import RunUsage
    from app.services.bench import _quality_per_cent

    assert _quality_per_cent(12, RunUsage(cost_usd=0.0)) == 0.0
    assert round(_quality_per_cent(12, RunUsage(cost_usd=0.087)), 2) == 1.38


def _row(preset, quality, cost, degraded=False):
    from app.models.schemas import BenchRow, RunUsage
    return BenchRow(preset=preset, rounds=1, usage=RunUsage(cost_usd=cost),
                    quality=quality, quality_per_cent=0.0, degraded=degraded)


def test_mark_best_picks_highest_quality_not_cheapest():
    """Selection logic, independent of the mock fixture: the highest-quality row
    wins even when it is neither first nor cheapest, and the takeaway names the
    priciest rival it still undercuts."""
    from app.services.bench import _mark_best_and_takeaway

    rows = [
        _row("Cheap", quality=7, cost=0.02),    # cheapest, low quality
        _row("Pricey single", quality=9, cost=0.11),  # pricier, mid quality
        _row("Team", quality=12, cost=0.087),   # best quality, not the cheapest
    ]
    takeaway = _mark_best_and_takeaway(rows)
    winners = [r for r in rows if r.best_quality]
    assert [w.preset for w in winners] == ["Team"]
    # takeaway names the pricier rival it beats on both quality and cost
    assert "Team" in takeaway and "Pricey single" in takeaway


def test_mark_best_tie_breaks_on_lower_cost():
    from app.services.bench import _mark_best_and_takeaway

    rows = [
        _row("Expensive12", quality=12, cost=0.20),
        _row("Cheaper12", quality=12, cost=0.05),  # same quality, lower cost -> wins
    ]
    _mark_best_and_takeaway(rows)
    assert [r.preset for r in rows if r.best_quality] == ["Cheaper12"]


def test_mark_best_takeaway_without_pricier_rival():
    """When the winner is also the most expensive, the takeaway has no rival clause."""
    from app.services.bench import _mark_best_and_takeaway

    rows = [
        _row("Best", quality=12, cost=0.10),  # highest quality AND highest cost
        _row("Other", quality=8, cost=0.04),
    ]
    takeaway = _mark_best_and_takeaway(rows)
    assert "Best" in takeaway and "cheaper" not in takeaway


def test_degraded_row_cannot_win_even_with_top_quality():
    """A preset that fell back to example data (mock) must not be crowned the
    winner — its quality came from mock data, not the real preset run."""
    from app.services.bench import _mark_best_and_takeaway

    rows = [
        _row("Degraded", quality=12, cost=0.0, degraded=True),  # top quality but fake
        _row("RealBest", quality=10, cost=0.05),
    ]
    _mark_best_and_takeaway(rows)
    assert [r.preset for r in rows if r.best_quality] == ["RealBest"]


def test_no_cost_claim_when_winner_cost_is_zero():
    """A $0-cost winner is a cache/no-fresh-call artifact, not a cost win — the
    takeaway must not claim it is 'cheaper' than a paid rival."""
    from app.services.bench import _mark_best_and_takeaway

    rows = [
        _row("Cached", quality=11, cost=0.0),    # real data, but cached -> $0
        _row("Paid", quality=9, cost=0.05),
    ]
    takeaway = _mark_best_and_takeaway(rows)
    assert [r.preset for r in rows if r.best_quality] == ["Cached"]
    assert "cheaper" not in takeaway


def test_all_degraded_has_no_winner():
    from app.services.bench import _mark_best_and_takeaway

    rows = [_row("A", 12, 0.0, degraded=True), _row("B", 10, 0.0, degraded=True)]
    takeaway = _mark_best_and_takeaway(rows)
    assert not any(r.best_quality for r in rows)
    assert takeaway
