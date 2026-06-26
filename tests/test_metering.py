"""Preset Bench: per-run token/cost metering."""
from app.models.schemas import RunUsage
from app.services.metering import RunMeter


def test_meter_starts_empty():
    assert RunMeter().snapshot() == RunUsage()


def test_meter_accumulates_across_calls():
    m = RunMeter()
    m.add(100, 50, 0.001)
    m.add(200, 80, 0.002)
    snap = m.snapshot()
    assert snap.calls == 2
    assert snap.input_tokens == 300
    assert snap.output_tokens == 130
    assert round(snap.cost_usd, 6) == 0.003


def test_orchestrator_attaches_summed_usage(tmp_path, monkeypatch):
    """A live run (faked httpx) sums usage across all four stage calls and
    attaches it to RunResponse.usage."""
    from app.services.config import Settings
    from app.services.guard import ApiGuard
    from app.services.orchestrator import Orchestrator

    payload = {
        "choices": [{"message": {"content": '{"requirements":[],"blocks":[],"warnings":[],"approved_architecture":{"blocks":[]}}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 40},
    }

    class _FakeResp:
        def raise_for_status(self): return None
        def json(self): return payload

    monkeypatch.setattr("app.services.qwen_client.httpx.post", lambda *a, **k: _FakeResp())
    settings = Settings(qwen_api_key="x")
    guard = ApiGuard(settings, state_dir=tmp_path, now=lambda: 1000.0)
    res = Orchestrator(settings, guard=guard).run("A 24V board with an STM32")

    assert res.mode == "qwen"
    assert res.usage is not None
    assert res.usage.calls == 4          # requirements, architecture, critique, arbitration
    assert res.usage.input_tokens == 400
    assert res.usage.output_tokens == 160
    assert res.usage.cost_usd > 0
