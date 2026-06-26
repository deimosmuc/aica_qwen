"""API Guard: budget cap, rate limits, input validation and caching."""
import pytest

from app.services.config import Settings
from app.services.guard import ApiGuard, GuardBlocked


def make_guard(tmp_path, clock, **overrides):
    settings = Settings(qwen_api_key="x", **overrides)
    return ApiGuard(settings, state_dir=tmp_path, now=clock)


def test_rejects_empty_or_junk_input(tmp_path):
    g = make_guard(tmp_path, lambda: 1000.0)
    with pytest.raises(GuardBlocked):
        g.precheck("sys", "  ", "qwen-plus")


def test_rejects_oversized_input(tmp_path):
    g = make_guard(tmp_path, lambda: 1000.0, guard_max_input_chars=50)
    with pytest.raises(GuardBlocked):
        g.precheck("sys", "x" * 100, "qwen-plus")


def test_allows_normal_input(tmp_path):
    g = make_guard(tmp_path, lambda: 1000.0)
    assert g.precheck("sys", "A 24V board with an STM32", "qwen-plus") is None


def test_cache_returns_without_new_call(tmp_path):
    g = make_guard(tmp_path, lambda: 1000.0)
    g.record("qwen-plus", "sys", "A 24V board with an STM32", 100, 50, {"ok": True})
    # Same request is now served from cache (no GuardBlocked, returns the dict).
    cached = g.precheck("sys", "A 24V board with an STM32", "qwen-plus")
    assert cached == {"ok": True}


def test_budget_cap_blocks(tmp_path):
    g = make_guard(tmp_path, lambda: 1000.0, guard_budget_usd=0.01,
                   guard_price_in_per_1k=1.0, guard_price_out_per_1k=1.0)
    # A normal request already exceeds the tiny 0.01 budget on estimate.
    with pytest.raises(GuardBlocked) as e:
        g.precheck("sys", "A 24V board with an STM32 and RS485", "qwen-plus")
    assert "budget" in str(e.value).lower()


def test_rate_limit_per_minute(tmp_path):
    now = [1000.0]
    g = make_guard(tmp_path, lambda: now[0], guard_rate_per_minute=2)
    for _ in range(2):
        g.record("qwen-plus", "sys", "different", 10, 10, {})
    with pytest.raises(GuardBlocked) as e:
        g.precheck("sys", "A 24V board with an STM32", "qwen-plus")
    assert "minute" in str(e.value).lower()


def test_spend_persists_across_instances(tmp_path):
    g1 = make_guard(tmp_path, lambda: 1000.0)
    g1.record("qwen-plus", "sys", "user input here", 1000, 1000, {})
    g2 = make_guard(tmp_path, lambda: 1000.0)  # fresh instance, same dir
    assert g2.status()["spent_usd"] > 0


def test_status_shape(tmp_path):
    g = make_guard(tmp_path, lambda: 1000.0, guard_budget_usd=5.0)
    s = g.status()
    assert s["budget_usd"] == 5.0
    assert s["remaining_usd"] == 5.0
    assert s["blocked"] is False


def test_record_uses_per_model_pricing(tmp_path):
    from app.services.config import Settings
    from app.services.guard import ApiGuard

    s = Settings(qwen_api_key="x")
    g = ApiGuard(s, state_dir=tmp_path, now=lambda: 1000.0)
    cost_turbo = g.record("qwen-turbo", "sys", "user", 1000, 1000, {"ok": True})
    cost_max = g.record("qwen-max", "sys2", "user2", 1000, 1000, {"ok": True})
    assert cost_max > cost_turbo


def test_record_unknown_model_falls_back_to_flat_price(tmp_path):
    from app.services.config import Settings
    from app.services.guard import ApiGuard

    s = Settings(qwen_api_key="x")
    g = ApiGuard(s, state_dir=tmp_path, now=lambda: 1000.0)
    cost = g.record("some-unlisted-model", "sys", "user", 1000, 1000, {"ok": True})
    expected = (1000 / 1000) * s.guard_price_in_per_1k + (1000 / 1000) * s.guard_price_out_per_1k
    assert round(cost, 6) == round(expected, 6)
