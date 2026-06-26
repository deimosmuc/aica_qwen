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
