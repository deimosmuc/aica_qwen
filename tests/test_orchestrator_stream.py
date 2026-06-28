"""Orchestrator.run_stream(): event ordering, rework, error fallback."""
import app.services.orchestrator as orch_mod
from app.models.schemas import (
    Arbitration, Architecture, Block, Critique, PcbCritique, PcbReadiness,
    Requirements, RunResponse, StreamEvent,
)
from app.services.config import Settings
from app.services.guard import GuardBlocked
from app.services.profiles import PROFILES, RunProfile

_ALL_ROLES = ("requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critique")


def _rework_profile(rounds=2):
    return RunProfile(name="t", models={r: "qwen-plus" for r in _ALL_ROLES},
                      rework=True, max_rounds=rounds)


def _stub_pcb_readiness() -> PcbReadiness:
    from app.models.schemas import ConstraintSet, NetClass
    return PcbReadiness(
        layerstack="2-layer", layerstack_reason="simple board",
        netclasses=[NetClass(name="Default", min_width_mm=0.2, clearance_mm=0.2)],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                  via_drill_mm=0.4, via_annular_ring_mm=0.15),
        floorplan_text="MCU central.", floorplan_ascii="[MCU]", package_hints=[],
    )


def _patch_agents(monkeypatch, critic_fn, calls):
    monkeypatch.setattr(orch_mod.RequirementsAgent, "run",
                        lambda self, c, text, g=None: Requirements(requirements=["r"], confidence=0.5))

    def arch(self, c, requirements, g=None):
        calls["arch"] += 1
        return Architecture(blocks=[Block(name="MCU", sheet="mcu.kicad_sch", purpose="core")])

    def crit(self, c, requirements, architecture, g=None):
        calls["crit"] += 1
        return critic_fn(calls["crit"])

    monkeypatch.setattr(orch_mod.SystemArchitectAgent, "run", arch)
    monkeypatch.setattr(orch_mod.DesignCriticAgent, "run", crit)
    monkeypatch.setattr(orch_mod.ArbitrationAgent, "run",
                        lambda self, c, req, arch, crit, g=None: Arbitration(approved_architecture=arch))
    monkeypatch.setattr(orch_mod.PcbEngineerAgent, "run",
                        lambda self, c, req, arch, arb, g=None: _stub_pcb_readiness())
    monkeypatch.setattr(orch_mod.PcbCriticAgent, "run",
                        lambda self, c, req, pcb, g=None: PcbCritique())


def test_stream_emits_stage_events_then_final(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(), calls)
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"),
                                        profile=PROFILES["Uniform qwen-plus"]).run_stream("board"))
    assert all(isinstance(e, StreamEvent) for e in events)
    stage = [e for e in events if e.type == "stage"]
    final = [e for e in events if e.type == "final"]
    assert len(stage) == 6                      # one per agent, no rework
    assert all(e.step is not None for e in stage)
    assert len(final) == 1 and final[-1] is events[-1]   # final is last
    assert isinstance(final[0].result, RunResponse)
    # the final trace equals the streamed steps, in order
    assert [e.step.agent for e in stage] == [s.agent for s in final[0].result.trace]


def test_stream_rework_emits_round_two_steps(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["DUMMY_CLOCK"]) if n == 1 else Critique(), calls)
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"),
                                        profile=_rework_profile()).run_stream("board"))
    stage = [e for e in events if e.type == "stage"]
    assert any(e.step.round == 2 for e in stage)         # rework streamed live
    assert calls["arch"] == 2 and calls["crit"] == 2


def test_stream_error_yields_error_then_mock_final(monkeypatch):
    def boom(self, c, text, g=None):
        raise GuardBlocked("budget cap")
    monkeypatch.setattr(orch_mod.RequirementsAgent, "run", boom)
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="sk-test")).run_stream("board"))
    assert any(e.type == "error" and "budget cap" in (e.notice or "") for e in events)
    final = [e for e in events if e.type == "final"]
    assert len(final) == 1 and final[0].result.mode == "mock"


def test_run_still_returns_final_result(monkeypatch):
    # The blocking run() is now a drainer over run_stream(); behaviour unchanged.
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(), calls)
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"),
                                profile=PROFILES["Uniform qwen-plus"]).run("board")
    assert isinstance(out, RunResponse)
    assert len(out.trace) == 6


def test_stream_mock_mode_emits_steps_and_final():
    events = list(orch_mod.Orchestrator(Settings(qwen_api_key="")).run_stream("a 24V board"))
    stage = [e for e in events if e.type == "stage"]
    final = [e for e in events if e.type == "final"]
    assert len(stage) == len(final[0].result.trace) == 6
    assert final[0].result.mode == "mock"
