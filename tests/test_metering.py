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
    """A live run (faked httpx) sums usage across all six stage calls and
    attaches it to RunResponse.usage."""
    import json
    from app.services.config import Settings
    from app.services.guard import ApiGuard
    from app.services.orchestrator import Orchestrator

    # Per-call blobs — each agent gets its own keys.
    blobs = [
        # 1. RequirementsAgent
        {"requirements": [], "constraints": [], "questions": [], "assumptions": [],
         "confidence": 0.5, "clarifications": []},
        # 2. SystemArchitectAgent
        {"blocks": [], "interfaces": [], "signals": [], "power": [],
         "placeholder_components": [], "connections": [], "notes": []},
        # 3. DesignCriticAgent
        {"warnings": [], "risks": [], "missing_blocks": [], "recommendations": []},
        # 4. ArbitrationAgent
        {"approved_architecture": {"blocks": [], "interfaces": [], "signals": [],
                                   "power": [], "placeholder_components": [],
                                   "connections": [], "notes": []},
         "todo": [], "human_review": [], "accepted_assumptions": []},
        # 5. PcbEngineerAgent
        {"layerstack": "2-layer", "layerstack_reason": "simple",
         "netclasses": [{"name": "Default", "min_width_mm": 0.2, "clearance_mm": 0.2, "nets": []}],
         "constraints": {"min_clearance_mm": 0.2, "min_track_width_mm": 0.2,
                         "via_drill_mm": 0.4, "via_annular_ring_mm": 0.15},
         "floorplan_text": "", "floorplan_ascii": "", "package_hints": []},
        # 6. PcbCriticAgent
        {"missing_blocks": [], "warnings": [], "risks": []},
    ]
    call_count = {"n": 0}

    class _FakeResp:
        def raise_for_status(self): return None
        def json(self):
            idx = min(call_count["n"], len(blobs) - 1)
            call_count["n"] += 1
            return {
                "choices": [{"message": {"content": json.dumps(blobs[idx])}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 40},
            }

    monkeypatch.setattr("app.services.qwen_client.httpx.post", lambda *a, **k: _FakeResp())
    settings = Settings(qwen_api_key="x")
    guard = ApiGuard(settings, state_dir=tmp_path, now=lambda: 1000.0)
    res = Orchestrator(settings, guard=guard).run("A 24V board with an STM32")

    assert res.mode == "qwen"
    assert res.usage is not None
    assert res.usage.calls == 6          # requirements, architecture, critique, arbitration, pcb_engineer, pcb_critic
    assert res.usage.input_tokens == 600
    assert res.usage.output_tokens == 240
    assert res.usage.cost_usd > 0
