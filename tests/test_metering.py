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
